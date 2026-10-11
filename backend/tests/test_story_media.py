import pytest

from apps.media.models import MediaAsset
from apps.stories.content import clean_content, resolve_media
from apps.stories.models import Story

URL = "/api/v1/admin/stories/"


@pytest.fixture
def asset(db):
    return MediaAsset.objects.create(
        file="uploads/2026/01/lighthouse.jpg", mime_type="image/jpeg", width=800, height=600, size_bytes=1234,
        alt_text="Lighthouse at dusk", caption="From the pier",
    )


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def image_node(asset_id, **attrs):
    return {"type": "image", "attrs": {"assetId": asset_id, **attrs}}


def para(text="Some text"):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def create(client, **extra):
    r = client.post(URL, {"title": "Story", "content_json": doc(para()), **extra}, format="json")
    assert r.status_code == 201, r.content
    return r.json()["data"]


# ---- cover image ---------------------------------------------------------------------
def test_cover_image_set_clear_and_unknown_id(staff_client, asset):
    data = create(staff_client, cover_image=asset.id)
    assert data["cover_image"] == asset.id
    assert data["cover"] == {"id": asset.id, "url": "/media/uploads/2026/01/lighthouse.jpg", "alt_text": "Lighthouse at dusk", "width": 800, "height": 600}

    cleared = staff_client.patch(f"{URL}{data['id']}/", {"cover_image": None}, format="json")
    assert cleared.status_code == 200 and cleared.json()["data"]["cover"] is None

    for bad in (999999, "abc"):
        r = staff_client.patch(f"{URL}{data['id']}/", {"cover_image": bad}, format="json")
        assert r.status_code == 400
        assert r.json()["errors"]["cover_image"] == ["That image does not exist."]


def test_cover_appears_nested_in_list_and_detail(staff_client, asset):
    data = create(staff_client, cover_image=asset.id)
    listed = staff_client.get(URL).json()["data"][0]
    detail = staff_client.get(f"{URL}{data['id']}/").json()["data"]
    for payload in (listed, detail):
        assert payload["cover"]["id"] == asset.id and payload["cover"]["width"] == 800
    assert "content_json" not in listed


def test_story_without_cover_has_null_cover(staff_client, db):
    assert create(staff_client)["cover"] is None
    assert staff_client.get(URL).json()["data"][0]["cover"] is None


# ---- image-exists check ---------------------------------------------------------------
def test_content_with_an_existing_asset_is_accepted(staff_client, asset):
    r = staff_client.post(URL, {"title": "With image", "content_json": doc(image_node(asset.id), para())}, format="json")
    assert r.status_code == 201


def test_content_with_missing_assets_is_rejected_naming_the_ids(staff_client, asset):
    r = staff_client.post(URL, {"title": "Broken", "content_json": doc(image_node(asset.id), image_node(12345), image_node(12346))}, format="json")
    assert r.status_code == 400
    assert r.json()["errors"]["content_json"] == ["These images are not in the media library: 12345, 12346."]
    assert Story.objects.count() == 0


def test_patch_also_checks_that_images_exist(staff_client, asset):
    data = create(staff_client)
    r = staff_client.patch(f"{URL}{data['id']}/", {"content_json": doc(image_node(777))}, format="json")
    assert r.status_code == 400 and "777" in r.json()["errors"]["content_json"][0]


# ---- resolve_media -----------------------------------------------------------------------
def test_resolve_media_adds_src_width_height_and_alt_fallback(asset):
    original = doc(image_node(asset.id, align="left"))
    resolved = resolve_media(original)
    attrs = resolved["content"][0]["attrs"]
    assert attrs["src"] == "/media/uploads/2026/01/lighthouse.jpg"
    assert (attrs["width"], attrs["height"]) == (800, 600)
    assert attrs["alt"] == "Lighthouse at dusk" and attrs["caption"] == "From the pier"  # fallbacks
    assert attrs["align"] == "left"
    assert "src" not in original["content"][0]["attrs"]  # the input was not modified


def test_resolve_media_keeps_the_nodes_own_alt_text(asset):
    attrs = resolve_media(doc(image_node(asset.id, alt="Mine", caption="Own")))["content"][0]["attrs"]
    assert (attrs["alt"], attrs["caption"]) == ("Mine", "Own")


def test_resolve_media_gives_none_for_a_deleted_asset(asset):
    stale = doc(image_node(asset.id))
    asset.delete()
    attrs = resolve_media(stale)["content"][0]["attrs"]
    assert attrs["src"] is None and attrs["width"] is None and attrs["height"] is None


def test_detail_and_revisions_return_resolved_images(staff_client, asset):
    data = create(staff_client, content_json=doc(image_node(asset.id)))
    detail = staff_client.get(f"{URL}{data['id']}/").json()["data"]
    assert detail["content_json"]["content"][0]["attrs"]["src"] == "/media/uploads/2026/01/lighthouse.jpg"
    revs = staff_client.get(f"{URL}{data['id']}/revisions/").json()["data"]
    assert revs[0]["content_json"]["content"][0]["attrs"]["width"] == 800


def test_src_and_width_sent_by_the_client_are_ignored_on_save(staff_client, asset):
    node = image_node(asset.id, src="https://evil.example/x.png", width=1, height=1, style="x", alt="Own alt")
    data = create(staff_client, content_json=doc(node))
    stored = Story.objects.get(pk=data["id"]).content_json["content"][0]["attrs"]
    assert stored == {"assetId": asset.id, "alt": "Own alt", "caption": "", "align": "center", "size": "full"}
    # ...while the response shows the real values from the library
    shown = data["content_json"]["content"][0]["attrs"]
    assert shown["src"] == "/media/uploads/2026/01/lighthouse.jpg" and shown["width"] == 800
    assert clean_content(doc(node))["content"][0]["attrs"] == stored


# ---- performance -------------------------------------------------------------------------
def test_story_list_query_count_stays_small_with_covers(staff_client, staff, asset, django_assert_max_num_queries):
    for i in range(15):
        Story.objects.create(title=f"S{i}", cover_image=asset, created_by=staff)
    with django_assert_max_num_queries(10):
        r = staff_client.get(URL)
    assert r.status_code == 200 and r.json()["data"][0]["cover"]["id"] == asset.id
