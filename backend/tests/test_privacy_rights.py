"""Phase 10: download my data, delete my account, sessions, profile text, enumeration safety, consent mode."""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.comments.models import Comment, CommentReport
from apps.reactions.models import Like
from apps.reactions.services import like_story

from .analytics_helpers import new_id
from .conftest import PASSWORD, register_payload
from .engagement_helpers import add_comment, make_story, make_user
from .security_helpers import enrol, login

User = get_user_model()
ME = "/api/v1/auth/me/"


def logged_in(email="reader@example.com", **kw):
    user = make_user(email, **kw)
    c = APIClient()
    assert login(c, email).status_code == 200
    return user, c


# ---- export -------------------------------------------------------------------------
def test_export_requires_login(client):
    assert client.get(ME + "export/").status_code in (401, 403)


def test_export_contains_my_data_and_nothing_secret():
    user, c = logged_in()
    story = make_story("Loved story")
    add_comment(story, user, "My comment", status="approved")
    add_comment(story, user, "Hidden one", status="hidden")
    like_story(user, story)
    other = make_user("other@example.com")
    CommentReport.objects.create(comment=add_comment(story, other, "x"), user=user, reason="spam")
    r = c.get(ME + "export/")
    assert r.status_code == 200 and r["Cache-Control"] == "no-store"
    data = r.json()["data"]
    assert data["account"]["email"] == "reader@example.com"
    assert {x["body"]: x["status"] for x in data["comments"]} == {"My comment": "approved", "Hidden one": "hidden"}
    assert data["likes"][0]["story"] == "Loved story"
    assert data["reports_made"][0]["reason"] == "spam"
    assert data["security"]["two_step_verification_enabled"] is False
    assert data["consent"]["stored_on_server"] is False
    text = json.dumps(data)
    assert "pbkdf2" not in text and "other@example.com" not in text  # nobody else's email, no hashes


def test_export_is_throttled(settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "data_export": "2/hour"}}
    from rest_framework.throttling import ScopedRateThrottle

    ScopedRateThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    _, c = logged_in()
    assert [c.get(ME + "export/").status_code for _ in range(3)] == [200, 200, 429]


# ---- deletion (anonymisation) -------------------------------------------------------
def test_delete_needs_the_right_password():
    user, c = logged_in()
    assert c.delete(ME, {}, format="json").status_code == 400
    assert c.delete(ME, {"password": "wrong-Password-1"}, format="json").status_code == 400
    user.refresh_from_db()
    assert user.is_active and user.email == "reader@example.com"


def test_delete_anonymises_and_keeps_counters_correct():
    user, c = logged_in()
    story = make_story()
    other = make_user("other@example.com")
    top = add_comment(story, user, "Top level", status="approved")
    add_comment(story, other, "A reply", status="approved", parent=top)
    add_comment(story, user, "Waiting", status="pending")
    like_story(user, story)
    like_story(other, story)
    CommentReport.objects.create(comment=add_comment(story, other, "x"), user=user, reason="spam")
    profile = user.profile
    profile.bio = "About me"
    profile.save()

    r = c.delete(ME, {"password": PASSWORD}, format="json")
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.email == f"deleted-{user.pk}@invalid.invalid" and user.is_active is False
    assert not user.has_usable_password() and user.profile.display_name == "Deleted user" and user.profile.bio == ""
    assert not Like.objects.filter(user=user).exists() and not CommentReport.objects.filter(user=user).exists()
    assert set(Comment.objects.filter(user=user).values_list("status", flat=True)) == {"deleted"}
    assert c.get(ME).json()["data"] is None  # logged out
    assert login(APIClient(), f"deleted-{user.pk}@invalid.invalid").status_code == 400
    assert login(APIClient(), "reader@example.com").status_code == 400

    story.refresh_from_db()
    counts = (story.like_count, story.comment_count)
    call_command("recount_engagement")
    story.refresh_from_db()
    assert counts == (story.like_count, story.comment_count)  # the stored counters already matched the real data
    assert story.like_count == 1


def test_delete_is_audited_and_old_entries_lose_the_name():
    user = make_user("staffer@example.com", staff=True)
    c = APIClient()
    login(c, "staffer@example.com")
    assert AuditLog.objects.filter(action="auth.staff_login").exists()
    assert c.delete(ME, {"password": PASSWORD}, format="json").status_code == 200
    assert AuditLog.objects.filter(action="user.anonymised").exists()
    assert not AuditLog.objects.filter(actor=user).exclude(actor_label="Deleted user").exists()


def test_the_last_superuser_cannot_delete_themselves(superuser):
    c = APIClient()
    login(c, "boss@example.com")
    r = c.delete(ME, {"password": PASSWORD}, format="json")
    assert r.status_code == 400
    superuser.refresh_from_db()
    assert superuser.is_active and superuser.email == "boss@example.com"


def test_a_second_superuser_may_delete_their_account(superuser):
    User.objects.create_superuser(email="second@example.com", password=PASSWORD)
    c = APIClient()
    login(c, "second@example.com")
    assert c.delete(ME, {"password": PASSWORD}, format="json").status_code == 200


def test_google_only_accounts_confirm_with_their_email():
    user = User.objects.create_user(email="g@example.com", password=None)
    assert not user.has_usable_password()
    c = APIClient()
    c.force_login(user)
    assert c.delete(ME, {"email": "nope@example.com"}, format="json").status_code == 400
    assert c.delete(ME, {"email": "G@example.com "}, format="json").status_code == 200


def test_deletion_needs_a_fresh_code_when_two_step_is_on(monkeypatch):
    from apps.accounts import totp

    user = make_user("staffer@example.com", staff=True)
    secret, _ = enrol(user)
    c = APIClient()
    login(c, "staffer@example.com")
    assert c.delete(ME, {"password": PASSWORD}, format="json").status_code in (400, 403)
    user.refresh_from_db()
    assert user.is_active


def test_deletion_is_throttled(settings):
    from rest_framework.throttling import ScopedRateThrottle

    rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "account_delete": "2/hour"}
    ScopedRateThrottle.THROTTLE_RATES = rates
    _, c = logged_in()
    codes = [c.delete(ME, {"password": "wrong-Password-1"}, format="json").status_code for _ in range(3)]
    assert codes == [400, 400, 429]


# ---- sessions -----------------------------------------------------------------------
def test_session_list_has_no_ip_or_user_agent():
    user = make_user()
    c1, c2 = APIClient(), APIClient()
    c1.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json", HTTP_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64; rv:1) Gecko/2010 Firefox/120.0 SECRET-AGENT-TEXT", REMOTE_ADDR="203.0.113.9")
    login(c2, user.email)
    r = c1.get("/api/v1/auth/sessions/")
    rows = r.json()["data"]
    assert len(rows) == 2 and sum(row["current"] for row in rows) == 1
    body = r.content.decode()
    assert "SECRET-AGENT-TEXT" not in body and "203.0.113.9" not in body
    assert any(row["device"] == "Firefox on Linux" for row in rows)
    assert all(set(row) == {"id", "device", "created_at", "last_seen_at", "current"} for row in rows)


def test_revoke_all_signs_out_every_other_device_but_keeps_this_one():
    user = make_user()
    a, b, c3 = APIClient(), APIClient(), APIClient()
    for c in (a, b, c3):
        login(c, user.email)
    r = a.post("/api/v1/auth/sessions/revoke-all/")
    assert r.status_code == 200
    assert a.get(ME).json()["data"] is not None  # "this device" stays signed in
    assert b.get(ME).json()["data"] is None and c3.get(ME).json()["data"] is None


def test_session_id_changes_on_login_and_logout():
    user = make_user()
    c = APIClient()
    c.get("/api/v1/auth/csrf/")
    before = c.cookies.get("sessionid").value if "sessionid" in c.cookies else None
    login(c, user.email)
    during = c.cookies["sessionid"].value
    assert during != before
    c.post("/api/v1/auth/logout/")
    after = c.cookies["sessionid"].value if "sessionid" in c.cookies else ""
    assert after != during


def test_changing_the_password_signs_out_other_sessions_and_rotates_this_one():
    user = make_user()
    a, b = APIClient(), APIClient()
    login(a, user.email)
    login(b, user.email)
    key_before = a.cookies["sessionid"].value
    r = a.post("/api/v1/auth/password/change/", {"current_password": PASSWORD, "new_password": "Another-long-pass-77"}, format="json")
    assert r.status_code == 200
    assert a.cookies["sessionid"].value != key_before
    assert a.get(ME).json()["data"] is not None and b.get(ME).json()["data"] is None


def test_staff_sessions_expire_when_idle(settings, monkeypatch):
    from apps.accounts import sessions as session_mod

    settings.STAFF_SESSION_IDLE_MINUTES = 10
    staff = make_user("staffer@example.com", staff=True)
    reader = make_user("reader@example.com")
    cs, cr = APIClient(), APIClient()
    login(cs, staff.email)
    login(cr, reader.email)
    assert cs.get(ME).json()["data"] is not None
    for client in (cs, cr):  # pretend the last request was 11 minutes ago
        sid = client.cookies["sessionid"].value
        from django.contrib.sessions.backends.db import SessionStore

        store = SessionStore(session_key=sid)
        store[session_mod.ACTIVITY_KEY] = timezone.now().timestamp() - 11 * 60
        store.save()
    assert cs.get(ME).json()["data"] is None  # staff: ended
    assert cr.get(ME).json()["data"] is not None  # readers keep the normal session age


def test_active_staff_stay_signed_in(settings):
    settings.STAFF_SESSION_IDLE_MINUTES = 10
    staff = make_user("staffer@example.com", staff=True)
    c = APIClient()
    login(c, staff.email)
    for _ in range(3):
        assert c.get(ME).json()["data"] is not None


# ---- profile text -------------------------------------------------------------------
@pytest.mark.parametrize("field,value", [("display_name", "<b>Bob</b>"), ("bio", "hi <script>x</script>"), ("display_name", "a > b"), ("display_name", "   ")])
def test_markup_and_blank_names_are_refused(field, value):
    _, c = logged_in()
    assert c.patch(ME, {field: value}, format="json").status_code == 400


def test_control_and_disguising_characters_are_removed():
    user, c = logged_in()
    r = c.patch(ME, {"display_name": "Ann\x00‮evil  Name\x07", "bio": "line1\r\n\x00line2 "}, format="json")
    assert r.status_code == 200
    user.profile.refresh_from_db()
    assert user.profile.display_name == "Annevil Name"
    assert "\x00" not in user.profile.bio and " " not in user.profile.bio and "line1\nline2" == user.profile.bio


def test_length_limits_are_enforced():
    _, c = logged_in()
    assert c.patch(ME, {"display_name": "x" * 81}, format="json").status_code == 400
    assert c.patch(ME, {"bio": "x" * 501}, format="json").status_code == 400


# ---- enumeration --------------------------------------------------------------------
def test_register_answers_the_same_for_new_and_existing_addresses(client, mailoutbox):
    make_user("taken@example.com")
    new = client.post("/api/v1/auth/register/", register_payload("fresh@example.com"), format="json")
    old = client.post("/api/v1/auth/register/", register_payload("taken@example.com"), format="json")
    assert new.status_code == old.status_code == 202
    assert new.json() == old.json()
    recipients = {tuple(m.to): m.subject for m in mailoutbox}
    assert ("taken@example.com",) in recipients and "tried to sign up" in recipients[("taken@example.com",)]
    assert User.objects.filter(email="taken@example.com").count() == 1


def test_login_gives_one_message_for_every_failure(client, db):
    make_user("real@example.com")
    inactive = make_user("off@example.com")
    inactive.is_active = False
    inactive.save()
    answers = {
        (r.status_code, json.dumps(r.json(), sort_keys=True))
        for r in (
            client.post("/api/v1/auth/login/", {"email": "nobody@example.com", "password": "Whatever-1234"}, format="json"),
            client.post("/api/v1/auth/login/", {"email": "real@example.com", "password": "Wrong-password-1"}, format="json"),
            client.post("/api/v1/auth/login/", {"email": "off@example.com", "password": PASSWORD}, format="json"),
        )
    }
    assert len(answers) == 1


def test_reset_and_resend_do_not_reveal_accounts(client, db):
    make_user("real@example.com")
    a = client.post("/api/v1/auth/password/reset/", {"email": "real@example.com"}, format="json")
    b = client.post("/api/v1/auth/password/reset/", {"email": "nobody@example.com"}, format="json")
    assert (a.status_code, a.json()) == (b.status_code, b.json())
    a = client.post("/api/v1/auth/email/resend/", {"email": "real@example.com"}, format="json")
    b = client.post("/api/v1/auth/email/resend/", {"email": "nobody@example.com"}, format="json")
    assert a.status_code == b.status_code and a.json().get("message") == b.json().get("message")


# ---- consent mode in the collector ---------------------------------------------------
def _collect(client, **extra):
    """Like the browser tracker: the optional consent flag travels in the JSON body."""
    from .analytics_helpers import COLLECT, DESKTOP_UA

    body = {"path": "/", "visitor_id": new_id(), "session_id": new_id(), "referrer": "", **extra}
    return client.post(COLLECT, body, format="json", HTTP_USER_AGENT=DESKTOP_UA)


def test_opt_in_mode_ignores_events_without_explicit_consent(client, settings):
    from apps.analytics.models import PageViewEvent

    settings.PRIVACY_CONSENT_MODE = "opt_in"
    assert _collect(client).status_code in (200, 204)
    assert _collect(client, consent=False).status_code in (200, 204)
    assert _collect(client, consent="true").status_code in (200, 204)  # a string is not an explicit true
    assert PageViewEvent.objects.count() == 0
    _collect(client, consent=True)
    assert PageViewEvent.objects.count() == 1


@pytest.mark.parametrize("mode", ["notice", "opt_out"])
def test_other_modes_count_without_a_consent_flag(client, settings, mode):
    from apps.analytics.models import PageViewEvent

    settings.PRIVACY_CONSENT_MODE = mode
    _collect(client)
    assert PageViewEvent.objects.count() == 1
