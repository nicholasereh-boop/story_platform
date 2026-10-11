from datetime import timedelta

import pytest
from django.utils import timezone

from apps.stories.models import Category, Story, StoryRevision, Tag
from apps.stories.services import create_revision, publish_due

URL = "/api/v1/admin/stories/"


def doc(text):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


DOC_A = doc("Hello world, this is the first version of the story.")
DOC_B = doc("Second version with different words.")


def create(client, title="My Story", **extra):
    r = client.post(URL, {"title": title, "content_json": DOC_A, **extra}, format="json")
    assert r.status_code == 201, r.content
    return r.json()["data"]


def revisions(story_id):
    return StoryRevision.objects.filter(story_id=story_id).count()


# ---- permissions ---------------------------------------------------------------
def test_anonymous_is_denied(client, db):
    for method, url in [("get", URL), ("post", URL), ("get", URL + "1/"), ("post", URL + "1/publish/")]:
        assert getattr(client, method)(url).status_code in (401, 403)


def test_normal_user_is_denied_everywhere(client, user, staff_client):
    sid = create(staff_client)["id"]
    client.force_authenticate(user)
    assert client.get(URL).status_code == 403
    assert client.post(URL, {"title": "x"}, format="json").status_code == 403
    assert client.get(f"{URL}{sid}/").status_code == 403
    assert client.patch(f"{URL}{sid}/", {"title": "x"}, format="json").status_code == 403
    assert client.delete(f"{URL}{sid}/").status_code == 403
    assert client.post(f"{URL}{sid}/publish/").status_code == 403
    assert client.get(f"{URL}{sid}/revisions/").status_code == 403


def test_staff_can_list(staff_client, db):
    r = staff_client.get(URL)
    assert r.status_code == 200
    assert r.json()["pagination"]["page_size"] == 12


# ---- create ----------------------------------------------------------------------
def test_create_is_always_a_draft_and_ignores_client_controlled_fields(staff_client, staff):
    data = create(
        staff_client, status="published", published_at="2020-01-01T00:00:00Z", scheduled_at="2030-01-01T00:00:00Z",
        view_count=99, like_count=99, comment_count=99,
    )
    assert data["status"] == "draft"
    assert data["published_at"] is None and data["scheduled_at"] is None
    assert (data["view_count"], data["like_count"], data["comment_count"]) == (0, 0, 0)
    story = Story.objects.get(pk=data["id"])
    assert story.created_by == staff and story.updated_by == staff
    assert revisions(story.pk) == 1


def test_create_without_content_gets_an_empty_document(staff_client):
    r = staff_client.post(URL, {"title": "Blank"}, format="json")
    assert r.status_code == 201
    assert r.json()["data"]["content_json"]["type"] == "doc"


def test_slug_is_generated_and_deduplicated(staff_client):
    assert create(staff_client)["slug"] == "my-story"
    assert create(staff_client)["slug"] == "my-story-2"
    assert create(staff_client)["slug"] == "my-story-3"


def test_slug_never_empty(staff_client):
    assert create(staff_client, title="???")["slug"] == "story"


def test_custom_slug_and_duplicates(staff_client):
    assert create(staff_client, slug="custom-one")["slug"] == "custom-one"
    r = staff_client.post(URL, {"title": "Other", "slug": "custom-one", "content_json": DOC_A}, format="json")
    assert r.status_code == 400 and "slug" in r.json()["errors"]
    for bad in ["Bad Slug!", "UPPER", "-lead", "trail-", "dou--ble"]:
        r = staff_client.post(URL, {"title": "Other", "slug": bad}, format="json")
        assert r.status_code == 400, bad


def test_excerpt_is_filled_from_content_when_blank(staff_client):
    data = create(staff_client)
    assert data["excerpt"].startswith("Hello world")
    custom = create(staff_client, title="Own", excerpt="My own summary")
    assert custom["excerpt"] == "My own summary"


def test_search_text_is_kept_in_sync(staff_client):
    sid = create(staff_client)["id"]
    assert "Hello world" in Story.objects.get(pk=sid).search_text
    staff_client.patch(f"{URL}{sid}/", {"content_json": DOC_B}, format="json")
    assert "Second version" in Story.objects.get(pk=sid).search_text


def test_categories_and_tags_assigned_by_id(staff_client, db):
    cat, tag = Category.objects.create(name="Fiction"), Tag.objects.create(name="sea")
    data = create(staff_client, category_ids=[cat.id], tag_ids=[tag.id])
    assert data["category_ids"] == [cat.id] and data["tag_ids"] == [tag.id]
    assert data["categories"][0]["slug"] == "fiction" and data["tags"][0]["slug"] == "sea"
    bad = staff_client.post(URL, {"title": "x", "category_ids": [99999]}, format="json")
    assert bad.status_code == 400


def test_dangerous_content_is_rejected_over_the_api(staff_client):
    bad = {"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "text", "text": "x", "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}]}]}]}
    r = staff_client.post(URL, {"title": "Evil", "content_json": bad}, format="json")
    assert r.status_code == 400 and "content_json" in r.json()["errors"]
    assert Story.objects.count() == 0


# ---- update / revisions -------------------------------------------------------------
def test_patch_updates_story_and_creates_revision(staff_client):
    sid = create(staff_client)["id"]
    r = staff_client.patch(f"{URL}{sid}/", {"title": "Renamed", "content_json": DOC_B, "is_featured": True, "seo_title": "SEO"}, format="json")
    assert r.status_code == 200
    data = r.json()["data"]
    assert (data["title"], data["is_featured"], data["seo_title"]) == ("Renamed", True, "SEO")
    assert data["slug"] == "my-story"  # slug stays stable when the title changes
    assert revisions(sid) == 2


def test_patch_cannot_change_status_or_counters(staff_client):
    sid = create(staff_client)["id"]
    r = staff_client.patch(f"{URL}{sid}/", {"status": "published", "view_count": 50}, format="json")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "draft" and r.json()["data"]["view_count"] == 0


def test_put_is_not_allowed(staff_client):
    sid = create(staff_client)["id"]
    assert staff_client.put(f"{URL}{sid}/", {"title": "x"}, format="json").status_code == 405


def test_patch_can_replace_categories(staff_client, db):
    a, b = Category.objects.create(name="A"), Category.objects.create(name="B")
    sid = create(staff_client, category_ids=[a.id])["id"]
    r = staff_client.patch(f"{URL}{sid}/", {"category_ids": [b.id]}, format="json")
    assert r.json()["data"]["category_ids"] == [b.id]


def test_autosave_does_not_flood_revisions(staff_client):
    sid = create(staff_client)["id"]
    staff_client.patch(f"{URL}{sid}/?autosave=1", {"content_json": DOC_B}, format="json")
    assert revisions(sid) == 1  # latest revision is younger than 10 minutes
    StoryRevision.objects.filter(story_id=sid).update(created_at=timezone.now() - timedelta(minutes=11))
    staff_client.patch(f"{URL}{sid}/?autosave=1", {"content_json": DOC_B}, format="json")
    assert revisions(sid) == 2


def test_identical_content_creates_no_new_revision(staff_client):
    sid = create(staff_client)["id"]
    staff_client.patch(f"{URL}{sid}/", {"content_json": DOC_A}, format="json")
    assert revisions(sid) == 1


def test_revision_list_and_restore(staff_client):
    sid = create(staff_client)["id"]
    staff_client.patch(f"{URL}{sid}/", {"title": "Second", "content_json": DOC_B}, format="json")
    revs = staff_client.get(f"{URL}{sid}/revisions/").json()["data"]
    assert [r["revision_number"] for r in revs] == [2, 1]  # newest first
    assert revs[0]["author"] == "staff" and revs[0]["content_json"] == DOC_B

    first = revs[-1]
    r = staff_client.post(f"{URL}{sid}/revisions/{first['id']}/restore/")
    assert r.status_code == 200
    assert r.json()["data"]["content_json"] == DOC_A and r.json()["data"]["title"] == "My Story"
    assert revisions(sid) == 3  # the restore is itself a new revision


def test_restore_of_unknown_revision_is_404(staff_client):
    sid = create(staff_client)["id"]
    assert staff_client.post(f"{URL}{sid}/revisions/99999/restore/").status_code == 404


# ---- workflow -------------------------------------------------------------------------
def test_publish_sets_published_at_and_keeps_it(staff_client):
    sid = create(staff_client)["id"]
    first = staff_client.post(f"{URL}{sid}/publish/").json()["data"]
    assert first["status"] == "published" and first["published_at"]
    again = staff_client.post(f"{URL}{sid}/publish/").json()["data"]
    assert again["published_at"] == first["published_at"]


def test_publish_refuses_an_empty_story(staff_client):
    sid = staff_client.post(URL, {"title": "Empty"}, format="json").json()["data"]["id"]
    r = staff_client.post(f"{URL}{sid}/publish/")
    assert r.status_code == 400 and r.json()["data"] is None
    assert Story.objects.get(pk=sid).status == "draft"


def test_unpublish_and_archive(staff_client):
    sid = create(staff_client)["id"]
    staff_client.post(f"{URL}{sid}/publish/")
    assert staff_client.post(f"{URL}{sid}/unpublish/").json()["data"]["status"] == "draft"
    assert staff_client.post(f"{URL}{sid}/archive/").json()["data"]["status"] == "archived"


def test_schedule_rejects_the_past_and_accepts_the_future(staff_client):
    sid = create(staff_client)["id"]
    past = (timezone.now() - timedelta(minutes=5)).isoformat()
    assert staff_client.post(f"{URL}{sid}/schedule/", {"scheduled_at": past}, format="json").status_code == 400
    assert staff_client.post(f"{URL}{sid}/schedule/", {}, format="json").status_code == 400
    future = (timezone.now() + timedelta(hours=2)).isoformat()
    r = staff_client.post(f"{URL}{sid}/schedule/", {"scheduled_at": future}, format="json")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "scheduled" and data["scheduled_at"] and data["published_at"] is None


def test_publish_due_publishes_a_due_scheduled_story(staff_client):
    sid = create(staff_client)["id"]
    future = (timezone.now() + timedelta(hours=1)).isoformat()
    staff_client.post(f"{URL}{sid}/schedule/", {"scheduled_at": future}, format="json")
    assert publish_due() == 0  # not due yet
    due = timezone.now() - timedelta(seconds=30)
    Story.objects.filter(pk=sid).update(scheduled_at=due)
    assert publish_due() == 1
    story = Story.objects.get(pk=sid)
    assert story.status == "published" and story.published_at == due


def test_admin_requests_publish_due_stories_automatically(staff_client):
    sid = create(staff_client)["id"]
    Story.objects.filter(pk=sid).update(status="scheduled", scheduled_at=timezone.now() - timedelta(minutes=1))
    assert staff_client.get(f"{URL}{sid}/").json()["data"]["status"] == "published"


def test_public_queryset_excludes_drafts_and_future_stories(db):
    now = timezone.now()
    Story.objects.create(title="Draft", content_json=doc("a"))
    Story.objects.create(title="Archived", status="archived", published_at=now - timedelta(days=1))
    Story.objects.create(title="Scheduled", status="scheduled", scheduled_at=now + timedelta(days=1))
    Story.objects.create(title="Future", status="published", published_at=now + timedelta(days=1))
    live = Story.objects.create(title="Live", status="published", published_at=now - timedelta(hours=1))
    assert list(Story.objects.public()) == [live]


def test_create_revision_service_skips_unchanged_content(staff, db):
    story = Story.objects.create(title="T", content_json=DOC_A)
    assert create_revision(story, staff).revision_number == 1
    assert create_revision(story, staff) is None


# ---- list filters ---------------------------------------------------------------------
@pytest.fixture
def library(db):
    fic, ess = Category.objects.create(name="Fiction"), Category.objects.create(name="Essays")
    sea, hill = Tag.objects.create(name="sea"), Tag.objects.create(name="hills")
    a = Story.objects.create(title="Alpha tale", status="published", published_at=timezone.now(), is_featured=True, content_json=doc("a"))
    b = Story.objects.create(title="Beta story", content_json=doc("b"))
    c = Story.objects.create(title="Gamma note", status="archived", content_json=doc("c"))
    a.categories.add(fic)
    a.tags.add(sea)
    b.categories.add(ess)
    b.tags.add(hill)
    return {"a": a, "b": b, "c": c, "fic": fic, "ess": ess, "sea": sea, "hill": hill}


def titles(client, query=""):
    return sorted(s["title"] for s in client.get(f"{URL}?{query}").json()["data"])


def test_list_filters(staff_client, library):
    assert titles(staff_client) == ["Alpha tale", "Beta story", "Gamma note"]
    assert titles(staff_client, "status=published") == ["Alpha tale"]
    assert titles(staff_client, "status=archived") == ["Gamma note"]
    assert titles(staff_client, "q=beta") == ["Beta story"]
    assert titles(staff_client, "q=gamma-n") == ["Gamma note"]  # matches the slug too
    assert titles(staff_client, "category=fiction") == ["Alpha tale"]
    assert titles(staff_client, "tag=hills") == ["Beta story"]
    assert titles(staff_client, "featured=1") == ["Alpha tale"]
    assert titles(staff_client, "category=fiction&status=draft") == []


def test_list_ordering(staff_client, library):
    ordered = [s["title"] for s in staff_client.get(f"{URL}?ordering=title").json()["data"]]
    assert ordered == ["Alpha tale", "Beta story", "Gamma note"]
    ordered = [s["title"] for s in staff_client.get(f"{URL}?ordering=-title").json()["data"]]
    assert ordered == ["Gamma note", "Beta story", "Alpha tale"]
    # unknown ordering values are ignored, not an error
    assert staff_client.get(f"{URL}?ordering=password").status_code == 200


def test_list_omits_content_and_is_paginated(staff_client, db):
    for i in range(15):
        Story.objects.create(title=f"Story {i}", content_json=doc("x"))
    body = staff_client.get(URL).json()
    assert len(body["data"]) == 12 and body["pagination"]["total_pages"] == 2
    assert "content_json" not in body["data"][0]
    assert len(staff_client.get(URL + "?page=2").json()["data"]) == 3


def test_list_query_count_stays_small(staff_client, staff, django_assert_max_num_queries, db):
    cat, tag = Category.objects.create(name="C"), Tag.objects.create(name="t")
    for i in range(15):
        s = Story.objects.create(title=f"Story {i}", content_json=doc("x"), created_by=staff)
        s.categories.add(cat)
        s.tags.add(tag)
    with django_assert_max_num_queries(10):
        r = staff_client.get(URL)
    assert r.status_code == 200 and len(r.json()["data"]) == 12


# ---- delete / 404 ---------------------------------------------------------------------
def test_delete_removes_the_story_and_its_revisions(staff_client):
    sid = create(staff_client)["id"]
    r = staff_client.delete(f"{URL}{sid}/")
    assert r.status_code == 204
    assert not Story.objects.filter(pk=sid).exists() and revisions(sid) == 0
    assert staff_client.get(f"{URL}{sid}/").status_code == 404


def test_missing_story_returns_standard_404_envelope(staff_client, db):
    r = staff_client.get(f"{URL}999999/")
    assert r.status_code == 404
    body = r.json()
    assert body["data"] is None and "errors" in body and "message" in body
    assert staff_client.post(f"{URL}999999/publish/").status_code == 404
    assert staff_client.get(f"{URL}999999/revisions/").status_code == 404
