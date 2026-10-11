import re
from pathlib import Path

import pytest
from PIL import Image
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.media.models import MediaAsset
from apps.stories.models import Story
from config.settings.base import storages_from_env

from .media_helpers import animated_gif, flat_png, jpeg_with_exif, make_image, noisy_png

URL = "/api/v1/admin/media/"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Every test writes into its own temporary folder, never into backend/media."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def stored_files(root):
    return [p for p in Path(root).rglob("*") if p.is_file()]


def upload(client, *files, **extra):
    return client.post(URL, {"files": list(files), **extra}, format="multipart")


def fake_asset(**kw):
    """An asset row without a real file, for list/permission tests."""
    defaults = dict(file="uploads/2026/01/x.jpg", mime_type="image/jpeg", width=10, height=10, size_bytes=1)
    return MediaAsset.objects.create(**{**defaults, **kw})


# ---- permissions -----------------------------------------------------------------
def test_anonymous_is_denied_everywhere(client, db):
    a = fake_asset()
    for method, url in [("get", URL), ("post", URL), ("get", f"{URL}{a.id}/"), ("patch", f"{URL}{a.id}/"),
                        ("delete", f"{URL}{a.id}/"), ("post", f"{URL}{a.id}/replace/")]:
        assert getattr(client, method)(url).status_code in (401, 403), (method, url)


def test_normal_user_is_denied_everywhere(client, user):
    a = fake_asset()
    client.force_authenticate(user)
    for method, url in [("get", URL), ("post", URL), ("get", f"{URL}{a.id}/"), ("patch", f"{URL}{a.id}/"),
                        ("delete", f"{URL}{a.id}/"), ("post", f"{URL}{a.id}/replace/")]:
        assert getattr(client, method)(url).status_code == 403, (method, url)


# ---- uploading ---------------------------------------------------------------------
@pytest.mark.parametrize("fmt,mime,ext", [("JPEG", "image/jpeg", ".jpg"), ("PNG", "image/png", ".png"),
                                          ("WEBP", "image/webp", ".webp"), ("GIF", "image/gif", ".gif")])
def test_upload_each_format_records_real_metadata(staff_client, media_root, fmt, mime, ext):
    r = upload(staff_client, make_image(fmt, size=(64, 48)))
    assert r.status_code == 201, r.content
    data = r.json()["data"][0]
    assert (data["width"], data["height"], data["mime_type"], data["file_type"]) == (64, 48, mime, "image")
    asset = MediaAsset.objects.get(pk=data["id"])
    path = Path(asset.file.path)
    assert path.exists() and path.suffix == ext
    assert data["size_bytes"] == path.stat().st_size == asset.size_bytes
    assert data["url"].startswith("/media/uploads/")
    assert data["uploaded_by"] == "staff"


def test_stored_filename_is_a_uuid_and_ignores_the_client_name(staff_client, media_root):
    r = upload(staff_client, make_image("JPEG", name="../../evil.jpg"))
    assert r.status_code == 201
    stored = MediaAsset.objects.get().file.name
    assert re.fullmatch(r"uploads/\d{4}/\d{2}/[0-9a-f]{32}\.jpg", stored)
    assert "evil" not in stored
    assert all(media_root in p.parents for p in stored_files(media_root))


def test_several_files_in_one_request(staff_client):
    r = upload(staff_client, make_image("JPEG"), make_image("PNG"), make_image("WEBP"))
    assert r.status_code == 201 and len(r.json()["data"]) == 3
    assert MediaAsset.objects.count() == 3


def test_single_file_field_and_alt_text(staff_client):
    r = staff_client.post(URL, {"file": make_image("PNG"), "alt_text": "A red square"}, format="multipart")
    assert r.status_code == 201
    assert r.json()["data"][0]["alt_text"] == "A red square"


def test_no_file_is_an_error(staff_client):
    assert staff_client.post(URL, {}, format="multipart").status_code == 400


def test_more_than_ten_files_rejected(staff_client, media_root):
    r = upload(staff_client, *[make_image("PNG", size=(4, 4)) for _ in range(11)])
    assert r.status_code == 400
    assert MediaAsset.objects.count() == 0 and not stored_files(media_root)


def test_one_bad_file_among_good_ones_saves_nothing(staff_client, media_root):
    bad = make_image("PNG", name="renamed.jpg", content_type="image/jpeg")  # PNG content, .jpg name
    r = upload(staff_client, make_image("JPEG"), bad, make_image("WEBP"))
    assert r.status_code == 400
    assert any("renamed.jpg" in m for m in r.json()["errors"]["file"])
    assert MediaAsset.objects.count() == 0 and not stored_files(media_root)


def test_every_problem_file_is_reported(staff_client):
    r = upload(staff_client, make_image("PNG", name="a.jpg", content_type="image/jpeg"), make_image("JPEG", name="b.svg", content_type="image/svg+xml"))
    assert len(r.json()["errors"]["file"]) == 2


# ---- rejected content ----------------------------------------------------------------
def test_text_file_renamed_to_jpg_is_rejected(staff_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    fake = SimpleUploadedFile("notes.jpg", b"this is just text, not an image", content_type="image/jpeg")
    r = upload(staff_client, fake)
    assert r.status_code == 400 and "not a valid image" in r.json()["errors"]["file"][0]


def test_svg_is_rejected(staff_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    svg = SimpleUploadedFile("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', content_type="image/svg+xml")
    r = upload(staff_client, svg)
    assert r.status_code == 400 and "only JPEG, PNG, WebP and GIF" in r.json()["errors"]["file"][0]


def test_png_content_named_jpg_is_rejected(staff_client):
    r = upload(staff_client, make_image("PNG", name="photo.jpg", content_type="image/jpeg"))
    assert r.status_code == 400 and "does not match" in r.json()["errors"]["file"][0]


def test_wrong_content_type_is_rejected(staff_client):
    assert upload(staff_client, make_image("JPEG", content_type="image/png")).status_code == 400
    assert upload(staff_client, make_image("JPEG", content_type="application/octet-stream")).status_code == 400


def test_other_extensions_rejected(staff_client):
    for name in ["doc.pdf", "pic.heic", "script.php", "noext"]:
        r = upload(staff_client, make_image("JPEG", name=name))
        assert r.status_code == 400, name


def test_too_large_is_rejected(staff_client, settings):
    settings.MEDIA_MAX_UPLOAD_BYTES = 2000
    r = upload(staff_client, noisy_png())
    assert r.status_code == 400 and "larger than" in r.json()["errors"]["file"][0]
    assert MediaAsset.objects.count() == 0


def test_too_many_pixels_and_too_long_sides_rejected(staff_client):
    assert upload(staff_client, flat_png((7000, 6000))).status_code == 400  # 42 megapixels
    assert upload(staff_client, flat_png((12001, 10))).status_code == 400  # side longer than 12000 px
    assert MediaAsset.objects.count() == 0


# ---- metadata stripping --------------------------------------------------------------
def test_exif_is_removed_and_orientation_applied(staff_client):
    r = upload(staff_client, jpeg_with_exif(size=(40, 30), orientation=6))
    assert r.status_code == 201
    data = r.json()["data"][0]
    assert (data["width"], data["height"]) == (30, 40)  # rotated into the right way up
    with Image.open(MediaAsset.objects.get().file.path) as stored:
        assert len(stored.getexif()) == 0  # no orientation, no camera make, no GPS
        assert "exif" not in stored.info
        assert stored.size == (30, 40)


def test_animated_gif_stays_animated(staff_client):
    r = upload(staff_client, animated_gif(frames=3))
    assert r.status_code == 201
    with Image.open(MediaAsset.objects.get().file.path) as stored:
        assert stored.n_frames == 3


# ---- gallery ---------------------------------------------------------------------------
def test_list_is_paginated_newest_first_and_searchable(staff_client, db):
    ids = [fake_asset(alt_text=f"picture {i}", caption="sunset" if i == 1 else "").id for i in range(30)]
    body = staff_client.get(URL).json()
    assert len(body["data"]) == 24 and body["pagination"]["total_pages"] == 2
    assert [a["id"] for a in body["data"]] == sorted(ids, reverse=True)[:24]
    assert len(staff_client.get(URL + "?page=2").json()["data"]) == 6
    assert [a["alt_text"] for a in staff_client.get(URL + "?q=picture 7").json()["data"]] == ["picture 7"]
    assert len(staff_client.get(URL + "?q=sunset").json()["data"]) == 1  # caption search
    small = fake_asset(size_bytes=0)
    assert staff_client.get(URL + "?ordering=size_bytes").json()["data"][0]["id"] == small.id
    assert staff_client.get(URL + "?ordering=hack").status_code == 200  # unknown ordering ignored


def test_patch_changes_only_alt_text_and_caption(staff_client, db):
    a = fake_asset()
    r = staff_client.patch(f"{URL}{a.id}/", {"alt_text": "Alt", "caption": "Cap", "width": 999, "mime_type": "x/y", "size_bytes": 5}, format="json")
    assert r.status_code == 200
    a.refresh_from_db()
    assert (a.alt_text, a.caption) == ("Alt", "Cap")
    assert (a.width, a.mime_type, a.size_bytes) == (10, "image/jpeg", 1)


def test_replace_keeps_the_id_and_swaps_the_file(staff_client, media_root):
    asset_id = upload(staff_client, make_image("JPEG", size=(40, 30))).json()["data"][0]["id"]
    asset = MediaAsset.objects.get(pk=asset_id)
    old_path = Path(asset.file.path)
    r = staff_client.post(f"{URL}{asset_id}/replace/", {"file": make_image("PNG", size=(10, 20))}, format="multipart")
    assert r.status_code == 200
    asset.refresh_from_db()
    new_path = Path(asset.file.path)
    assert asset.pk == asset_id and new_path != old_path and new_path.suffix == ".png"
    assert not old_path.exists() and new_path.exists()
    assert (asset.width, asset.height, asset.mime_type) == (10, 20, "image/png")
    assert len(stored_files(media_root)) == 1


def test_replace_rejects_bad_files_and_keeps_the_old_one(staff_client, media_root):
    asset_id = upload(staff_client, make_image("JPEG")).json()["data"][0]["id"]
    bad = make_image("PNG", name="x.jpg", content_type="image/jpeg")
    assert staff_client.post(f"{URL}{asset_id}/replace/", {"file": bad}, format="multipart").status_code == 400
    assert len(stored_files(media_root)) == 1


# ---- deleting and usage ----------------------------------------------------------------
def test_delete_unused_removes_record_and_file(staff_client, media_root):
    asset_id = upload(staff_client, make_image("JPEG")).json()["data"][0]["id"]
    assert len(stored_files(media_root)) == 1
    assert staff_client.delete(f"{URL}{asset_id}/").status_code == 204
    assert not MediaAsset.objects.filter(pk=asset_id).exists() and not stored_files(media_root)
    assert staff_client.get(f"{URL}{asset_id}/").status_code == 404


def image_doc(asset_id):
    return {"type": "doc", "content": [{"type": "image", "attrs": {"assetId": asset_id}}]}


def test_used_in_lists_cover_and_content_usage(staff_client, db):
    a = fake_asset()
    cover_story = Story.objects.create(title="Has cover", cover_image=a)
    content_story = Story.objects.create(title="Has content", content_json=image_doc(a.id))
    Story.objects.create(title="Unrelated")
    used = staff_client.get(f"{URL}{a.id}/").json()["data"]["used_in"]
    assert used == [
        {"id": cover_story.id, "title": "Has cover", "status": "draft", "used_as": "cover"},
        {"id": content_story.id, "title": "Has content", "status": "draft", "used_as": "content"},
    ]
    assert staff_client.get(f"{URL}{fake_asset().id}/").json()["data"]["used_in"] == []


def test_delete_is_refused_when_in_use_and_force_overrides(staff_client, media_root):
    asset_id = upload(staff_client, make_image("JPEG")).json()["data"][0]["id"]
    asset = MediaAsset.objects.get(pk=asset_id)
    cover_story = Story.objects.create(title="Cover story", cover_image=asset)
    Story.objects.create(title="Content story", content_json=image_doc(asset_id))

    r = staff_client.delete(f"{URL}{asset_id}/")
    assert r.status_code == 400
    assert len(r.json()["errors"]["used_in"]) == 2
    assert isinstance(r.json()["errors"]["used_in"][0]["id"], int)
    assert "used in 2" in r.json()["message"]
    assert MediaAsset.objects.filter(pk=asset_id).exists() and len(stored_files(media_root)) == 1

    assert staff_client.delete(f"{URL}{asset_id}/?force=1").status_code == 204
    cover_story.refresh_from_db()
    assert cover_story.cover_image is None  # SET_NULL
    assert not stored_files(media_root)


# ---- throttling ------------------------------------------------------------------------
def test_upload_throttle_returns_429(staff_client, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "media_upload", "2/hour")
    assert upload(staff_client, make_image("PNG", size=(4, 4))).status_code == 201
    assert upload(staff_client, make_image("PNG", size=(4, 4))).status_code == 201
    r = upload(staff_client, make_image("PNG", size=(4, 4)))
    assert r.status_code == 429 and r.json()["data"] is None
    assert staff_client.get(URL).status_code == 200  # only POST is throttled


# ---- storage settings --------------------------------------------------------------------
def test_local_storage_when_no_bucket_is_configured():
    for env in ({}, {"MEDIA_STORAGE_BUCKET": ""}, {"MEDIA_STORAGE_BUCKET": "  ", "MEDIA_STORAGE_ENDPOINT": "http://x"}):
        storages = storages_from_env(env)
        assert storages["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"
        assert "staticfiles" in storages


def test_s3_storage_when_a_bucket_is_configured():
    storages = storages_from_env({
        "MEDIA_STORAGE_BUCKET": "story-media", "MEDIA_STORAGE_ENDPOINT": "http://localhost:9000",
        "MEDIA_STORAGE_ACCESS_KEY": "k", "MEDIA_STORAGE_SECRET_KEY": "s", "MEDIA_CDN_DOMAIN": "media.example.com",
    })
    default = storages["default"]
    assert default["BACKEND"] == "storages.backends.s3.S3Storage"
    options = default["OPTIONS"]
    assert options["bucket_name"] == "story-media" and options["endpoint_url"] == "http://localhost:9000"
    assert options["custom_domain"] == "media.example.com" and options["region_name"] is None
    assert options["file_overwrite"] is False and options["querystring_auth"] is False
    assert "immutable" in options["object_parameters"]["CacheControl"]
