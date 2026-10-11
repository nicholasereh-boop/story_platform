"""Phase 10 (E3): one corpus of hostile text pushed through every place user text can enter.

For each payload the assertions are: it is either refused (400) or stored as inert TEXT; it comes back inside JSON
(so it is escaped by the serializer, never interpreted); and nothing in the HTML the backend itself generates (e-mails)
contains it unescaped. The Django admin is out of scope.
"""
import json

import pytest
from rest_framework.test import APIClient

from apps.stories.models import Story

from .conftest import PASSWORD
from .engagement_helpers import comments_url, make_story, make_user
from .security_helpers import login
from .test_media import media_root, upload  # noqa: F401
from .media_helpers import make_image

CORPUS = [
    "<script>alert(1)</script>",
    "\"><script>alert(document.cookie)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    "<iframe src=javascript:alert(1)></iframe>",
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "<a href=\"javascript:alert(1)\">x</a>",
    "' onmouseover='alert(1)",
    "{{7*7}}",
    "${7*7}",
    "{% load os %}{{ settings.SECRET_KEY }}",
    "<%= 7*7 %>",
    "‮<script>alert(1)</script>",
    "text with line sep   and para sep  ",
    "null byte \x00 inside",
    "<!--[if IE]><script>alert(1)</script><![endif]-->",
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "</textarea><script>alert(1)</script>",
    "</script><script>alert(1)</script>",
]
IDS = [f"p{i}" for i in range(len(CORPUS))]
DANGEROUS = ("\x00", "‮", " ", " ")


def inert(value):
    """What may be stored: no markup characters and none of the disguising characters."""
    return not any(ch in value for ch in "<>") and not any(ch in value for ch in DANGEROUS)


def doc_with(text):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def assert_json_safe(response):
    """The body is JSON, served as JSON, with nosniff: a browser will never treat it as HTML."""
    assert response["Content-Type"].startswith("application/json")
    assert response["X-Content-Type-Options"] == "nosniff"
    json.loads(response.content)


@pytest.mark.parametrize("payload", CORPUS, ids=IDS)
def test_story_fields(staff_client, payload):
    r = staff_client.post("/api/v1/admin/stories/", {
        "title": f"T {payload}"[:200], "excerpt": payload[:500], "seo_title": payload[:70], "seo_description": payload[:200],
        "content_json": doc_with(payload),
    }, format="json")
    assert_json_safe(r)
    assert r.status_code in (201, 400)
    if r.status_code == 201:
        # Stored as plain text inside JSON. Rendering is done by React as text; there is no HTML path for these fields.
        data = r.json()["data"]
        assert data["content_json"]["content"][0]["content"][0]["type"] == "text"
        assert "<script" not in json.dumps(data["content_json"]["content"][0]["attrs"] if "attrs" in data["content_json"]["content"][0] else {})


@pytest.mark.parametrize("payload", CORPUS, ids=IDS)
def test_story_content_never_creates_script_nodes_or_unsafe_links(staff_client, payload):
    link = {"type": "paragraph", "content": [{"type": "text", "text": "x", "marks": [{"type": "link", "attrs": {"href": payload}}]}]}
    r = staff_client.post("/api/v1/admin/stories/", {"title": "T", "content_json": {"type": "doc", "content": [link]}}, format="json")
    assert_json_safe(r)
    if r.status_code == 201:
        href = r.json()["data"]["content_json"]["content"][0]["content"][0]["marks"][0]["attrs"]["href"]
        assert href.lower().startswith(("http://", "https://", "mailto:")) and not any(c in href for c in "<>\"' \x00")


@pytest.mark.parametrize("payload", CORPUS, ids=IDS)
def test_comments(payload):
    story = make_story()
    user = make_user("c@example.com")
    c = APIClient()
    login(c, user.email)
    r = c.post(comments_url(story), {"body": f"hi {payload}"}, format="json")
    assert_json_safe(r)
    assert r.status_code in (201, 202, 400)
    listing = APIClient().get(comments_url(story))
    assert_json_safe(listing)
    for row in listing.json()["data"]:
        # whatever is stored is data in a JSON string; the renderer (React) escapes it as text
        assert isinstance(row["body"], str)


@pytest.mark.parametrize("payload", CORPUS, ids=IDS)
def test_display_names_and_bios(payload):
    user = make_user("p@example.com")
    c = APIClient()
    login(c, user.email)
    r = c.patch("/api/v1/auth/me/", {"display_name": f"Ann {payload}"[:80], "bio": payload}, format="json")
    assert_json_safe(r)
    if r.status_code == 200:
        data = r.json()["data"]
        assert inert(data["display_name"]) and inert(data["bio"])
    else:
        assert r.status_code == 400
        user.profile.refresh_from_db()
        assert user.profile.display_name != f"Ann {payload}"[:80] or inert(user.profile.display_name)
    reg = APIClient().post("/api/v1/auth/register/", {"email": "newbie@example.com", "password": PASSWORD, "display_name": payload[:80]}, format="json")
    assert reg.status_code in (202, 400)


@pytest.mark.parametrize("payload", CORPUS, ids=IDS)
def test_media_text(staff_client, media_root, payload):
    asset = upload(staff_client, make_image("PNG")).json()["data"][0]
    url = f"/api/v1/admin/media/{asset['id']}/"
    r = staff_client.patch(url, {"alt_text": payload[:300], "caption": payload[:500]}, format="json")
    assert_json_safe(r)
    if r.status_code == 200:
        d = r.json()["data"]
        assert inert(d["alt_text"]) and inert(d["caption"])
    else:
        assert r.status_code == 400
    # the file name is never user-controlled either
    r = upload(staff_client, make_image("PNG", name=f"{payload[:40]}.png"))
    assert r.status_code in (201, 400)
    if r.status_code == 201:
        assert inert(r.json()["data"][0]["original_name"])


@pytest.mark.parametrize("payload", CORPUS, ids=IDS)
def test_search_reflects_nothing_as_html(payload):
    Story.objects.all().delete()
    make_story("Plain story")
    r = APIClient().get("/api/v1/search/", {"q": payload})
    assert_json_safe(r)
    assert r.status_code in (200, 400)
    assert "text/html" not in r["Content-Type"]


@pytest.mark.parametrize("payload", CORPUS, ids=IDS)
def test_emails_the_backend_builds_carry_no_markup(client, mailoutbox, payload):
    """The only HTML-capable output the backend generates is e-mail. Hostile names are refused or cleaned at the door,
    and the messages are plain text (no HTML alternative), so a name has nowhere to become markup."""
    client.post("/api/v1/auth/register/", {"email": "mailme@example.com", "password": PASSWORD, "display_name": payload[:80]}, format="json")
    client.post("/api/v1/auth/password/reset/", {"email": "mailme@example.com"}, format="json")
    for message in mailoutbox:
        assert not getattr(message, "alternatives", [])
        assert "<script" not in message.body.lower()
