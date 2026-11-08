"""News comments: input cleaning and the same spam rules as story comments (reusing their pure text helpers, not their data)."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.comments.text import MAX_BODY, MAX_LINKS, blocked_word, clean_body, count_links

from ..models import NewsComment

DUPLICATE_WINDOW = timedelta(hours=1)


class CommentProblem(ValueError):
    pass


def check_body(raw, user):
    """The cleaned text, or CommentProblem with a message a reader can act on."""
    text = clean_body(raw)
    if not text:
        raise CommentProblem("Please write something before posting.")
    if len(text) > MAX_BODY:
        raise CommentProblem(f"Comments can be at most {MAX_BODY} characters.")
    if count_links(text) > MAX_LINKS:
        raise CommentProblem(f"Comments can contain at most {MAX_LINKS} links.")
    if blocked_word(text):
        raise CommentProblem("Your comment contains a word that is not allowed here.")
    if NewsComment.objects.filter(user=user, body=text, created_at__gte=timezone.now() - DUPLICATE_WINDOW).exists():
        raise CommentProblem("You already posted that comment. Please do not repeat yourself.")
    return text


def create_comment(user, article, raw):
    text = check_body(raw, user)
    status = NewsComment.Status.PENDING if settings.NEWS_COMMENT_MODERATION else NewsComment.Status.APPROVED
    return NewsComment.objects.create(article=article, user=user, body=text, status=status)


def set_status(comment, status):
    comment.status = status
    comment.save(update_fields=["status", "updated_at"])
    return comment
