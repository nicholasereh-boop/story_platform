import hashlib
import json

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView
from .services import access, fx, github, payments

from apps.audit import service as audit
from apps.core.http import mark_per_user
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsStaffUser
from apps.core.text import clean_plain_text
from apps.core.throttles import FlexibleScopedRateThrottle
from apps.media.images import display_name_of, process_uploads

from .models import PaymentEvent, ProjectScreenshot, SourceDownload, SourcePackage, SourceProject, SourcePurchase, Technology
from .permissions import IsActiveUser, MarketplaceEnabled, PublicReadOrActive
from .serializers import (
    ModerationSerializer, OwnerProjectSerializer, backend_price_message, ProjectCardSerializer, ProjectDetailSerializer, ProjectWriteSerializer,
    PurchaseSerializer, TechnologySerializer, ScreenshotSerializer, check_package_kind,
)
from .services import access, github, payments
from .services.packages import remove_package, save_package, save_screenshots
from .services.uploads import ArchiveRejected, clean_version, limits, safe_download_name, sanitize_archive

MAX_SCREENSHOTS = 8


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "This is not available right now."


class BadGateway(APIException):
    status_code = 502
    default_detail = "The payment provider could not be reached."


class Conflict(APIException):
    status_code = 409
    default_detail = "This conflicts with the current state."


def backend_is_unpriced(project):
    """True when the rule "backend code is never free" is on and this project has a backend package priced at 0."""
    return (
        getattr(settings, "MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True)
        and project.backend_price <= 0
        and any(p.kind == "backend" and p.is_active for p in project.packages.all())
    )


def card_queryset():
    return SourceProject.objects.select_related("owner__profile").prefetch_related("technologies", "screenshots", "packages")


def owned_project(request, pk):
    """The project, only if it belongs to the signed-in seller. Anything else is a 404 (we do not reveal other sellers' drafts)."""
    return get_object_or_404(card_queryset().filter(owner=request.user), pk=pk)


def fresh(project):
    return card_queryset().get(pk=project.pk)


def _delete_files(storage, names):
    for name in names:
        try:
            storage.delete(name)
        except Exception:
            pass  # a file that cannot be removed must never undo the database change


def client_ip_hash(request):
    try:
        return audit.hash_ip(BaseThrottle().get_ident(request))
    except Exception:
        return ""


# ------------------------------------------------------------------------------------------ public
class ProjectListCreateView(generics.ListCreateAPIView):
    """GET: published projects (anyone). POST: a signed-in member starts a new draft."""

    permission_classes = [MarketplaceEnabled, PublicReadOrActive]
    pagination_class = StandardPagination

    def get_throttles(self):
        if self.request.method == "GET":
            self.throttle_scope = "marketplace_read"
            return [FlexibleScopedRateThrottle()]  # replaces the default anonymous limit, like the public stories API
        self.throttle_scope = "marketplace_write"
        return super().get_throttles()

    def get_serializer_class(self):
        return ProjectWriteSerializer if self.request.method == "POST" else ProjectCardSerializer

    def get_queryset(self):
        qs = card_queryset().filter(status=SourceProject.Status.PUBLISHED)
        params = self.request.query_params
        q = (params.get("q") or "").strip()[:100]
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(summary__icontains=q) | Q(technologies__name__icontains=q)).distinct()
        tech = (params.get("tech") or "").strip()
        if tech:
            qs = qs.filter(technologies__slug=tech)
        if params.get("free") in ("1", "true"):
            qs = qs.filter(
                Q(frontend_price=0, packages__kind="frontend", packages__is_active=True)
                | Q(backend_price=0, packages__kind="backend", packages__is_active=True)
            ).distinct()
        ordering = params.get("ordering")
        return qs.order_by("title", "id") if ordering == "title" else qs.order_by("-published_at", "-id")

    def create(self, request, *args, **kwargs):
        serializer = ProjectWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            project = serializer.save(owner=request.user)
        return Response(OwnerProjectSerializer(fresh(project), context={"request": request}).data, status=status.HTTP_201_CREATED)


class MarketplaceConfigView(APIView):
    """GET: what the pages need to describe pricing truthfully (the currency, and that backend code is always paid)."""

    permission_classes = [MarketplaceEnabled, AllowAny]
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "marketplace_read"

    def get(self, request, **kwargs):
        return Response({
            "currency": getattr(settings, "MARKETPLACE_CURRENCY", "USD"),
            "backend_requires_payment": bool(getattr(settings, "MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True)),
            "max_price": settings.MARKETPLACE_MAX_PRICE,
            "payments_enabled": bool(settings.PAYSTACK_SECRET_KEY),
        })


class TechnologyListView(generics.ListAPIView):
    permission_classes = [MarketplaceEnabled, AllowAny]
    serializer_class = TechnologySerializer
    pagination_class = None
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "marketplace_read"

    def get_queryset(self):
        return Technology.objects.filter(projects__status=SourceProject.Status.PUBLISHED).distinct()


class ProjectDetailView(APIView):
    permission_classes = [MarketplaceEnabled, AllowAny]
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "marketplace_read"

    def get(self, request, slug, **kwargs):
        project = get_object_or_404(card_queryset(), slug=slug)
        user = request.user
        visible = project.status == SourceProject.Status.PUBLISHED or (
            user.is_authenticated and (project.owner_id == user.pk or user.is_staff)
        )
        if not visible:
            raise NotFound()
        response = Response(ProjectDetailSerializer(project, context={"request": request}).data)
        return mark_per_user(response, request)


# ------------------------------------------------------------------------------------------ seller
class MyProjectsView(generics.ListAPIView):
    permission_classes = [MarketplaceEnabled, IsActiveUser]
    serializer_class = OwnerProjectSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return card_queryset().filter(owner=self.request.user).order_by("-updated_at", "-id")


class MyProjectDetailView(APIView):
    permission_classes = [MarketplaceEnabled, IsActiveUser]

    def get(self, request, pk, **kwargs):
        return Response(OwnerProjectSerializer(owned_project(request, pk), context={"request": request}).data)


class ProjectUpdateView(APIView):
    """PATCH or DELETE a project. Only its seller; other sellers get a 404."""

    permission_classes = [MarketplaceEnabled, IsActiveUser]
    throttle_scope = "marketplace_write"

    def patch(self, request, pk, **kwargs):
        project = owned_project(request, pk)
        serializer = ProjectWriteSerializer(data=request.data, instance=project, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            project = serializer.save(owner=request.user, instance=project)
        body = OwnerProjectSerializer(fresh(project), context={"request": request}).data
        body["sent_back_to_review"] = getattr(project, "_sent_back_to_review", False)
        return Response(body)

    def delete(self, request, pk, **kwargs):
        project = owned_project(request, pk)
        if SourcePurchase.objects.filter(package__project=project).exists():
            raise Conflict("This project has buyers, so it cannot be deleted. Archive it instead.")
        package_files = [p.file.name for p in project.packages.all() if p.file]
        screenshot_files = [s.file.name for s in project.screenshots.all() if s.file]
        project.delete()
        _delete_files(SourcePackage._meta.get_field("file").storage, package_files)
        _delete_files(ProjectScreenshot._meta.get_field("file").storage, screenshot_files)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectStateView(APIView):
    """submit | unpublish | archive: the seller's own state changes."""

    permission_classes = [MarketplaceEnabled, IsActiveUser]
    throttle_scope = "marketplace_write"
    action_name = ""

    def post(self, request, pk, **kwargs):
        project = owned_project(request, pk)
        S = SourceProject.Status
        if self.action_name == "submit":
            return self.submit(request, project, S)
        if self.action_name == "unpublish":
            if project.status not in (S.PUBLISHED, S.PENDING):
                raise Conflict("Only a published or waiting project can be taken offline.")
            project.status = S.DRAFT
            project.save(update_fields=["status", "updated_at"])
        else:  # archive
            if project.status == S.ARCHIVED:
                raise Conflict("This project is already archived.")
            project.status = S.ARCHIVED
            project.save(update_fields=["status", "updated_at"])
            audit.log(request, "marketplace.archive", project, title=project.title, by="seller")
        return Response(OwnerProjectSerializer(fresh(project), context={"request": request}).data)

    def submit(self, request, project, S):
        if project.status not in (S.DRAFT, S.REJECTED):
            raise Conflict("This project has already been submitted.")
        problems = {}
        if not project.title.strip():
            problems["title"] = ["A title is required."]
        if len(project.description.strip()) < 30:
            problems["description"] = ["Describe the project in at least 30 characters."]
        if not project.rights_confirmed_at:
            problems["rights_confirmed"] = ["Confirm that you own this code or are allowed to distribute it."]
        if not any(p.is_active for p in project.packages.all()):
            problems["packages"] = ["Upload or import at least one package (frontend or backend)."]
        if backend_is_unpriced(project):
            problems["backend_price"] = [backend_price_message()]
        if problems:
            raise serializers.ValidationError(problems)
        with transaction.atomic():
            if settings.MARKETPLACE_REQUIRE_REVIEW and not request.user.is_staff:
                project.status = S.PENDING
                project.review_note = ""
                project.save(update_fields=["status", "review_note", "updated_at"])
                audit.log(request, "marketplace.submit", project, title=project.title)
            else:
                project.status = S.PUBLISHED
                project.review_note = ""
                project.published_at = project.published_at or timezone.now()
                project.save(update_fields=["status", "review_note", "published_at", "updated_at"])
                audit.log(request, "marketplace.publish", project, title=project.title, review="not required")
        return Response(OwnerProjectSerializer(fresh(project), context={"request": request}).data)


def _back_to_review_if_needed(request, project):
    """A published project whose files changed is checked again (unless review is off or staff did it)."""
    if project.status == SourceProject.Status.PUBLISHED and settings.MARKETPLACE_REQUIRE_REVIEW and not request.user.is_staff:
        project.status = SourceProject.Status.PENDING
        project.save(update_fields=["status", "updated_at"])
        return True
    return False


class ScreenshotUploadView(APIView):
    permission_classes = [MarketplaceEnabled, IsActiveUser]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "marketplace_upload"

    def post(self, request, pk, **kwargs):
        project = owned_project(request, pk)
        files = request.FILES.getlist("files") + request.FILES.getlist("file")
        if not files:
            raise serializers.ValidationError({"file": ["No image was uploaded."]})
        if project.screenshots.count() + len(files) > MAX_SCREENSHOTS:
            raise serializers.ValidationError({"file": [f"A project can have at most {MAX_SCREENSHOTS} screenshots."]})
        processed = process_uploads(files)  # same checks as the media library: decoded, re-encoded, metadata stripped
        alt = clean_plain_text(request.data.get("alt_text", ""), max_length=300) if len(files) == 1 else ""
        save_screenshots(project, processed, alt)
        return Response(ScreenshotSerializer(ProjectScreenshot.objects.filter(project=project), many=True).data, status=status.HTTP_201_CREATED)


class ScreenshotDeleteView(APIView):
    permission_classes = [MarketplaceEnabled, IsActiveUser]
    throttle_scope = "marketplace_write"

    def delete(self, request, pk, shot_id, **kwargs):
        project = owned_project(request, pk)
        shot = get_object_or_404(project.screenshots, pk=shot_id)
        name = shot.file.name
        shot.delete()
        try:
            shot.file.storage.delete(name)
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class PackageUploadView(APIView):
    """POST a ZIP from the seller's computer. The server checks and REBUILDS it (see services/uploads.py)."""

    permission_classes = [MarketplaceEnabled, IsActiveUser]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "marketplace_upload"

    def post(self, request, pk, **kwargs):
        project = owned_project(request, pk)
        kind = check_package_kind(request.data.get("kind"))
        upload = request.FILES.get("file")
        if upload is None:
            raise serializers.ValidationError({"file": ["Choose a ZIP file to upload."]})
        if not str(upload.name or "").lower().endswith(".zip"):
            raise serializers.ValidationError({"file": ["Only .zip files are accepted."]})
        if upload.size > limits()["archive"]:
            raise serializers.ValidationError({"file": [f"The file is larger than {limits()['archive'] // (1024 * 1024)} MB."]})
        try:
            version = clean_version(request.data.get("version"))
            archive = sanitize_archive(upload)
        except ArchiveRejected as exc:
            raise serializers.ValidationError({"file": [exc.message]})
        try:
            package = save_package(project, kind, archive, source="upload", original_name=display_name_of(upload), version=version)
        finally:
            archive.close()
        sent_back = _back_to_review_if_needed(request, project)
        body = OwnerProjectSerializer(fresh(project), context={"request": request}).data
        body["sent_back_to_review"] = sent_back
        return Response(body, status=status.HTTP_201_CREATED)


class GitHubImportView(APIView):
    """POST {kind, repository, ref?, token?}. The token (private repositories only) is used for this one request."""

    permission_classes = [MarketplaceEnabled, IsActiveUser]
    parser_classes = [JSONParser]
    throttle_scope = "marketplace_upload"

    def post(self, request, pk, **kwargs):
        if not settings.MARKETPLACE_GITHUB_ENABLED:
            raise NotFound()
        project = owned_project(request, pk)
        kind = check_package_kind(request.data.get("kind"))
        try:
            owner, repo, ref = github.parse_repository(request.data.get("repository"), request.data.get("ref"))
            token = github.clean_token(request.data.get("token"))
            version = clean_version(request.data.get("version"))
            raw = github.download_zipball(owner, repo, ref, token)
        except github.GitHubImportError as exc:
            raise serializers.ValidationError({"repository": [exc.message]})
        except ArchiveRejected as exc:
            raise serializers.ValidationError({"version": [exc.message]})
        finally:
            token = None  # nothing below needs it, and it is never stored or logged
        try:
            archive = sanitize_archive(raw)
        except ArchiveRejected as exc:
            raise serializers.ValidationError({"repository": [exc.message]})
        finally:
            raw.close()
        try:
            save_package(project, kind, archive, source="github", source_ref=f"{owner}/{repo}@{ref or 'default'}",
                         original_name=f"{repo}.zip", version=version)
        finally:
            archive.close()
        sent_back = _back_to_review_if_needed(request, project)
        body = OwnerProjectSerializer(fresh(project), context={"request": request}).data
        body["sent_back_to_review"] = sent_back
        return Response(body, status=status.HTTP_201_CREATED)


class PackageRemoveView(APIView):
    permission_classes = [MarketplaceEnabled, IsActiveUser]
    throttle_scope = "marketplace_write"

    def delete(self, request, pk, kind, **kwargs):
        project = owned_project(request, pk)
        package = get_object_or_404(project.packages, kind=check_package_kind(kind))
        remove_package(package)
        return Response(OwnerProjectSerializer(fresh(project), context={"request": request}).data)


# ------------------------------------------------------------------------------------------ buying
class CheckoutView(APIView):
    """POST {kind}. The PRICE IS READ FROM THE DATABASE; any amount the browser sends is ignored."""

    permission_classes = [MarketplaceEnabled, IsActiveUser]
    parser_classes = [JSONParser]
    throttle_scope = "marketplace_checkout"

    def post(self, request, pk, **kwargs):
        kind = check_package_kind(request.data.get("kind"))
        project = get_object_or_404(card_queryset(), pk=pk, status=SourceProject.Status.PUBLISHED)
        package = get_object_or_404(project.packages, kind=kind, is_active=True)
        if project.owner_id == request.user.pk:
            raise Conflict("You cannot buy your own project.")
        price = project.price_for(kind)
        if price <= 0:
            if kind == "backend" and getattr(settings, "MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True):
                raise serializers.ValidationError({"kind": ["The seller has not set a price for this backend yet, so it cannot be bought."]})
            raise serializers.ValidationError({"kind": ["This package is free. Use the download button."]})
        if access.has_paid(request.user, package):
            raise Conflict("You already own this package. Find it under My purchases.")

        try:
            client = payments.get_client()  # refuses (503) when no secret key is configured
        except payments.PaystackError as exc:
            raise (ServiceUnavailable if exc.status == 503 else BadGateway)(exc.message)
        try:
            charge_amount, charge_currency, rate = fx.charge_quote(price, project.currency)  # dollars -> what Paystack can collect
        except fx.RateUnavailable:
            raise ServiceUnavailable("Payments are not available right now. Please try again shortly.")
        amount_minor = payments.to_minor(charge_amount)
        with transaction.atomic():
            purchase = SourcePurchase.objects.create(
                buyer=request.user, package=package, amount=charge_amount, amount_minor=amount_minor, currency=charge_currency,
                list_price=price, list_currency=project.currency, fx_rate=rate, reference=payments.new_reference(),
            )
        callback = f"{settings.FRONTEND_URL}/marketplace/purchases?reference={purchase.reference}"
        try:
            data = client.initialize(
                email=request.user.email, amount_minor=amount_minor, reference=purchase.reference, currency=charge_currency,
                callback_url=callback, metadata={"purchase_id": purchase.pk, "package_id": package.pk},
            )
        except payments.PaystackError as exc:
            purchase.status = SourcePurchase.Status.FAILED
            purchase.failure_reason = "initialize_failed"
            purchase.save(update_fields=["status", "failure_reason"])
            raise (ServiceUnavailable if exc.status == 503 else BadGateway)(exc.message)
        url = str(data.get("authorization_url", ""))
        if not url.startswith("https://"):
            purchase.status = SourcePurchase.Status.FAILED
            purchase.failure_reason = "bad_checkout_url"
            purchase.save(update_fields=["status", "failure_reason"])
            raise BadGateway()
        return Response({
            "reference": purchase.reference, "authorization_url": url, "amount": f"{charge_amount:.2f}", "currency": charge_currency,
            "list_price": f"{price:.2f}", "list_currency": project.currency,
        })

    
class VerifyPaymentView(APIView):
    """POST {reference}: the buyer's browser came back from Paystack. The SERVER asks Paystack; the browser's claim is not used."""

    permission_classes = [MarketplaceEnabled, IsActiveUser]
    parser_classes = [JSONParser]
    throttle_scope = "marketplace_verify"

    def post(self, request, **kwargs):
        reference = str(request.data.get("reference", "")).strip()[:64]
        purchase = SourcePurchase.objects.filter(reference=reference, buyer=request.user).select_related("package__project").first()
        if purchase is None:
            raise NotFound()
        if purchase.status != SourcePurchase.Status.SUCCESS:
            try:
                purchase, outcome = payments.verify_and_fulfil(purchase)
            except payments.PaystackError as exc:
                raise (ServiceUnavailable if exc.status == 503 else BadGateway)(exc.message)
            if outcome == "paid":
                audit.log(request, "marketplace.purchase", purchase, project=purchase.package.project.title, kind=purchase.package.kind,
                          amount=str(purchase.amount), currency=purchase.currency)
        return Response(PurchaseSerializer(purchase).data)


class PaystackWebhookView(APIView):
    """Paystack calls this. Nothing in the body is believed until the signature is valid AND Paystack confirms it again."""

    authentication_classes = []
    permission_classes = [MarketplaceEnabled, AllowAny]
    parser_classes = []  # the body is read raw: the signature covers its exact bytes
    throttle_classes = [FlexibleScopedRateThrottle]
    throttle_scope = "marketplace_webhook"

    def post(self, request, **kwargs):
        raw = request.body
        if not payments.signature_is_valid(raw, request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")):
            return Response({"errors": {"detail": "Invalid signature."}, "message": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw.decode("utf-8"))
            event = str(payload.get("event", ""))[:60]
            reference = str((payload.get("data") or {}).get("reference", ""))[:64]
        except (ValueError, AttributeError, UnicodeDecodeError):
            return Response({"errors": {"detail": "Bad payload."}, "message": "Bad payload."}, status=status.HTTP_400_BAD_REQUEST)

        digest = hashlib.sha256(raw).hexdigest()
        record, created = PaymentEvent.objects.get_or_create(payload_hash=digest, defaults={"event": event, "reference": reference})
        if not created and record.processed_at:
            return Response({"received": True, "duplicate": True})

        outcome = "ignored"
        if event == "charge.success" and reference:
            purchase = SourcePurchase.objects.filter(reference=reference).select_related("package__project", "buyer").first()
            if purchase is None:
                outcome = "unknown_reference"
            else:
                try:
                    verified = payments.get_client().verify(reference)  # never trust the webhook body itself
                except payments.PaystackError:
                    return Response({"errors": {"detail": "Try again later."}, "message": "Try again later."}, status=503)
                purchase, outcome = payments.fulfil(reference, verified)
                if outcome == "paid":
                    audit.log(request, "marketplace.purchase", purchase, actor=purchase.buyer, project=purchase.package.project.title,
                              kind=purchase.package.kind, amount=str(purchase.amount), currency=purchase.currency, via="webhook")
        record.outcome = outcome
        record.processed_at = timezone.now()
        record.save(update_fields=["outcome", "processed_at"])
        return Response({"received": True})


class PurchaseListView(generics.ListAPIView):
    permission_classes = [MarketplaceEnabled, IsActiveUser]
    serializer_class = PurchaseSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return SourcePurchase.objects.filter(buyer=self.request.user).select_related("package__project").order_by("-created_at", "-id")


class PackageDownloadView(APIView):
    """GET: the ONLY way to a source package. Entitlement is re-checked on every request; each download is recorded."""

    permission_classes = [MarketplaceEnabled, IsActiveUser]
    throttle_scope = "marketplace_download"

    def get(self, request, pk, **kwargs):
        package = get_object_or_404(SourcePackage.objects.select_related("project"), pk=pk)
        basis, purchase = access.download_basis(request.user, package)
        if basis is None:
            # A package that is not public looks like it does not exist; a paid one says what is missing.
            project = package.project
            if project.status == SourceProject.Status.PUBLISHED and package.is_active and project.price_for(package.kind) > 0:
                raise PermissionDenied("Buy this package to download it.")
            raise NotFound()
        if not package.file:
            raise NotFound()
        try:
            handle = package.file.storage.open(package.file.name, "rb")
        except (FileNotFoundError, OSError):
            raise ServiceUnavailable("The file is temporarily unavailable. Please try again later.")
        SourceDownload.objects.create(user=request.user, package=package, purchase=purchase, basis=basis, ip_hash=client_ip_hash(request))
        response = FileResponse(handle, as_attachment=True, filename=safe_download_name(package.project.slug, package.kind, package.version),
                                content_type="application/zip")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


# ------------------------------------------------------------------------------------------ staff moderation
class AdminProjectListView(generics.ListAPIView):
    permission_classes = [IsStaffUser]
    serializer_class = ModerationSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = card_queryset()
        state = self.request.query_params.get("status")
        if state in SourceProject.Status.values:
            qs = qs.filter(status=state)
        return qs.order_by("-updated_at", "-id")


class AdminProjectActionView(APIView):
    """approve | reject | archive. Moderators decide; they never edit a seller's content."""

    permission_classes = [IsStaffUser]

    def post(self, request, pk, action, **kwargs):
        project = get_object_or_404(card_queryset(), pk=pk)
        S = SourceProject.Status
        if action == "approve":
            if project.status not in (S.PENDING, S.REJECTED, S.DRAFT, S.ARCHIVED):
                raise Conflict("This project is already published.")
            if backend_is_unpriced(project):
                raise Conflict(backend_price_message() + " Ask the seller to set one before it is published.")
            project.status = S.PUBLISHED
            project.review_note = ""
            project.published_at = project.published_at or timezone.now()
            audit_name = "marketplace.publish"
        elif action == "reject":
            note = clean_plain_text(request.data.get("note", ""), max_length=500)
            if not note:
                raise serializers.ValidationError({"note": ["Tell the seller what to fix."]})
            project.status = S.REJECTED
            project.review_note = note
            audit_name = "marketplace.reject"
        elif action == "archive":
            project.status = S.ARCHIVED
            audit_name = "marketplace.archive"
        else:
            raise NotFound()
        with transaction.atomic():
            project.save()
            audit.log(request, audit_name, project, title=project.title, status_to=project.status, by="staff")
        return Response(ModerationSerializer(fresh(project), context={"request": request}).data)
