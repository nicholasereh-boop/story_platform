"""Helpers for the News tests: ready-made sources and rights records."""
from datetime import timedelta

from django.utils import timezone

from apps.news.models import NewsRightsRecord, NewsSource

API = "/api/v1/news/"
ADMIN = API + "admin/"


def make_source(slug="daily-example", **overrides):
    values = {"name": "Daily Example", "source_type": "licensed", "terms_url": "https://example.com/terms", "allows_full_text": True,
              "allows_commercial_use": True, "approval_state": "approved", "is_active": True}
    values.update(overrides)
    return NewsSource.objects.create(slug=slug, **values)


def make_record(source, **overrides):
    values = {"title": "Syndication 2026", "licence": "Syndication agreement", "basis": "written_permission", "allows_full_text": True,
              "allows_commercial_use": True, "allows_modification": True, "status": "approved", "evidence_note": "Signed PDF in the legal drive",
              "effective_from": timezone.now() - timedelta(days=1)}
    values.update(overrides)
    return NewsRightsRecord.objects.create(source=source, **values)



def make_article(source, user=None, **overrides):
    """A DRAFT created through the real service (so hashes, slug, attribution and revision exist)."""
    from apps.news.services import articles

    data = {"title": "Council approves new bridge", "standfirst": "Work starts in spring.", "body": "<p>The council voted on Tuesday.</p>",
            "author_name": "Ada Obi", "original_url": "https://example.com/original"}
    data.update(overrides.pop("data", {}))
    return articles.create_article(user, source, data, **overrides)


def make_live_article(source, user, **overrides):
    """A published article (gate passed)."""
    from apps.news.services import articles

    article = make_article(source, user, **overrides)
    articles.submit(article, user)
    return articles.publish(article, user)