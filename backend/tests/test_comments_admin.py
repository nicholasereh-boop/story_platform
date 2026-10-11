"""Staff moderation API: permissions, listing filters, status changes, reports and the moderation setting."""
import pytest

from apps.comments import services
from apps.comments.models import Comment, CommentReport

from .engagement_helpers import BASE, add_comment, client_for, make_story, make_user, reload_counts

pytestmark = pytest.mark.django_db

ADMIN = BASE + "admin/"


@pytest.fixture
def staff_user():
    return make_user("staff@example.com", staff=True)


@pytest.fixture
def admin(staff_user):
    return client_for(staff_user)


def test_every_admin_endpoint_rejects_non_staff_and_anonymous():
    story, reader = make_story(), make_user()
    comment = add_comment(story, reader)
    calls = [
        ("get", "comments/"), ("patch", f"comments/{comment.id}/"), ("get", f"comments/{comment.id}/reports/"),
        ("post", f"comments/{comment.id}/dismiss-reports/"), ("get", "comment-settings/"), ("patch", "comment-settings/"),
    ]
    for who in (client_for(reader), client_for()):
        for method, path in calls:
            r = getattr(who, method)(ADMIN + path, {"status": "hidden", "comment_moderation": "off"}, format="json") if method in ("patch", "post") else getattr(who, method)(ADMIN + path)
            assert r.status_code in (401, 403), (method, path)
    comment.refresh_from_db()
    assert comment.status == "approved" and services.get_moderation_mode() == "off"


def test_list_shape_includes_story_author_and_report_count(admin):
    story = make_story("Moon story")
    author = make_user("writer@example.com")
    comment = add_comment(story, author, "Hello")
    CommentReport.objects.create(comment=comment, user=make_user("r1@example.com"), reason="a")
    CommentReport.objects.create(comment=comment, user=make_user("r2@example.com"), reason="b")
    r = admin.get(ADMIN + "comments/")
    item = r.json()["data"][0]
    assert item["story"] == {"id": story.id, "title": "Moon story", "slug": story.slug}
    assert item["author"] == {"display_name": "writer", "email": "writer@example.com"}
    assert item["report_count"] == 2 and item["status"] == "approved"
    assert set(r.json()["pagination"]) == {"count", "page", "page_size", "total_pages", "has_next", "has_previous"}


def test_list_filters(admin):
    s1, s2 = make_story("One"), make_story("Two")
    ann, bob = make_user("ann@example.com"), make_user("bob@example.com")
    a = add_comment(s1, ann, "alpha words", status="approved")
    b = add_comment(s1, bob, "beta words", status="pending")
    c = add_comment(s2, ann, "gamma", status="hidden")
    CommentReport.objects.create(comment=c, user=bob)

    def got(**params):
        return {i["id"] for i in admin.get(ADMIN + "comments/", params).json()["data"]}

    assert got() == {a.id, b.id, c.id}
    assert got(status="pending") == {b.id}
    assert got(story=s2.id) == {c.id} and got(story=s1.slug) == {a.id, b.id}
    assert got(reported="1") == {c.id}
    assert got(q="beta") == {b.id} and got(q="ANN@") == {a.id, c.id}
    assert admin.get(ADMIN + "comments/", {"status": "bogus"}).status_code == 400


def test_list_is_paginated(admin):
    story, user = make_story(), make_user()
    for i in range(15):
        add_comment(story, user, f"c{i}")
    r = admin.get(ADMIN + "comments/").json()
    assert len(r["data"]) == 12 and r["pagination"]["count"] == 15 and r["pagination"]["has_next"]


def test_patch_changes_status_and_keeps_counts(admin):
    story = make_story()
    comment = add_comment(story, make_user(), "x", status="pending")
    url = f"{ADMIN}comments/{comment.id}/"
    for status, count in [("approved", 1), ("hidden", 0), ("approved", 1), ("deleted", 0)]:
        r = admin.patch(url, {"status": status}, format="json")
        assert r.status_code == 200 and r.json()["data"]["status"] == status
        assert reload_counts(story)[1] == count


def test_patch_accepts_only_approved_hidden_deleted_and_nothing_else(admin):
    comment = add_comment(make_story(), make_user(), "keep me")
    url = f"{ADMIN}comments/{comment.id}/"
    assert admin.patch(url, {"status": "pending"}, format="json").status_code == 400
    assert admin.patch(url, {"status": "bogus"}, format="json").status_code == 400
    assert admin.patch(url, {"body": "edited by staff"}, format="json").status_code == 400
    assert admin.patch(url, {"status": "hidden", "body": "x"}, format="json").status_code == 400
    comment.refresh_from_db()
    assert comment.status == "approved" and comment.body == "keep me"
    assert admin.patch(f"{ADMIN}comments/99999/", {"status": "hidden"}, format="json").status_code == 404


def test_reports_list_and_dismiss_keeps_status(admin):
    story, author = make_story(), make_user()
    comment = add_comment(story, author, "reported")
    CommentReport.objects.create(comment=comment, user=make_user("r1@example.com"), reason="rude")
    CommentReport.objects.create(comment=comment, user=make_user("r2@example.com"), reason="")
    reports = admin.get(f"{ADMIN}comments/{comment.id}/reports/").json()["data"]
    assert [r["reason"] for r in reports] == ["rude", ""]
    assert reports[0]["reporter"]["email"] == "r1@example.com"
    r = admin.post(f"{ADMIN}comments/{comment.id}/dismiss-reports/")
    assert r.status_code == 200 and r.json()["data"] == {"dismissed": 2}
    assert CommentReport.objects.count() == 0
    comment.refresh_from_db()
    assert comment.status == "approved"  # dismissing never changes the status
    assert admin.get(f"{ADMIN}comments/99999/reports/").status_code == 404


def test_moderation_setting_read_and_change(admin):
    assert admin.get(ADMIN + "comment-settings/").json()["data"] == {"comment_moderation": "off"}
    for mode in ("approve_first", "approve_first_time", "off"):
        r = admin.patch(ADMIN + "comment-settings/", {"comment_moderation": mode}, format="json")
        assert r.status_code == 200 and services.get_moderation_mode() == mode
    assert admin.patch(ADMIN + "comment-settings/", {"comment_moderation": "nope"}, format="json").status_code == 400
    assert services.get_moderation_mode() == "off"


def test_pending_comments_filter_supports_the_sidebar_badge(admin):
    story, user = make_story(), make_user()
    add_comment(story, user, "p1", status="pending")
    add_comment(story, user, "p2", status="pending")
    add_comment(story, user, "ok")
    r = admin.get(ADMIN + "comments/", {"status": "pending", "page_size": 1}).json()
    assert r["pagination"]["count"] == 2  # the frontend reads the count from here
