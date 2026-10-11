"""Public, read-only API: visibility, filters, search, related, counts, privacy, throttling, query counts."""
import json
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.stories.models import Category, Story, Tag

BASE = "/api/v1/"
PRIVATE_KEYS = {
    "status", "scheduled_at", "created_by", "updated_by", "view_count",  # like/comment counts became public in Phase 8
    "search_text", "revisions", "email", "created_at",
}


def doc(text):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def make(title, status="published", published_ago_days=1, cats=(), tags=(), user=None, text=None, **extra):
    """Create a story directly in the database in any state."""
    now = timezone.now()
    story = Story.objects.create(
        title=title, content_json=doc(text or f"Body of {title}"), status=status, created_by=user, **extra
    )
    if status == "published":
        story.published_at = now - timedelta(days=published_ago_days)
    if status == "scheduled":
        story.scheduled_at = now + timedelta(days=2)
    story.save()
    story.categories.set(cats)
    story.tags.set(tags)
    return story


def get(client, path, **params):
    return client.get(BASE + path, params)


def slugs(response):
    return [s["slug"] for s in response.json()["data"]]


def all_keys(value, found=None):
    """Every dict key anywhere in a JSON response."""
    found = set() if found is None else found
    if isinstance(value, dict):
        for k, v in value.items():
            found.add(k)
            all_keys(v, found)
    elif isinstance(value, list):
        for v in value:
            all_keys(v, found)
    return found


@pytest.fixture
def taxonomy(db):
    return {
        "news": Category.objects.create(name="News"),
        "life": Category.objects.create(name="Life"),
        "empty": Category.objects.create(name="Empty"),
        "python": Tag.objects.create(name="Python"),
        "django": Tag.objects.create(name="Django"),
        "unused": Tag.objects.create(name="Unused"),
    }


# ---- visibility matrix ---------------------------------------------------------
def test_only_public_stories_are_visible_everywhere(client, db, taxonomy):
    news, python = taxonomy["news"], taxonomy["python"]
    visible = make("Visible", cats=[news], tags=[python])
    hidden = {
        "draft": make("Hidden draft", status="draft", cats=[news], tags=[python]),
        "scheduled": make("Hidden scheduled", status="scheduled", cats=[news], tags=[python]),
        "archived": make("Hidden archived", status="archived", cats=[news], tags=[python]),
        "future": make("Hidden future", cats=[news], tags=[python], published_ago_days=-3),
    }
    assert slugs(get(client, "stories/")) == [visible.slug]
    assert slugs(get(client, "stories/", category="news")) == [visible.slug]
    assert slugs(get(client, "stories/", tag="python")) == [visible.slug]
    assert slugs(get(client, "categories/news/stories/")) == [visible.slug]
    assert slugs(get(client, "search/", q="Hidden")) == []
    assert [r["slug"] for r in get(client, "sitemap-data/").json()["data"]] == [visible.slug]
    for story in hidden.values():
        assert get(client, f"stories/{story.slug}/").status_code == 404  # 404, never 403
        assert get(client, f"stories/{story.slug}/related/").status_code == 404
    assert get(client, f"stories/{visible.slug}/").status_code == 200


def test_unknown_slug_is_404(client, db):
    assert get(client, "stories/nope/").status_code == 404
    assert get(client, "categories/nope/stories/").status_code == 404


def test_due_scheduled_story_appears_without_celery(client, db):
    story = make("Due", status="scheduled")
    Story.objects.filter(pk=story.pk).update(scheduled_at=timezone.now() - timedelta(minutes=1))
    assert slugs(get(client, "stories/")) == [story.slug]
    assert get(client, f"stories/{story.slug}/").status_code == 200


def test_requires_no_login_and_is_get_only(client, db):
    story = make("Open")
    assert get(client, "stories/").status_code == 200
    assert client.post(BASE + "stories/", {}, format="json").status_code == 405
    assert client.delete(BASE + f"stories/{story.slug}/").status_code == 405
    assert client.patch(BASE + f"stories/{story.slug}/", {}, format="json").status_code == 405


def test_list_is_newest_first_and_paginated(client, db):
    for i in range(14):
        make(f"Story {i}", published_ago_days=20 - i)  # higher i = newer
    r = get(client, "stories/").json()
    assert len(r["data"]) == 12
    assert r["data"][0]["title"] == "Story 13"
    assert r["pagination"]["total_pages"] == 2 and r["pagination"]["count"] == 14
    assert len(get(client, "stories/", page=2).json()["data"]) == 2


# ---- filters -------------------------------------------------------------------
def test_filters_featured_category_tag(client, db, taxonomy):
    a = make("A", cats=[taxonomy["news"]], tags=[taxonomy["python"]], is_featured=True)
    b = make("B", cats=[taxonomy["life"]], tags=[taxonomy["django"]])
    assert slugs(get(client, "stories/", featured="1")) == [a.slug]
    assert slugs(get(client, "stories/", category="life")) == [b.slug]
    assert slugs(get(client, "stories/", tag="python")) == [a.slug]
    assert slugs(get(client, "stories/", category="news", tag="django")) == []
    assert slugs(get(client, "stories/", category="does-not-exist")) == []


# ---- categories & tags: only public, counts only count public ----------------------
def test_category_and_tag_lists_count_only_public_stories(client, db, taxonomy):
    news, life, python = taxonomy["news"], taxonomy["life"], taxonomy["python"]
    make("P1", cats=[news], tags=[python])
    make("P2", cats=[news], tags=[python])
    make("D1", status="draft", cats=[news, life], tags=[python, taxonomy["django"]])
    make("F1", cats=[life], published_ago_days=-1)  # future-dated
    cats = {c["slug"]: c for c in get(client, "categories/").json()["data"]}
    assert set(cats) == {"news"}  # life/empty have no PUBLIC story
    assert cats["news"]["story_count"] == 2
    tags = {t["slug"]: t for t in get(client, "tags/").json()["data"]}
    assert set(tags) == {"python"} and tags["python"]["story_count"] == 2


def test_a_category_with_no_public_stories_is_404(client, db, taxonomy):
    make("Draft only", status="draft", cats=[taxonomy["life"]])
    assert get(client, "categories/life/stories/").status_code == 404
    assert get(client, "categories/empty/stories/").status_code == 404


def test_story_in_two_categories_is_counted_once(client, db, taxonomy):
    make("Both", cats=[taxonomy["news"], taxonomy["life"]], tags=[taxonomy["python"], taxonomy["django"]])
    cats = {c["slug"]: c["story_count"] for c in get(client, "categories/").json()["data"]}
    assert cats == {"life": 1, "news": 1}
    assert len(get(client, "stories/").json()["data"]) == 1


# ---- search --------------------------------------------------------------------
def test_search_matches_title_excerpt_and_body_case_insensitively(client, db):
    by_title = make("Lighthouse keeper")
    by_excerpt = make("Other one", excerpt="A tale about a LIGHTHOUSE at night")
    by_body = make("Third", text="Deep in the body we find a lighthouse lamp.")
    make("Unrelated", text="Nothing here")
    assert set(slugs(get(client, "search/", q="lighthouse"))) == {by_title.slug, by_excerpt.slug, by_body.slug}


def test_search_no_match_and_pagination_shape(client, db):
    make("Something")
    r = get(client, "search/", q="zzzzzz").json()
    assert r["data"] == [] and r["pagination"]["count"] == 0


@pytest.mark.parametrize("q", ["", "a", " a ", "x" * 101])
def test_search_rejects_bad_length(client, db, q):
    r = get(client, "search/", q=q)
    assert r.status_code == 400
    assert "2 to 100" in r.json()["message"]


def test_search_without_q_is_400_and_100_chars_is_ok(client, db):
    assert client.get(BASE + "search/").status_code == 400
    assert get(client, "search/", q="y" * 100).status_code == 200


# ---- related -------------------------------------------------------------------
def test_related_is_ranked_by_shared_terms_then_newest_and_excludes_self(client, db, taxonomy):
    news, life, python, django = taxonomy["news"], taxonomy["life"], taxonomy["python"], taxonomy["django"]
    base = make("Base", cats=[news], tags=[python, django], published_ago_days=10)
    three = make("Three shared", cats=[news], tags=[python, django], published_ago_days=9)
    two_new = make("Two shared newer", cats=[news], tags=[python], published_ago_days=2)
    two_old = make("Two shared older", cats=[news], tags=[django], published_ago_days=5)
    one = make("One shared", cats=[life], tags=[python], published_ago_days=1)
    make("No overlap", cats=[life], tags=[taxonomy["unused"]])
    make("Draft overlap", status="draft", cats=[news], tags=[python, django])
    order = slugs(get(client, f"stories/{base.slug}/related/"))
    assert order == [three.slug, two_new.slug, two_old.slug, one.slug]
    assert base.slug not in order


def test_related_is_capped_at_four_and_empty_without_terms(client, db, taxonomy):
    base = make("Base", cats=[taxonomy["news"]])
    for i in range(6):
        make(f"R{i}", cats=[taxonomy["news"]])
    assert len(slugs(get(client, f"stories/{base.slug}/related/"))) == 4
    lonely = make("Lonely")
    assert slugs(get(client, f"stories/{lonely.slug}/related/")) == []


# ---- shape and privacy -----------------------------------------------------------
def test_list_item_shape(client, db, taxonomy, staff):
    make("Shape", cats=[taxonomy["news"]], tags=[taxonomy["python"]], user=staff, is_featured=True)
    item = get(client, "stories/").json()["data"][0]
    assert set(item) == {
        "id", "title", "slug", "excerpt", "cover", "categories", "tags", "author", "published_at", "reading_minutes", "is_featured",
        "like_count", "comment_count",
    }
    assert item["categories"] == [{"name": "News", "slug": "news"}]
    assert item["tags"] == [{"name": "Python", "slug": "python"}]
    assert item["cover"] is None
    assert item["author"] == "staff"  # display name only, never the email
    assert item["reading_minutes"] == 1


def test_detail_shape_and_seo_fallbacks(client, db):
    story = make("Plain title", excerpt="Short summary")
    data = get(client, f"stories/{story.slug}/").json()["data"]
    assert data["seo_title"] == "Plain title"
    assert data["seo_description"] == "Short summary"
    assert data["canonical_path"] == f"/stories/{story.slug}"
    assert data["content_json"]["type"] == "doc"
    assert "updated_at" in data
    custom = make("Another", seo_title="Custom SEO", seo_description="Custom description")
    data = get(client, f"stories/{custom.slug}/").json()["data"]
    assert (data["seo_title"], data["seo_description"]) == ("Custom SEO", "Custom description")


def test_reading_minutes_uses_200_words_per_minute(client, db):
    story = make("Long", text="word " * 450)
    assert get(client, f"stories/{story.slug}/").json()["data"]["reading_minutes"] == 3
    assert get(client, "stories/").json()["data"][0]["reading_minutes"] == 3


@pytest.fixture
def asset(db):
    from apps.media.models import MediaAsset

    return MediaAsset.objects.create(
        file="uploads/2026/01/lighthouse.jpg", mime_type="image/jpeg", width=800, height=600, size_bytes=1234,
        alt_text="Lighthouse at dusk",
    )


def test_cover_has_no_internal_id(client, asset):
    make("With cover", cover_image=asset)
    cover = get(client, "stories/").json()["data"][0]["cover"]
    assert set(cover) == {"url", "alt_text", "width", "height"}
    assert cover["alt_text"] == "Lighthouse at dusk" and cover["width"] == 800 and cover["url"].endswith("lighthouse.jpg")


def test_detail_resolves_image_nodes(client, asset):
    story = make("Img")
    story.content_json = {
        "type": "doc",
        "content": [{"type": "image", "attrs": {"assetId": asset.pk, "alt": "A", "caption": "", "align": "center", "size": "full"}}],
    }
    story.save()
    node = get(client, f"stories/{story.slug}/").json()["data"]["content_json"]["content"][0]
    assert node["attrs"]["src"].endswith("lighthouse.jpg") and node["attrs"]["width"] == 800 and node["attrs"]["height"] == 600


def test_no_private_fields_in_any_response(client, db, taxonomy, staff):
    story = make("Privacy", cats=[taxonomy["news"]], tags=[taxonomy["python"]], user=staff, view_count=7, like_count=3, comment_count=2)
    paths = [
        "stories/", f"stories/{story.slug}/", f"stories/{story.slug}/related/", "categories/",
        "categories/news/stories/", "tags/", "search/?q=Privacy", "sitemap-data/",
    ]
    for path in paths:
        r = client.get(BASE + path)
        assert r.status_code == 200, path
        leaked = all_keys(r.json()["data"]) & PRIVATE_KEYS
        assert not leaked, (path, leaked)
        raw = json.dumps(r.json())
        assert staff.email not in raw, path


# ---- sitemap data ---------------------------------------------------------------
def test_sitemap_data_shape_and_cache(client, db):
    first = make("First")
    data = get(client, "sitemap-data/").json()["data"]
    assert data == [{"slug": first.slug, "updated_at": data[0]["updated_at"]}]
    make("Second")
    assert len(get(client, "sitemap-data/").json()["data"]) == 1  # served from the 5-minute cache
    from django.core.cache import cache

    cache.clear()
    assert len(get(client, "sitemap-data/").json()["data"]) == 2


# ---- throttling ------------------------------------------------------------------
def test_public_read_scope_is_configured(settings):
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_read"] == "120/min"
    from apps.stories import public_views as pv

    for name in ("PublicStoryListView", "PublicStoryDetailView", "PublicRelatedStoriesView", "PublicCategoryListView",
                 "PublicCategoryStoriesView", "PublicTagListView", "PublicSearchView", "PublicSitemapDataView"):
        view = getattr(pv, name)
        assert view.throttle_scope == "public_read"
        assert view.throttle_classes == [ScopedRateThrottle]
        assert view.authentication_classes == []


def test_public_reads_are_limited_per_ip(client, db, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "public_read", "3/min")
    assert [get(client, "stories/").status_code for _ in range(4)] == [200, 200, 200, 429]
    other = APIClient(REMOTE_ADDR="10.9.9.9")
    assert get(other, "stories/").status_code == 200  # another visitor is not affected


def test_anonymous_default_hourly_limit_does_not_apply_to_public_reads(client, db):
    # The site-wide anon limit is 100/hour; a busy public site must not hit it.
    assert all(get(client, "stories/").status_code == 200 for _ in range(105))


# ---- query counts ------------------------------------------------------------------
def _queries(client, path):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(BASE + path).status_code == 200
    return len(ctx)


def test_list_query_count_is_fixed(client, db, taxonomy, staff):
    for i in range(2):
        make(f"Small {i}", cats=[taxonomy["news"]], tags=[taxonomy["python"]], user=staff)
    small = _queries(client, "stories/")
    for i in range(10):
        make(f"Big {i}", cats=[taxonomy["news"], taxonomy["life"]], tags=[taxonomy["python"], taxonomy["django"]], user=staff)
    assert _queries(client, "stories/") == small
    assert small <= 6
    assert _queries(client, "search/?q=Big") <= 6
    assert _queries(client, "categories/news/stories/") <= 7
