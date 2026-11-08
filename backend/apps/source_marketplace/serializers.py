from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.utils import display_name
from apps.core.text import clean_plain_text, strip_unsafe_chars
from apps.stories.content import youtube_id

from .models import ProjectScreenshot, SourceProject, SourcePurchase, Technology
from .services import access, projects

MAX_TEXT = 20000


def site_currency():
    return getattr(settings, "MARKETPLACE_CURRENCY", "USD")


def backend_price_message():
    return f"Backend source code is sold, not given away. Set a price above 0 ({site_currency()})."


class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ["name", "slug"]


class ScreenshotSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProjectScreenshot
        fields = ["id", "url", "width", "height", "alt_text", "position"]

    def get_url(self, obj):
        return obj.file.url if obj.file else None


def backend_requires_payment():
    return bool(getattr(settings, "MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True))


def _offer(project, package):
    price = project.price_for(package.kind)
    free = price <= 0 and not (package.kind == "backend" and backend_requires_payment())  # backend code is never free
    return {
        "package_id": package.pk,
        "kind": package.kind,
        "version": package.version,
        "size_bytes": package.size_bytes,
        "file_count": package.file_count,
        "source": package.source,
        "price": f"{price:.2f}",
        "currency": project.currency,
        "is_free": free,
        "updated_at": package.updated_at,
    }


def active_packages(project):
    # Uses the prefetch cache when the view loaded packages already.
    return sorted((p for p in project.packages.all() if p.is_active), key=lambda p: p.kind)


class ProjectCardSerializer(serializers.ModelSerializer):
    """What the marketplace grid needs. Never includes private fields or package files."""

    seller = serializers.SerializerMethodField()
    technologies = TechnologySerializer(many=True, read_only=True)
    cover = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()

    class Meta:
        model = SourceProject
        fields = ["id", "slug", "title", "summary", "seller", "technologies", "cover", "offers", "has_video", "currency", "published_at"]

    def get_seller(self, obj):
        return display_name(obj.owner) if obj.owner else "Former member"

    def get_cover(self, obj):
        shots = list(obj.screenshots.all())
        if not shots:
            return None
        s = shots[0]
        return {"url": s.file.url, "width": s.width, "height": s.height, "alt_text": s.alt_text}

    def get_offers(self, obj):
        return [_offer(obj, p) for p in active_packages(obj)]

    def get_has_video(self, obj):
        return bool(obj.youtube_id or obj.frontend_video_id or obj.backend_video_id)


class ProjectDetailSerializer(ProjectCardSerializer):
    """The public project page. `viewer` fields say what the signed-in reader may do; the server still re-checks on download."""

    screenshots = ScreenshotSerializer(many=True, read_only=True)
    viewer = serializers.SerializerMethodField()

    class Meta(ProjectCardSerializer.Meta):
        fields = ProjectCardSerializer.Meta.fields + [
            "description", "notes", "youtube_id", "frontend_video_id", "backend_video_id", "screenshots", "status", "viewer",
        ]

    def get_viewer(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_owner = bool(user and user.is_authenticated and obj.owner_id == user.pk)
        can = {}
        for package in active_packages(obj):
            basis, _ = access.download_basis(user, package)
            can[package.kind] = {"can_download": bool(basis), "basis": basis, "purchased": access.has_paid(user, package)}
        return {"is_owner": is_owner, "packages": can}


class OwnerProjectSerializer(ProjectDetailSerializer):
    """The seller's own view of a project: includes status, review note, prices and what the upload check did."""

    packages = serializers.SerializerMethodField()

    class Meta(ProjectDetailSerializer.Meta):
        fields = ProjectDetailSerializer.Meta.fields + [
            "review_note", "frontend_price", "backend_price", "rights_confirmed_at", "packages", "created_at", "updated_at",
        ]

    def get_packages(self, obj):
        return [
            {**_offer(obj, p), "scan_report": p.scan_report, "source_ref": p.source_ref, "sha256": p.sha256}
            for p in active_packages(obj)
        ]


class ProjectWriteSerializer(serializers.Serializer):
    """Create / update. Status, owner, currency and review fields can NOT be set here."""

    title = serializers.CharField(max_length=160)
    slug = serializers.CharField(max_length=90, required=False, allow_blank=True)
    summary = serializers.CharField(max_length=300, required=False, allow_blank=True)
    description = serializers.CharField(max_length=MAX_TEXT, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=MAX_TEXT, required=False, allow_blank=True)
    technologies = serializers.ListField(child=serializers.CharField(max_length=60), required=False, max_length=30)
    youtube_url = serializers.CharField(max_length=300, required=False, allow_blank=True)  # video about BOTH parts (optional)
    frontend_video_url = serializers.CharField(max_length=300, required=False, allow_blank=True)  # video about the frontend (optional)
    backend_video_url = serializers.CharField(max_length=300, required=False, allow_blank=True)  # video about the backend (optional)
    frontend_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal("0"))
    backend_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal("0"))
    rights_confirmed = serializers.BooleanField(required=False)

    # Fields whose change on a published project sends it back to review (the page buyers see changed).
    CONTENT_FIELDS = {"title", "summary", "description", "notes", "youtube_url", "frontend_video_url", "backend_video_url", "technologies"}

    def validate_title(self, value):
        return clean_plain_text(value, max_length=160, allow_blank=False)

    def validate_summary(self, value):
        return clean_plain_text(value, max_length=300)

    # Descriptions and notes are plain text and are always rendered as text (never as HTML), so code such as <div> is fine.
    def validate_description(self, value):
        return strip_unsafe_chars(value, multiline=True)

    def validate_notes(self, value):
        return strip_unsafe_chars(value, multiline=True)

    def validate_slug(self, value):
        value = value.strip().lower()
        if value and not projects.valid_custom_slug(value):
            raise serializers.ValidationError("Use lowercase letters, numbers and single dashes, with at least one letter.")
        return value

    def validate_technologies(self, values):
        names, error = projects.clean_technologies(values)
        if error:
            raise serializers.ValidationError(error)
        return names

    @staticmethod
    def _video_id(value):
        """Empty is fine (every video is optional); anything else must be a real YouTube link. Only the 11-character id is kept."""
        value = value.strip()
        if not value:
            return ""
        vid = youtube_id(value)
        if not vid:
            raise serializers.ValidationError("Enter a YouTube link (https://www.youtube.com/watch?v=... or https://youtu.be/...).")
        return vid

    def validate_youtube_url(self, value):
        return self._video_id(value)

    def validate_frontend_video_url(self, value):
        return self._video_id(value)

    def validate_backend_video_url(self, value):
        return self._video_id(value)

    def validate(self, attrs):
        cap = Decimal(str(settings.MARKETPLACE_MAX_PRICE))
        for field in ("frontend_price", "backend_price"):
            if field in attrs and attrs[field] > cap:
                raise serializers.ValidationError({field: [f"The highest price allowed is {cap:,.0f} {site_currency()}."]})
        if getattr(settings, "MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True) and "backend_price" in attrs and attrs["backend_price"] <= 0:
            if self.instance is not None and self.instance.packages.filter(kind="backend", is_active=True).exists():
                raise serializers.ValidationError({"backend_price": [backend_price_message()]})
        slug = attrs.get("slug")
        if slug:
            qs = SourceProject.objects.filter(slug=slug)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"slug": ["That address is already taken."]})
            if self.instance is not None and self.instance.status == SourceProject.Status.PUBLISHED and slug != self.instance.slug:
                raise serializers.ValidationError({"slug": ["The address of a published project cannot change."]})
        return attrs

    def save(self, owner=None, instance=None):
        data = dict(self.validated_data)
        names = data.pop("technologies", None)
        rights = data.pop("rights_confirmed", None)
        vid = data.pop("youtube_url", None)
        frontend_vid = data.pop("frontend_video_url", None)
        backend_vid = data.pop("backend_video_url", None)
        slug = data.pop("slug", "")
        changed_content = set(self.initial_data.keys() if hasattr(self.initial_data, "keys") else []) & self.CONTENT_FIELDS
        if instance is None:
            instance = SourceProject(owner=owner, currency=site_currency())
            instance.slug = slug or projects.make_slug(data.get("title", "project"))
        elif slug and instance.status != SourceProject.Status.PUBLISHED:
            instance.slug = slug
        for key, value in data.items():
            setattr(instance, key, value)
        if vid is not None:
            instance.youtube_id = vid
        if frontend_vid is not None:
            instance.frontend_video_id = frontend_vid
        if backend_vid is not None:
            instance.backend_video_id = backend_vid
        if rights is True and not instance.rights_confirmed_at:
            instance.rights_confirmed_at = timezone.now()
        elif rights is False:
            instance.rights_confirmed_at = None
        sent_back = False
        if (
            instance.pk
            and changed_content
            and instance.status == SourceProject.Status.PUBLISHED
            and settings.MARKETPLACE_REQUIRE_REVIEW
            and not (owner and owner.is_staff)
        ):
            instance.status = SourceProject.Status.PENDING
            sent_back = True
        instance.save()
        if names is not None:
            projects.set_technologies(instance, names)
        instance._sent_back_to_review = sent_back
        return instance


class PurchaseSerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    kind = serializers.CharField(source="package.kind")
    package_id = serializers.IntegerField(source="package.pk")
    version = serializers.CharField(source="package.version")
    can_download = serializers.SerializerMethodField()

    class Meta:
        model = SourcePurchase
        fields = [
            "id", "reference", "status", "amount", "currency", "list_price", "list_currency", "created_at", "verified_at",
            "project", "kind", "package_id", "version", "can_download",
        ]
    def get_project(self, obj):
        p = obj.package.project
        return {"id": p.pk, "slug": p.slug, "title": p.title}

    def get_can_download(self, obj):
        return (
            obj.status == SourcePurchase.Status.SUCCESS
            and obj.package.is_active
            and obj.package.project.status != SourceProject.Status.REJECTED
        )


class ModerationSerializer(ProjectCardSerializer):
    """Staff review queue: what a moderator needs to decide, including the upload check's report."""

    owner_email = serializers.SerializerMethodField()
    packages = serializers.SerializerMethodField()

    class Meta(ProjectCardSerializer.Meta):
        fields = ProjectCardSerializer.Meta.fields + ["status", "review_note", "owner_email", "rights_confirmed_at", "description", "notes", "youtube_id", "frontend_video_id", "backend_video_id", "packages", "updated_at"]

    def get_owner_email(self, obj):
        return obj.owner.email if obj.owner else ""

    def get_packages(self, obj):
        return [{**_offer(obj, p), "scan_report": p.scan_report, "source_ref": p.source_ref} for p in active_packages(obj)]


def check_package_kind(value):
    if value not in ("frontend", "backend"):
        raise serializers.ValidationError({"kind": ["Choose frontend or backend."]})
    return value