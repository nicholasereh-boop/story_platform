"""Takedown workflow. receive() records a complaint and tells the editors; hold() hides the article at once (quarantine, nothing is deleted);
uphold() withdraws it for good; dismiss() restores it to the review queue (never straight to public)."""
import re

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from ..models import NewsArticle, NewsTakedown
from . import articles

SLUG = re.compile(r"/news/(?:article/|articles/)?([a-z0-9][a-z0-9-]*)/?(?:[?#].*)?$")


class TakedownError(ValueError):
    pass


def find_article(ref):
    """The article a sender means, from a pasted link or a slug. Returns None when nothing matches (the complaint is still recorded)."""
    ref = (ref or "").strip()
    match = SLUG.search(ref)
    slug = match.group(1) if match else (ref if re.fullmatch(r"[a-z0-9][a-z0-9-]*", ref) else "")
    return NewsArticle.objects.filter(slug=slug).first() if slug else None


def receive(*, name, email, ref, claim, message):
    article = find_article(ref)
    with transaction.atomic():
        takedown = NewsTakedown.objects.create(article=article, article_ref=ref[:300], contact_name=name, contact_email=email, claim=claim, message=message)
    recipient = getattr(settings, "NEWS_TAKEDOWN_NOTIFY_EMAIL", "")
    if recipient:
        try:
            send_mail(f"News complaint #{takedown.pk}", f"{name} <{email}> reported: {ref}\n\n{message[:1500]}", None, [recipient], fail_silently=True)
        except Exception:
            pass  # the complaint is saved; a mail problem must not lose it or show an error to the sender
    return takedown


def _need(takedown, states, verb):
    if takedown.status not in states:
        raise TakedownError(f"A complaint that is {takedown.get_status_display().lower()} cannot be {verb}.")


@transaction.atomic
def hold(takedown, user):
    _need(takedown, (NewsTakedown.Status.OPEN,), "put on hold")
    if takedown.article is None:
        raise TakedownError("This complaint does not match an article, so there is nothing to put on hold.")
    articles.quarantine(takedown.article, f"takedown complaint #{takedown.pk}", user)
    articles.bump_cache()
    return _close(takedown, user, NewsTakedown.Status.ON_HOLD, "")


@transaction.atomic
def uphold(takedown, user, note):
    _need(takedown, (NewsTakedown.Status.OPEN, NewsTakedown.Status.ON_HOLD), "upheld")
    note = (note or "").strip()
    if not note:
        raise TakedownError("Write a short resolution note.")
    article = takedown.article
    if article is not None and article.status in (NewsArticle.Status.PUBLISHED, NewsArticle.Status.SCHEDULED, NewsArticle.Status.QUARANTINED):
        articles.withdraw(article, user, f"upheld complaint #{takedown.pk}: {note}")
    return _close(takedown, user, NewsTakedown.Status.UPHELD, note)


@transaction.atomic
def dismiss(takedown, user, note):
    _need(takedown, (NewsTakedown.Status.OPEN, NewsTakedown.Status.ON_HOLD), "dismissed")
    note = (note or "").strip()
    if not note:
        raise TakedownError("Write a short resolution note.")
    article = takedown.article
    if takedown.status == NewsTakedown.Status.ON_HOLD and article is not None and article.status == NewsArticle.Status.QUARANTINED:
        articles.restore(article, user)  # back to the review queue; an editor republishes after checking
    return _close(takedown, user, NewsTakedown.Status.DISMISSED, note)


def _close(takedown, user, status, note):
    takedown.status = status
    takedown.resolution_note = note[:300]
    takedown.handled_by = user
    takedown.handled_at = timezone.now()
    takedown.save(update_fields=["status", "resolution_note", "handled_by", "handled_at"])
    return takedown
