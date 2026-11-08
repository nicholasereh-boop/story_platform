"""Input safety for comment text: cleaning and the v1 spam filter. Pure functions, easy to test.

Comments are PLAIN TEXT. Nothing here (or anywhere) interprets HTML or markdown; the frontend renders the body as
text, so a "<script>" typed by a reader is just characters on the screen.
"""
import re
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

MAX_BODY = 2000
MAX_LINKS = 2
DUPLICATE_WINDOW = timedelta(hours=1)
DELETED_PLACEHOLDER = "[This comment was deleted]"

_LINK_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def clean_body(raw):
    """Normalise a comment: unify newlines, drop control characters, trim, collapse long runs of blank lines.

    Returns the cleaned text, which is "" for whitespace-only input (the caller rejects that).
    """
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    # Remove control characters (category Cc) except newline and tab.
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch) != "Cc")
    text = re.sub(r"[ \t]+\n", "\n", text)  # trailing spaces make "blank" lines look non-blank
    text = re.sub(r"\n{4,}", "\n\n\n", text)  # at most 2 blank lines in a row
    return text.strip()


MAX_NAME = 60


def clean_name(raw):
    """A visitor's display name: one line, no control characters, collapsed spaces, at most 60 characters."""
    text = "".join(ch for ch in (raw or "") if unicodedata.category(ch) != "Cc" or ch in " ")
    return re.sub(r"\s+", " ", text).strip()[:MAX_NAME]


def count_links(text):
    return len(_LINK_RE.findall(text))


def blocked_word(text):
    """The first COMMENT_BLOCKED_WORDS entry found as a whole word (case-insensitive), or None."""
    for word in settings.COMMENT_BLOCKED_WORDS:
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE):
            return word
    return None


def spam_problem(text, user, exclude_comment_id=None, session_key=None):
    """Spam filter v1. Returns a clear message if the text must be rejected, else None.

    Rules: more than 2 links, a blocked word, or the same text by the same user within the last hour.
    """
    if count_links(text) > MAX_LINKS:
        return f"Comments can contain at most {MAX_LINKS} links."
    if blocked_word(text):
        return "Your comment contains a word that is not allowed here."
    from .models import Comment

    author = {"user": user} if user is not None else {"user": None, "session_key": session_key}
    duplicates = Comment.objects.filter(body=text, created_at__gte=timezone.now() - DUPLICATE_WINDOW, **author)
    if exclude_comment_id:
        duplicates = duplicates.exclude(pk=exclude_comment_id)
    if duplicates.exists():
        return "You already posted that comment. Please do not repeat yourself."
    return None
