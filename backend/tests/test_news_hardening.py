"""News Phase 6: cross-cutting checks: cache invalidation, XSS end to end, and everything switched off."""
import pytest

from apps.news.services import articles

from .marketplace_helpers import client_for
from .news_helpers import ADMIN, API, make_article, make_live_article, make_record, make_source

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def public(settings):
    settings.NEWS_PUBLIC_ENABLED = True
    settings.NEWS_PUBLIC_CACHE_SECONDS = 300  # long on purpose: only the version bump may make a list fresh


@pytest.fixture
def setup(staff):
    source = make_source()
    make_record(source)
    return source


def slugs(client, path="articles/"):
    return [a["slug"] for a in client.get(API + path).json()["data"]]


def test_a_cached_list_is_refreshed_the_moment_an_article_is_published_or_taken_down(client, staff, setup):
    assert slugs(client) == []
    assert slugs(client) == []  # now served from the cache
    live = make_live_article(setup, staff)
    assert slugs(client) == [live.slug]
    articles.withdraw(live, staff, "mistake")
    assert slugs(client) == []


def test_quarantine_and_restore_refresh_the_cache_too(client, staff, setup):
    live = make_live_article(setup, staff)
    assert slugs(client) == [live.slug]
    articles.quarantine(live, "complaint", staff)
    assert slugs(client) == []
    assert client.get(API + f"articles/{live.slug}/").status_code == 404


def test_revoking_the_licence_removes_the_article_from_every_public_list(client, staff, setup):
    from apps.news.services import rights

    live = make_live_article(setup, staff)
    assert slugs(client) == [live.slug] and slugs(client, "breaking/") == [] and slugs(client, "featured/") == []
    record = live.rights_record
    rights.revoke_record(record, staff, "agreement ended")
    assert slugs(client) == []
    assert client.get(API + f"articles/{live.slug}/").status_code == 404


def test_hostile_markup_never_reaches_readers(client, staff, setup):
    hostile = ('<p onclick="x()">Hi</p><script>alert(1)</script><img src=x onerror=alert(2)><iframe src="https://evil.example"></iframe>'
               '<a href="javascript:alert(3)">click</a><style>body{display:none}</style><svg onload=alert(4)></svg>')
    article = make_article(setup, staff, data={"body": hostile})
    articles.submit(article, staff)
    articles.publish(article, staff)
    body = client.get(API + f"articles/{article.slug}/").json()["data"]["body"].lower()
    for bad in ("<script", "onerror", "onclick", "onload", "<iframe", "javascript:", "<style", "<svg", "<img"):
        assert bad not in body
    assert "hi" in body


def test_the_whole_section_answers_404_when_news_is_switched_off(client, staff, settings, setup):
    live = make_live_article(setup, staff)
    settings.NEWS_ENABLED = False
    for path in ("config/", "articles/", f"articles/{live.slug}/", "categories/", "featured/", "breaking/"):
        assert client.get(API + path).status_code == 404, path
    assert client_for(staff).get(ADMIN + "articles/").status_code == 404
    assert client_for(staff).get(ADMIN + "monitoring/").status_code == 404


def test_public_endpoints_never_accept_writes_from_visitors(client, staff, setup):
    live = make_live_article(setup, staff)
    for method in (client.post, client.put, client.patch, client.delete):
        assert method(API + f"articles/{live.slug}/", {}, format="json").status_code in (401, 403, 405)
        assert method(API + "articles/", {}, format="json").status_code in (401, 403, 405)