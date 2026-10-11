"""Audit log: every listed action is recorded with safe metadata; append-only; transactional; read-only API; retention."""
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit import service as audit
from apps.audit.actions import ACTIONS
from apps.audit.models import AuditImmutableError, AuditLog
from apps.audit.retention import purge
from apps.comments.models import CommentReport
from apps.stories.models import Story

from .analytics_helpers import at, event
from .conftest import PASSWORD
from .engagement_helpers import add_comment, make_story, make_user
from .media_helpers import make_image
from .security_helpers import enrol, fake_clock, login, verify

API = "/api/v1/"
ADMIN = API + "admin/"
LOGS = ADMIN + "audit-logs/"
APPS = Path(__file__).resolve().parents[1] / "apps"

pytestmark = pytest.mark.django_db


def doc(text="Hello"):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


def actions():
    return list(AuditLog.objects.order_by("id").values_list("action", flat=True))


def last(action):
    return AuditLog.objects.filter(action=action).order_by("-id").first()


# ---------------------------------------------------------------- every action writes one entry
def test_story_actions_are_recorded(staff_client, staff):
    story = staff_client.post(ADMIN + "stories/", {"title": "Alpha", "content_json": doc()}, format="json").json()["data"]
    sid = story["id"]
    assert last("story.create").metadata == {"title": "Alpha", "status": "draft"}
    assert last("story.create").actor == staff and last("story.create").object_id == str(sid) and last("story.create").object_type == "story"

    staff_client.patch(f"{ADMIN}stories/{sid}/", {"title": "Alpha 2", "content_json": doc("Changed")}, format="json")
    entry = last("story.update")
    assert entry.metadata["title"] == "Alpha 2" and set(entry.metadata["fields"]) == {"title", "content_json"}
    assert "Changed" not in str(entry.metadata)  # never the story body

    staff_client.patch(f"{ADMIN}stories/{sid}/?autosave=1", {"title": "Alpha 3"}, format="json")
    assert AuditLog.objects.filter(action="story.update").count() == 1  # autosaves are not audited

    staff_client.post(f"{ADMIN}stories/{sid}/publish/")
    assert last("story.publish").metadata["status_from"] == "draft" and last("story.publish").metadata["status_to"] == "published"
    staff_client.post(f"{ADMIN}stories/{sid}/unpublish/")
    assert last("story.unpublish").metadata["status_to"] == "draft"
    when = (timezone.now() + timedelta(days=2)).isoformat()
    staff_client.post(f"{ADMIN}stories/{sid}/schedule/", {"scheduled_at": when}, format="json")
    assert last("story.schedule").metadata["status_to"] == "scheduled"
    staff_client.post(f"{ADMIN}stories/{sid}/archive/")
    assert last("story.archive").metadata["status_to"] == "archived"
    first_revision = staff_client.get(f"{ADMIN}stories/{sid}/revisions/").json()["data"][-1]["id"]
    staff_client.post(f"{ADMIN}stories/{sid}/revisions/{first_revision}/restore/")
    assert last("story.restore_revision").object_id == str(sid)
    staff_client.delete(f"{ADMIN}stories/{sid}/")
    gone = last("story.delete")
    assert gone.object_id == str(sid) and gone.metadata["title"]
    assert not Story.objects.filter(pk=sid).exists()


def test_category_and_tag_actions_are_recorded(staff_client):
    for kind in ("categories", "tags"):
        prefix = "category" if kind == "categories" else "tag"
        obj = staff_client.post(f"{ADMIN}{kind}/", {"name": "Thing"}, format="json").json()["data"]
        assert last(f"{prefix}.create").metadata["name"] == "Thing"
        staff_client.patch(f"{ADMIN}{kind}/{obj['id']}/", {"name": "Thing 2"}, format="json")
        assert last(f"{prefix}.update").metadata["name"] == "Thing 2"
        staff_client.delete(f"{ADMIN}{kind}/{obj['id']}/")
        assert last(f"{prefix}.delete").object_id == str(obj["id"])


def test_media_actions_are_recorded(staff_client):
    r = staff_client.post(ADMIN + "media/", {"files": make_image("PNG")}, format="multipart")
    assert r.status_code == 201
    media_id = r.json()["data"][0]["id"]
    entry = last("media.upload")
    assert entry.object_type == "media" and entry.object_id == str(media_id) and entry.metadata["mime_type"] == "image/png"
    staff_client.patch(f"{ADMIN}media/{media_id}/", {"alt_text": "A red square"}, format="json")
    assert last("media.update").metadata["fields"] == ["alt_text"] and "red square" not in str(last("media.update").metadata)
    staff_client.post(f"{ADMIN}media/{media_id}/replace/", {"file": make_image("JPEG")}, format="multipart")
    assert last("media.replace").metadata["mime_type"] == "image/jpeg"
    staff_client.delete(f"{ADMIN}media/{media_id}/")
    assert last("media.delete").object_id == str(media_id)


def test_comment_actions_are_recorded(staff_client, staff):
    story = make_story()
    reader = make_user("reader@example.com")
    comment = add_comment(story, reader, "A comment with private words")
    CommentReport.objects.create(comment=comment, user=make_user("other@example.com"), reason="rude")
    staff_client.patch(f"{ADMIN}comments/{comment.id}/", {"status": "hidden"}, format="json")
    entry = last("comment.status")
    assert entry.metadata["status_from"] == "approved" and entry.metadata["status_to"] == "hidden"
    assert "private words" not in str(entry.metadata)
    staff_client.post(f"{ADMIN}comments/{comment.id}/dismiss-reports/")
    assert last("comment.reports_dismissed").metadata["dismissed"] == 1
    staff_client.patch(ADMIN + "comment-settings/", {"comment_moderation": "approve_first"}, format="json")
    assert last("settings.comment_moderation").metadata == {"mode_from": "off", "mode_to": "approve_first"}
    staff_client.patch(ADMIN + "comment-settings/", {"comment_moderation": "approve_first"}, format="json")
    assert AuditLog.objects.filter(action="settings.comment_moderation").count() == 1  # no change, no entry


def test_analytics_purge_is_recorded_for_command_and_task(settings):
    settings.ANALYTICS_RETENTION_DAYS = 40
    event(1, at(date.today() - timedelta(days=200)))
    call_command("purge_analytics")
    entry = last("analytics.purge")
    assert entry and entry.metadata["events"] == 1 and entry.actor is None and entry.actor_label == "system"
    event(2, at(date.today() - timedelta(days=210)))
    from apps.analytics.tasks import purge_old

    purge_old()
    assert AuditLog.objects.filter(action="analytics.purge").count() == 2
    call_command("purge_analytics")  # nothing left to purge: no noise
    assert AuditLog.objects.filter(action="analytics.purge").count() == 2


def test_user_management_actions_are_recorded(superuser_client, superuser):
    target = make_user("target@example.com")
    superuser_client.patch(f"{ADMIN}users/{target.pk}/", {"is_active": False}, format="json")
    assert last("user.update").metadata["changes"] == {"is_active": [True, False]} and last("user.update").object_id == str(target.pk)
    assert "target@example.com" not in str(last("user.update").metadata)
    superuser_client.post(f"{ADMIN}users/{target.pk}/revoke-sessions/")
    assert last("user.sessions_revoked").object_id == str(target.pk)
    again = make_user("again@example.com", verified=False)
    superuser_client.post(f"{ADMIN}users/{again.pk}/resend-verification/")
    assert last("user.verification_resent").object_id == str(again.pk)


def test_account_deletion_is_recorded(client, user):
    login(client, user.email)
    client.delete(API + "auth/me/", {"password": PASSWORD}, format="json")
    entry = last("user.anonymised")
    assert entry.object_id == str(user.pk) and entry.actor_label == "Deleted user"


def test_login_and_mfa_events_are_recorded(client, staff, monkeypatch):
    client.post(API + "auth/login/", {"email": staff.email, "password": "wrong-password-1"}, format="json")
    assert last("auth.staff_login_failed").actor == staff
    secret, codes = enrol(staff)
    fake_clock(monkeypatch, 1_800_000_030)
    login(client, staff.email)
    assert AuditLog.objects.filter(action="auth.staff_login", actor=staff).count() == 1
    client.post(API + "auth/mfa/verify/", {"recovery_code": codes[0]}, format="json")
    assert last("mfa.recovery_used")
    client.post(API + "auth/password/change/", {"current_password": PASSWORD, "new_password": "Brand-new-passphrase-42", "code": codes[1]}, format="json")
    assert last("auth.password_changed").actor == staff


def test_reader_logins_are_not_audited(client, user):
    login(client, user.email)
    client.post(API + "auth/login/", {"email": user.email, "password": "wrong-password-1"}, format="json")
    assert AuditLog.objects.count() == 0


def test_purging_the_audit_log_is_recorded_once():
    AuditLog.objects.create(action="story.create", actor_label="x", created_at=timezone.now() - timedelta(days=500))
    purge()
    assert actions() == ["audit.purge"]


def test_every_catalog_action_is_written_by_real_code():
    source = "\n".join(p.read_text() for p in APPS.rglob("*.py") if "tests" not in p.parts and p.name != "actions.py")
    for name in ACTIONS:
        prefix, _, suffix = name.partition(".")
        literal = f'"{name}"' in source
        templated = f'audit_prefix = "{prefix}"' in source and f'.{suffix}"' in source
        assert literal or templated, f"{name} is in the catalog but nothing writes it"
    assert all(re.fullmatch(r"[a-z_]+\.[a-z_]+", name) for name in ACTIONS)


# ---------------------------------------------------------------- metadata and IP safety
def test_sensitive_metadata_is_dropped_and_long_values_cut():
    entry = audit.log(None, "story.update", None, title="T", password="pw", token="tk", new_password="n", content="BODY", body="B",
                      session_key="s", recovery_code="r", authorization="a", cookie="c", text="t", nested={"secret": 1, "ok": 2}, long="x" * 999)
    assert set(entry.metadata) == {"title", "nested", "long"}
    assert entry.metadata["nested"] == {"ok": 2} and len(entry.metadata["long"]) == 200


def test_metadata_is_always_json_safe():
    entry = audit.log(None, "story.update", None, when=timezone.now(), ids={3, 1, 2}, obj=object(), deep={"a": {"b": {"c": {"d": 1}}}})
    AuditLog.objects.get(pk=entry.pk)  # round-trips through the database
    assert entry.metadata["ids"] == [1, 2, 3]


def test_the_ip_is_stored_only_as_a_keyed_hash(staff_client, staff):
    c = APIClient(REMOTE_ADDR="203.0.113.9")
    c.force_authenticate(staff)
    c.post(ADMIN + "tags/", {"name": "ip"}, format="json")
    c.post(ADMIN + "tags/", {"name": "ip2"}, format="json")
    first, second = AuditLog.objects.order_by("id")
    assert re.fullmatch(r"[0-9a-f]{64}", first.ip_hash) and first.ip_hash == second.ip_hash
    assert "203.0.113.9" not in first.ip_hash
    for entry in AuditLog.objects.all():
        assert "203.0.113.9" not in repr(entry.__dict__)
    assert audit.hash_ip("203.0.113.9") != audit.hash_ip("203.0.113.10") and audit.hash_ip("") == ""


# ---------------------------------------------------------------- append-only
def test_entries_cannot_be_changed_or_deleted():
    entry = AuditLog.objects.create(action="story.create", actor_label="x")
    entry.action = "story.delete"
    with pytest.raises(AuditImmutableError):
        entry.save()
    with pytest.raises(AuditImmutableError):
        entry.delete()
    with pytest.raises(AuditImmutableError):
        AuditLog.objects.all().delete()
    with pytest.raises(AuditImmutableError):
        AuditLog.objects.filter(pk=entry.pk).update(action="x")
    with pytest.raises(AuditImmutableError):
        AuditLog.objects.bulk_update([entry], ["action"])
    assert AuditLog.objects.get(pk=entry.pk).action == "story.create"


def test_the_api_is_read_only(staff_client):
    entry = AuditLog.objects.create(action="story.create", actor_label="x")
    for method in ("post", "put", "patch", "delete"):
        assert getattr(staff_client, method)(LOGS).status_code == 405, method
    assert staff_client.get(f"{LOGS}{entry.pk}/").status_code == 404
    assert staff_client.delete(f"{LOGS}{entry.pk}/").status_code == 404


def test_only_staff_can_read_the_log(client, user, staff_client):
    assert client.get(LOGS).status_code in (401, 403)
    client.force_authenticate(user)
    assert client.get(LOGS).status_code == 403
    assert staff_client.get(LOGS).status_code == 200


# ---------------------------------------------------------------- transactions
def test_nothing_is_written_when_the_action_fails(staff_client):
    r = staff_client.post(ADMIN + "stories/", {"title": "x", "content_json": {"type": "script"}}, format="json")
    assert r.status_code == 400 and AuditLog.objects.count() == 0
    assert staff_client.post(ADMIN + "stories/999999/publish/").status_code == 404 and AuditLog.objects.count() == 0
    staff_client.post(ADMIN + "stories/", {"title": "ok", "content_json": doc()}, format="json")
    empty = staff_client.post(ADMIN + "stories/", {"title": "", "content_json": doc()}, format="json")
    count = AuditLog.objects.count()
    sid = Story.objects.get().pk
    Story.objects.filter(pk=sid).update(title="")
    assert staff_client.post(f"{ADMIN}stories/{sid}/publish/").status_code == 400
    assert AuditLog.objects.count() == count and empty.status_code in (201, 400)


def test_a_rolled_back_transaction_takes_its_entry_with_it():
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            audit.log(None, "story.create", None, title="never happened")
            raise RuntimeError("the action failed")
    assert AuditLog.objects.count() == 0
    with transaction.atomic():
        audit.log(None, "story.create", None, title="happened")
    assert AuditLog.objects.count() == 1


def test_a_failing_audit_write_never_breaks_the_action(staff_client, monkeypatch):
    class Broken:
        class objects:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("audit database is down")

    monkeypatch.setattr(audit, "AuditLog", Broken)
    r = staff_client.post(ADMIN + "stories/", {"title": "Still saved", "content_json": doc()}, format="json")
    assert r.status_code == 201 and Story.objects.filter(title="Still saved").exists()
    assert audit.log(None, "story.create", None) is None  # swallowed, not raised


def test_a_database_error_inside_the_audit_write_does_not_poison_the_callers_transaction(monkeypatch):
    from django.db import IntegrityError

    def explode(**kwargs):
        raise IntegrityError("simulated")

    monkeypatch.setattr(AuditLog.objects, "create", explode)
    with transaction.atomic():
        assert audit.log(None, "story.create", None) is None
        Story.objects.create(title="still works", content_json=doc())
    assert Story.objects.filter(title="still works").exists()


# ---------------------------------------------------------------- listing and filters
@pytest.fixture
def entries(staff, superuser):
    now = timezone.now()
    rows = [
        ("story.create", staff, "story", "1", now - timedelta(days=10), "Alpha Writer"),
        ("story.publish", staff, "story", "1", now - timedelta(days=5), "Alpha Writer"),
        ("tag.create", superuser, "tag", "7", now - timedelta(days=2), "The Boss"),
        ("user.update", superuser, "user", "42", now - timedelta(hours=1), "The Boss"),
    ]
    return [AuditLog.objects.create(action=a, actor=u, object_type=t, object_id=i, created_at=c, actor_label=l) for a, u, t, i, c, l in rows]


def ids(client, **params):
    r = client.get(LOGS, params)
    assert r.status_code == 200, r.content
    return [row["action"] for row in r.json()["data"]]


def test_list_is_newest_first_and_paginated(staff_client, entries):
    r = staff_client.get(LOGS).json()
    assert [row["action"] for row in r["data"]] == ["user.update", "tag.create", "story.publish", "story.create"]
    assert r["pagination"]["count"] == 4
    row = r["data"][0]
    assert set(row) == {"id", "created_at", "actor", "actor_label", "action", "action_label", "object_type", "object_id", "metadata", "ip_ref"}
    assert row["action_label"] == ACTIONS["user.update"]


def test_filters(staff_client, entries, staff, superuser):
    assert ids(staff_client, action="story.create") == ["story.create"]
    assert ids(staff_client, action="story.*") == ["story.publish", "story.create"]
    assert ids(staff_client, actor=staff.pk) == ["story.publish", "story.create"]
    assert ids(staff_client, object_type="tag") == ["tag.create"]
    assert ids(staff_client, object_type="story", object_id="1") == ["story.publish", "story.create"]
    assert ids(staff_client, q="boss") == ["user.update", "tag.create"]
    assert ids(staff_client, q="42") == ["user.update"]
    today = timezone.now().date()
    assert ids(staff_client, **{"from": (today - timedelta(days=3)).isoformat()}) == ["user.update", "tag.create"]
    assert ids(staff_client, to=(today - timedelta(days=6)).isoformat()) == ["story.create"]
    assert ids(staff_client, **{"from": (today - timedelta(days=6)).isoformat(), "to": (today - timedelta(days=4)).isoformat()}) == ["story.publish"]
    assert staff_client.get(LOGS, {"from": "yesterday"}).status_code == 400
    assert staff_client.get(LOGS, {"actor": "abc"}).status_code == 400


def test_a_deleted_accounts_name_is_not_shown(staff_client, user, entries):
    AuditLog.objects.create(action="comment.status", actor=user, actor_label="reader", object_type="comment", object_id="3")
    user.email = f"deleted-{user.pk}@invalid.invalid"
    user.save()
    row = next(r for r in staff_client.get(LOGS, {"action": "comment.status"}).json()["data"])
    assert row["actor_label"] == "Deleted user"


# ---------------------------------------------------------------- retention
def test_purge_removes_only_old_entries(settings):
    settings.AUDIT_RETENTION_DAYS = 100
    old = AuditLog.objects.create(action="story.create", actor_label="a", created_at=timezone.now() - timedelta(days=101))
    new = AuditLog.objects.create(action="story.create", actor_label="a", created_at=timezone.now() - timedelta(days=99))
    summary = purge()
    assert summary["entries"] == 1
    assert not AuditLog.objects.filter(pk=old.pk).exists() and AuditLog.objects.filter(pk=new.pk).exists()
    assert AuditLog.objects.filter(action="audit.purge").count() == 1


def test_dry_run_changes_nothing(settings):
    AuditLog.objects.create(action="story.create", actor_label="a", created_at=timezone.now() - timedelta(days=999))
    assert purge(dry_run=True)["entries"] == 1 and AuditLog.objects.count() == 1


def test_retention_never_drops_below_30_days(settings):
    settings.AUDIT_RETENTION_DAYS = 1
    AuditLog.objects.create(action="story.create", actor_label="a", created_at=timezone.now() - timedelta(days=20))
    assert purge()["entries"] == 0


def test_the_command_and_the_celery_job(settings, capsys):
    settings.AUDIT_RETENTION_DAYS = 60
    AuditLog.objects.create(action="story.create", actor_label="a", created_at=timezone.now() - timedelta(days=90))
    call_command("purge_audit_logs", "--dry-run")
    assert AuditLog.objects.count() == 1
    call_command("purge_audit_logs")
    assert actions() == ["audit.purge"]
    from apps.audit.tasks import purge_old_entries
    from config.celery import app

    assert purge_old_entries()["entries"] == "0"
    assert app.conf.beat_schedule["audit-purge-old"]["task"] == "apps.audit.tasks.purge_old_entries"
