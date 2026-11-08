# """Who may download what. Called on EVERY download request; the browser's say-so is never part of the decision."""
from django.conf import settings

from ..models import SourceProject, SourcePurchase


def download_basis(user, package):
    """(basis, purchase): basis is "owner" | "staff" | "free" | "purchase", or None when `user` may NOT download `package`.

    * the seller always can (their own files);
    * staff can while a project is under review; a PUBLISHED backend must be paid for like anyone else's;
    * a free FRONTEND (price 0) of a PUBLISHED project needs a signed-in account; backend code is never free;
    * a paid package needs a verified purchase. Buyers keep access when a project is archived or sent back to review
      (they paid), but not when staff rejected it; nobody else ever reaches unpublished work.
    """
    if not (user and user.is_authenticated and user.is_active):
        return None, None
    project = package.project
    if not package.is_active:
        return None, None
    # Backend source code is never handed out as "free": it needs a verified payment (the rule can be switched off in settings).
    backend_is_paid_only = package.kind == "backend" and getattr(settings, "MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True)
    if project.owner_id == user.pk:
        return "owner", None  # a seller always has their own files
    if user.is_staff:
        # Moderators need the files while they REVIEW a project. Once a backend is published it must be paid for like anyone else's.
        if not (backend_is_paid_only and project.status == SourceProject.Status.PUBLISHED):
            return "staff", None
    price = project.price_for(package.kind)
    if price <= 0 and not backend_is_paid_only and project.status == SourceProject.Status.PUBLISHED:
        return "free", None
    if project.status == SourceProject.Status.REJECTED:
        return None, None
    purchase = SourcePurchase.objects.filter(buyer=user, package=package, status=SourcePurchase.Status.SUCCESS).order_by("-id").first()
    if purchase:
        return "purchase", purchase
    return None, None


def has_paid(user, package):
    if not (user and user.is_authenticated):
        return False
    return SourcePurchase.objects.filter(buyer=user, package=package, status=SourcePurchase.Status.SUCCESS).exists()






# the down code can be use in place of the up code 



"""Who may download what. Called on EVERY download request; the browser's say-so is never part of the decision."""
# from django.conf import settings

# from ..models import SourceProject, SourcePurchase


# def download_basis(user, package):
#     """(basis, purchase): basis is "owner" | "staff" | "free" | "purchase", or None when `user` may NOT download `package`.

#     * the seller always can; staff can (moderation);
#     * a free FRONTEND (price 0) of a PUBLISHED project needs a signed-in account; backend code is never free;
#     * a paid package needs a verified purchase. Buyers keep access when a project is archived or sent back to review
#       (they paid), but not when staff rejected it; nobody else ever reaches unpublished work.
#     """
#     if not (user and user.is_authenticated and user.is_active):
#         return None, None
#     project = package.project
#     if not package.is_active:
#         return None, None
#     if project.owner_id == user.pk:
#         return "owner", None
#     if user.is_staff:
#         return "staff", None
#     price = project.price_for(package.kind)
#     # Backend source code is never handed out as "free": it needs a verified payment (the rule can be switched off in settings).
#     backend_is_paid_only = package.kind == "backend" and getattr(settings, "MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True)
#     if price <= 0 and not backend_is_paid_only and project.status == SourceProject.Status.PUBLISHED:
#         return "free", None
#     if project.status == SourceProject.Status.REJECTED:
#         return None, None
#     purchase = SourcePurchase.objects.filter(buyer=user, package=package, status=SourcePurchase.Status.SUCCESS).order_by("-id").first()
#     if purchase:
#         return "purchase", purchase
#     return None, None


# def has_paid(user, package):
#     if not (user and user.is_authenticated):
#         return False
#     return SourcePurchase.objects.filter(buyer=user, package=package, status=SourcePurchase.Status.SUCCESS).exists()