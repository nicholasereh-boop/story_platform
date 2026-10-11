"""Privacy rights: "download my data" and "delete my account" (which ANONYMISES the account).

Why anonymise instead of deleting rows: comments, likes and the story counters (like_count, comment_count) must stay
correct, and audit entries must keep making sense. So the person is erased from the data instead: e-mail replaced,
name and profile text removed, password made unusable, sessions ended, likes and reports removed, every comment moved to
the "deleted" status THROUGH comments.services.set_status (which keeps Story.comment_count right), and the account
deactivated. It cannot be undone.
"""
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.db import transaction

from apps.audit import service as audit
from apps.audit.models import AuditLog
from apps.comments import services as comment_services
from apps.comments.models import Comment, CommentReport
from apps.reactions.models import Like
from apps.reactions.services import unlike_story

from . import mfa, sessions
from .models import User
from .services import get_profile, is_email_verified

DELETED_NAME = "Deleted user"
DELETED_DOMAIN = "invalid.invalid"


def is_last_active_superuser(user):
    """True when `user` is the only active superuser (the account that must never be removed or demoted)."""
    return user.is_superuser and user.is_active and not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).exists()


def is_anonymised(user):
    return user.email.endswith("@" + DELETED_DOMAIN)


def export_data(user):
    """Everything the site holds about this person, as plain JSON-ready data. Never includes hashes, secrets or sessions."""
    profile = get_profile(user)
    comments = Comment.objects.filter(user=user).select_related("story").order_by("created_at", "id")
    likes = Like.objects.filter(user=user).select_related("story").order_by("created_at", "id")
    reports = CommentReport.objects.filter(user=user).order_by("created_at", "id")
    return {
        "account": {
            "id": user.pk,
            "email": user.email,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "email_verified": is_email_verified(user),
            "is_staff": user.is_staff,
            "sign_in_methods": ["password"] * bool(user.has_usable_password()) + [a.provider for a in SocialAccount.objects.filter(user=user)],
        },
        "profile": {"display_name": profile.display_name, "bio": profile.bio, "avatar_url": profile.avatar_url},
        "comments": [
            {
                "id": c.pk,
                "story": c.story.title,
                "story_slug": c.story.slug,
                "body": c.body,
                "status": c.status,
                "is_reply": c.parent_id is not None,
                "created_at": c.created_at,
                "edited_at": c.edited_at,
            }
            for c in comments
        ],
        "likes": [{"story": l.story.title, "story_slug": l.story.slug, "created_at": l.created_at} for l in likes],
        "reports_made": [{"comment_id": r.comment_id, "reason": r.reason, "created_at": r.created_at} for r in reports],
        "security": {"two_step_verification_enabled": mfa.is_enabled(user)},
        "consent": {
            "stored_on_server": False,
            "note": "Your analytics choice is kept only in your own browser (localStorage); the server holds no record of it.",
        },
    }


@transaction.atomic
def anonymise(request, user):
    """Erase the person from the account. The caller has already checked the password or e-mail confirmation."""
    if is_last_active_superuser(user):
        raise ValueError("last_superuser")
    user_id = user.pk
    # 1. Comments: through set_status so Story.comment_count stays correct.
    for comment in Comment.objects.filter(user=user).exclude(status=Comment.Status.DELETED).order_by("-parent_id", "id"):
        comment_services.set_status(comment, Comment.Status.DELETED)
    # 2. Likes (through unlike_story, so like_count stays correct) and reports.
    for like in list(Like.objects.filter(user=user).select_related("story")):
        unlike_story(user, like.story)
    CommentReport.objects.filter(user=user).delete()
    # 3. Profile text and picture.
    profile = get_profile(user)
    profile.display_name, profile.bio, profile.avatar_url = DELETED_NAME, "", ""
    profile.save()
    # 4. Sign-in methods and two-step verification.
    EmailAddress.objects.filter(user=user).delete()
    SocialAccount.objects.filter(user=user).delete()
    mfa.disable(user)
    # 5. Sessions, then the account itself.
    sessions.revoke_all(user)
    user.email = f"deleted-{user_id}@{DELETED_DOMAIN}"
    user.set_unusable_password()
    user.is_active = False
    user.is_staff = False
    user.is_superuser = False
    user.save()
    # 6. Old audit entries keep their meaning but lose the person's name.
    AuditLog.objects.filter(actor=user).redact_actor_labels(DELETED_NAME)
    audit.log(request, "user.anonymised", user, actor=user, self_service=True)
    return user
