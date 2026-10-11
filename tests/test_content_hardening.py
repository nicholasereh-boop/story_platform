"""Phase 10 (E1, E2): hostile story JSON and crafted uploads."""
import copy
import os
import re
from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.stories.content import clean_content, youtube_id

from .media_helpers import flat_png, image_bytes, jpeg_with_exif, make_image
from .test_media import media_root, stored_files, upload  # noqa: F401  (media_root is an autouse fixture)


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def para(text, marks=None):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return {"type": "paragraph", "content": [node]}


# ---- E2: story content ----------------------------------------------------------------
@pytest.mark.parametrize("href", [
    "javascript:alert(1)", "JAVASCRIPT:alert(1)", " javascript:alert(1)", "java\tscript:alert(1)", "java\nscript:alert(1)",
    "vbscript:msgbox(1)", "data:text/html;base64,PHNjcmlwdD4=", "data:image/svg+xml,<svg onload=alert(1)>", "file:///etc/passwd",
    "//evil.example/x", "ftp://example.com", "\x00javascript:alert(1)", "https://exa mple.com", "tel:+123456789",
])
def test_link_protocols_are_an_allowlist(href):
    with pytest.raises(ValidationError):
        clean_content(doc(para("x", [{"type": "link", "attrs": {"href": href}}])))


@pytest.mark.parametrize("href", ["http://example.com", "https://example.com/a?b=c#d", "mailto:me@example.com", "HTTPS://EXAMPLE.COM"])
def test_allowed_protocols_pass(href):
    out = clean_content(doc(para("x", [{"type": "link", "attrs": {"href": href}}])))
    assert out["content"][0]["content"][0]["marks"][0]["attrs"]["href"] == href


@pytest.mark.parametrize("value", ["short", "x" * 12, "dQw4w9WgXcQ extra", "javascript:alert(1)", "https://evil.example/embed/dQw4w9WgXcQ", "dQw4w9WgXc!", "<script>1234", ""])
def test_youtube_accepts_only_an_eleven_character_id(value):
    assert youtube_id(value) is None
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "youtube", "attrs": {"videoId": value}}))


def test_youtube_node_stores_only_the_id():
    out = clean_content(doc({"type": "youtube", "attrs": {"videoId": "dQw4w9WgXcQ", "src": "https://evil.example", "onload": "x"}}))
    assert out["content"][0] == {"type": "youtube", "attrs": {"videoId": "dQw4w9WgXcQ"}}


@pytest.mark.parametrize("node", [
    {"type": "script"}, {"type": "iframe", "attrs": {"src": "https://evil.example"}}, {"type": "html", "text": "<b>x</b>"},
    {"type": "codeBlock"}, {"type": "table"}, {"type": "embed"}, {"type": "paragraph", "content": [{"type": "style"}]},
])
def test_unknown_nodes_are_rejected(node):
    with pytest.raises(ValidationError):
        clean_content(doc(node))


@pytest.mark.parametrize("mark", [{"type": "code"}, {"type": "highlight"}, {"type": "textStyle", "attrs": {"color": "red"}}, {"type": "script"}])
def test_unknown_marks_are_rejected(mark):
    with pytest.raises(ValidationError):
        clean_content(doc(para("x", [mark])))


def test_event_handler_attributes_never_survive():
    hostile = doc({"type": "paragraph", "attrs": {"onclick": "alert(1)", "style": "x", "textAlign": "left"}, "content": [{"type": "text", "text": "x"}]})
    out = clean_content(hostile)
    assert out["content"][0]["attrs"] == {"textAlign": "left"}


def test_image_attributes_are_rebuilt_from_the_allowlist():
    out = clean_content(doc({"type": "image", "attrs": {"assetId": 3, "alt": "a", "src": "javascript:alert(1)", "onerror": "x", "align": "left"}}))
    assert set(out["content"][0]["attrs"]) <= {"assetId", "alt", "caption", "align", "size"}


@pytest.mark.parametrize("asset", ["3", -1, 0, None, True, "javascript:alert(1)", 1.5])
def test_image_needs_a_real_positive_asset_id(asset):
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "image", "attrs": {"assetId": asset}}))


def test_depth_node_and_size_caps():
    deep = {"type": "paragraph"}
    for _ in range(40):
        deep = {"type": "blockquote", "content": [deep]}
    with pytest.raises(ValidationError):
        clean_content(doc(deep))
    with pytest.raises(ValidationError):
        clean_content(doc(*[{"type": "paragraph"} for _ in range(5001)]))
    with pytest.raises(ValidationError):
        clean_content(doc(*[para("x" * 15000) for _ in range(80)]))


def test_a_hostile_document_is_not_mutated_in_place():
    original = doc(para("x", [{"type": "link", "attrs": {"href": "https://ok.example", "onclick": "x"}}]))
    snapshot = copy.deepcopy(original)
    clean_content(original)
    assert original == snapshot


def test_the_story_api_refuses_hostile_content(staff_client):
    r = staff_client.post("/api/v1/admin/stories/", {"title": "T", "content_json": doc({"type": "iframe"})}, format="json")
    assert r.status_code == 400
    r = staff_client.post("/api/v1/admin/stories/", {"title": "T", "content_json": doc(para("x", [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}]))}, format="json")
    assert r.status_code == 400


# ---- E1: uploads ----------------------------------------------------------------------
def test_stored_images_contain_no_payload_and_no_metadata(staff_client, media_root):
    payload = b"<script>alert(1)</script>GIF89a"
    for f in (
        SimpleUploadedFile("x.jpg", image_bytes("JPEG") + payload, content_type="image/jpeg"),
        SimpleUploadedFile("y.png", image_bytes("PNG") + payload, content_type="image/png"),
        jpeg_with_exif(),
    ):
        upload(staff_client, f)
    files = stored_files(media_root)
    assert files
    for p in files:
        data = p.read_bytes()
        assert b"<script" not in data and b"SpyCam" not in data
        with Image.open(BytesIO(data)) as im:
            assert not im.getexif() and "exif" not in im.info and "icc_profile" not in im.info


@pytest.mark.parametrize("name,content,ctype", [
    ("a.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', "image/svg+xml"),
    ("a.jpg", b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/jpeg"),
    ("a.jpg", b"<html><script>alert(1)</script></html>", "image/jpeg"),
    ("a.html", b"<html></html>", "text/html"),
    ("a.php.jpg", b"<?php echo 1;?>", "image/jpeg"),
    ("a.jpg", b"", "image/jpeg"),
    ("a.jpg", b"\xff\xd8\xff garbage", "image/jpeg"),
])
def test_disguised_and_broken_files_are_refused(staff_client, media_root, name, content, ctype):
    r = upload(staff_client, SimpleUploadedFile(name, content, content_type=ctype))
    assert r.status_code == 400
    assert stored_files(media_root) == []


def test_a_png_named_jpg_and_a_wrong_content_type_are_refused(staff_client):
    assert upload(staff_client, SimpleUploadedFile("a.jpg", image_bytes("PNG"), content_type="image/jpeg")).status_code == 400
    assert upload(staff_client, SimpleUploadedFile("a.png", image_bytes("PNG"), content_type="text/html")).status_code == 400


def test_decompression_bombs_are_refused(staff_client, monkeypatch, media_root):
    from apps.media import images

    monkeypatch.setattr(images, "MAX_PIXELS", 1_000_000)
    r = upload(staff_client, flat_png((3000, 3000)))
    assert r.status_code == 400 and stored_files(media_root) == []


def test_oversized_files_are_refused(staff_client, settings):
    settings.MEDIA_MAX_UPLOAD_BYTES = 100
    assert upload(staff_client, make_image("PNG", size=(200, 200))).status_code == 400


def test_stored_names_are_random_and_the_client_name_is_display_text_only(staff_client, media_root):
    evil = make_image("JPEG", name="../../../etc/passwd<script>.jpg")
    r = upload(staff_client, evil)
    assert r.status_code == 201
    row = r.json()["data"][0]
    assert "<" not in row["original_name"] and ".." not in row["original_name"] and "/" not in row["original_name"]
    stored = stored_files(media_root)
    assert len(stored) == 1 and re.fullmatch(r"[0-9a-f]{32}\.jpg", stored[0].name)
    assert "passwd" not in str(stored[0]) and Path(media_root) in stored[0].parents


def test_alt_text_and_caption_are_plain_text_with_limits(staff_client, media_root):
    asset = upload(staff_client, make_image("PNG")).json()["data"][0]
    url = f"/api/v1/admin/media/{asset['id']}/"
    assert staff_client.patch(url, {"alt_text": "<img src=x onerror=alert(1)>"}, format="json").status_code == 400
    assert staff_client.patch(url, {"caption": "a" * 501}, format="json").status_code == 400
    assert staff_client.patch(url, {"alt_text": "x" * 301}, format="json").status_code == 400
    ok = staff_client.patch(url, {"alt_text": "Fine‮ text\x00"}, format="json")
    assert ok.status_code == 200 and ok.json()["data"]["alt_text"] == "Fine text"


def test_the_upload_quota_is_per_user_per_hour(staff_client, settings, media_root):
    settings.MEDIA_UPLOAD_QUOTA_PER_HOUR = 2
    assert upload(staff_client, make_image("PNG")).status_code == 201
    assert upload(staff_client, make_image("PNG"), make_image("JPEG")).status_code == 429  # would make 3
    assert upload(staff_client, make_image("PNG")).status_code == 201
    assert upload(staff_client, make_image("PNG")).status_code == 429
