import pytest

from apps.stories.models import Category, Story, Tag

CATS = "/api/v1/admin/categories/"
TAGS = "/api/v1/admin/tags/"


@pytest.mark.parametrize("url", [CATS, TAGS])
def test_permissions(client, user, url, db):
    assert client.get(url).status_code in (401, 403)
    assert client.post(url, {"name": "x"}, format="json").status_code in (401, 403)
    client.force_authenticate(user)
    assert client.get(url).status_code == 403
    assert client.post(url, {"name": "x"}, format="json").status_code == 403


def test_create_category_generates_slug(staff_client, db):
    r = staff_client.post(CATS, {"name": "Short Fiction", "description": "Made up things"}, format="json")
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["slug"] == "short-fiction" and data["story_count"] == 0 and data["description"] == "Made up things"


def test_create_tag_generates_slug_and_deduplicates(staff_client, db):
    assert staff_client.post(TAGS, {"name": "C++"}, format="json").json()["data"]["slug"] == "c"
    assert staff_client.post(TAGS, {"name": "C"}, format="json").json()["data"]["slug"] == "c-2"


@pytest.mark.parametrize("url,model", [(CATS, Category), (TAGS, Tag)])
def test_duplicate_names_rejected_in_any_case(staff_client, url, model, db):
    assert staff_client.post(url, {"name": "Poetry"}, format="json").status_code == 201
    for name in ["Poetry", "poetry", "POETRY", "  poetry "]:
        r = staff_client.post(url, {"name": name}, format="json")
        assert r.status_code == 400 and "name" in r.json()["errors"], name
    assert model.objects.count() == 1


def test_update_category_keeps_slug_stable(staff_client, db):
    cid = staff_client.post(CATS, {"name": "Old name"}, format="json").json()["data"]["id"]
    r = staff_client.patch(f"{CATS}{cid}/", {"name": "New name", "description": "d"}, format="json")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "New name" and data["slug"] == "old-name"
    # a category may keep its own name when saving, but not take another's
    other = staff_client.post(CATS, {"name": "Other"}, format="json").json()["data"]["id"]
    assert staff_client.patch(f"{CATS}{other}/", {"name": "new NAME"}, format="json").status_code == 400
    assert staff_client.patch(f"{CATS}{other}/", {"name": "Other"}, format="json").status_code == 200


def test_update_and_delete_tag(staff_client, db):
    tid = staff_client.post(TAGS, {"name": "sea"}, format="json").json()["data"]["id"]
    assert staff_client.patch(f"{TAGS}{tid}/", {"name": "ocean"}, format="json").json()["data"]["name"] == "ocean"
    assert staff_client.delete(f"{TAGS}{tid}/").status_code == 204
    assert staff_client.get(f"{TAGS}{tid}/").status_code == 404


def test_deleting_a_category_or_tag_keeps_the_stories(staff_client, db):
    cat, tag = Category.objects.create(name="Fiction"), Tag.objects.create(name="sea")
    story = Story.objects.create(title="Kept")
    story.categories.add(cat)
    story.tags.add(tag)
    assert staff_client.delete(f"{CATS}{cat.id}/").status_code == 204
    assert staff_client.delete(f"{TAGS}{tag.id}/").status_code == 204
    story.refresh_from_db()
    assert Story.objects.filter(pk=story.pk).exists()
    assert story.categories.count() == 0 and story.tags.count() == 0


def test_story_count_is_correct(staff_client, db):
    cat, tag = Category.objects.create(name="Fiction"), Tag.objects.create(name="sea")
    Category.objects.create(name="Empty")
    for i in range(2):
        s = Story.objects.create(title=f"S{i}")
        s.categories.add(cat)
        s.tags.add(tag)
    counts = {c["name"]: c["story_count"] for c in staff_client.get(CATS).json()["data"]}
    assert counts == {"Empty": 0, "Fiction": 2}
    assert staff_client.get(TAGS).json()["data"][0]["story_count"] == 2
    assert staff_client.get(f"{CATS}{cat.id}/").json()["data"]["story_count"] == 2


def test_lists_are_not_paginated(staff_client, db):
    for i in range(15):
        Category.objects.create(name=f"Cat {i:02d}")
    body = staff_client.get(CATS).json()
    assert len(body["data"]) == 15 and "pagination" not in body


def test_tag_autocomplete(staff_client, db):
    for name in ["sea", "seaside", "hills", "Season"]:
        Tag.objects.create(name=name)
    names = sorted(t["name"] for t in staff_client.get(TAGS + "?q=sea").json()["data"])
    assert names == ["Season", "sea", "seaside"]
    assert staff_client.get(TAGS + "?q=zzz").json()["data"] == []


def test_missing_category_returns_standard_404(staff_client, db):
    r = staff_client.get(f"{CATS}999999/")
    assert r.status_code == 404
    assert r.json()["data"] is None and "errors" in r.json()
