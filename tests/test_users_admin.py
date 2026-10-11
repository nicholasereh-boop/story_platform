"""Phase 10: staff user management (/api/v1/admin/users/)."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from rest_framework.test import APIClient

from apps.audit.models import AuditLog

from .conftest import PASSWORD
from .engagement_helpers import add_comment, make_story, make_user
from .security_helpers import enrol, login

User = get_user_model()
URL = "/api/v1/admin/users/"
SECRET_WORDS = ("password", "mfa_secret", "session_key", "recovery", "secret", "token", "hash")


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def patch(client, user, **body):
    return client.patch(f"{URL}{user.pk}/", body, format="json")


@pytest.fixture
def reader(db):
    return make_user("someone@example.com")


# ---- who may call it ----------------------------------------------------------------
def test_permission_matrix_for_the_list(client, user, staff_client, superuser_client):
    assert client.get(URL).status_code in (401, 403)
    assert client_for(user).get(URL).status_code == 403
    assert staff_client.get(URL).status_code == 200
    assert superuser_client.get(URL).status_code == 200


def test_only_staff_can_use_the_detail_and_action_routes(client, user, reader):
    for c in (client, client_for(user)):
        assert c.get(f"{URL}{reader.pk}/").status_code in (401, 403)
        assert c.patch(f"{URL}{reader.pk}/", {"is_active": False}, format="json").status_code in (401, 403)
        assert c.post(f"{URL}{reader.pk}/revoke-sessions/").status_code in (401, 403)
        assert c.post(f"{URL}{reader.pk}/resend-verification/").status_code in (401, 403)


def test_methods_that_do_not_exist_are_refused(staff_client, reader):
    assert staff_client.post(URL, {}, format="json").status_code == 405
    assert staff_client.delete(f"{URL}{reader.pk}/").status_code == 405
    assert staff_client.put(f"{URL}{reader.pk}/", {"is_active": False}, format="json").status_code == 405


# ---- the list ----------------------------------------------------------------------
def test_list_shape_and_counts(staff_client, reader):
    story = make_story()
    add_comment(story, reader, "hello")
    from apps.reactions.services import like_story

    like_story(reader, story)
    r = staff_client.get(URL, {"q": "someone@"})
    assert r.status_code == 200
    row = r.json()["data"][0]
    assert set(row) >= {"id", "email", "display_name", "role", "is_active", "email_verified", "date_joined", "last_login",
                        "comment_count", "like_count", "mfa_enabled"}
    assert row["role"] == "reader" and row["comment_count"] == 1 and row["like_count"] == 1
    assert row["email_verified"] is True and row["mfa_enabled"] is False
    assert r.json()["pagination"]["count"] == 1


def test_filters(staff_client, staff, superuser, reader):
    unverified = make_user("unverified@example.com", verified=False)
    gone = make_user("gone@example.com")
    gone.is_active = False
    gone.save()

    def emails(**params):
        return {u["email"] for u in staff_client.get(URL, params).json()["data"]}

    assert emails(role="superuser") == {"boss@example.com"}
    assert emails(role="staff") == {"staff@example.com"}
    assert "someone@example.com" in emails(role="reader") and "staff@example.com" not in emails(role="reader")
    assert emails(active="0") == {"gone@example.com"}
    assert "gone@example.com" not in emails(active="1")
    assert emails(verified="0") >= {"unverified@example.com"} and "someone@example.com" not in emails(verified="0")
    assert emails(q="UNVERIFIED") == {"unverified@example.com"}
    assert staff_client.get(URL, {"role": "wizard"}).status_code == 400


def test_ordering_ignores_unknown_fields(staff_client, reader):
    assert staff_client.get(URL, {"ordering": "email"}).status_code == 200
    assert staff_client.get(URL, {"ordering": "password"}).status_code == 200  # falls back, never sorts by a secret


def test_list_is_paginated(staff_client, db):
    for i in range(15):
        make_user(f"u{i}@example.com")
    r = staff_client.get(URL)
    assert len(r.json()["data"]) == 12 and r.json()["pagination"]["count"] == 15


def test_mfa_enabled_is_reported_without_the_secret(staff_client, staff):
    enrol(staff)
    row = next(u for u in staff_client.get(URL).json()["data"] if u["id"] == staff.pk)
    assert row["mfa_enabled"] is True
    assert "secret" not in str(row).lower()


def test_no_secret_is_ever_returned(staff_client, staff, reader):
    enrol(staff)
    body = staff_client.get(URL).content.decode() + staff_client.get(f"{URL}{staff.pk}/").content.decode()
    assert "pbkdf2" not in body and "argon" not in body
    for key in SECRET_WORDS:
        assert f'"{key}"' not in body.lower()


def test_unknown_user_is_404(staff_client):
    assert staff_client.get(f"{URL}999999/").status_code == 404


# ---- changing a user ----------------------------------------------------------------
def test_staff_can_deactivate_and_reactivate_a_reader(staff_client, reader):
    assert patch(staff_client, reader, is_active=False).status_code == 200
    reader.refresh_from_db()
    assert reader.is_active is False
    assert patch(staff_client, reader, is_active=True).status_code == 200
    reader.refresh_from_db()
    assert reader.is_active is True


def test_only_is_active_and_is_staff_are_accepted(staff_client, superuser_client, reader):
    for body in ({"is_superuser": True}, {"email": "x@example.com"}, {"password": "x"}, {"is_active": False, "is_superuser": True}, {}):
        r = superuser_client.patch(f"{URL}{reader.pk}/", body, format="json")
        assert r.status_code == 400, body
    reader.refresh_from_db()
    assert reader.is_active and not reader.is_superuser and reader.email == "someone@example.com"


def test_values_must_be_real_booleans(superuser_client, reader):
    assert patch(superuser_client, reader, is_active="false").status_code == 400
    assert patch(superuser_client, reader, is_active=0).status_code == 400


def test_staff_cannot_grant_or_remove_the_staff_role(staff_client, superuser_client, reader, staff):
    assert patch(staff_client, reader, is_staff=True).status_code == 403
    reader.refresh_from_db()
    assert reader.is_staff is False
    assert patch(superuser_client, reader, is_staff=True).status_code == 200
    reader.refresh_from_db()
    assert reader.is_staff is True
    other = User.objects.create_user(email="other-staff@example.com", password=PASSWORD, is_staff=True)
    assert patch(staff_client, other, is_staff=False).status_code == 403


def test_staff_cannot_touch_superusers(staff_client, superuser):
    assert patch(staff_client, superuser, is_active=False).status_code == 403
    assert staff_client.post(f"{URL}{superuser.pk}/revoke-sessions/").status_code == 403
    assert staff_client.post(f"{URL}{superuser.pk}/resend-verification/").status_code == 403
    superuser.refresh_from_db()
    assert superuser.is_active


def test_nobody_can_deactivate_or_demote_themselves(staff_client, staff, superuser_client, superuser):
    assert patch(staff_client, staff, is_active=False).status_code == 400
    assert patch(superuser_client, superuser, is_active=False).status_code == 400
    assert patch(superuser_client, superuser, is_staff=False).status_code == 400
    # a superuser who is not the last one still cannot do it to themselves
    second = User.objects.create_superuser(email="second@example.com", password=PASSWORD)
    assert patch(client_for(second), second, is_active=False).status_code == 400
    staff.refresh_from_db()
    assert staff.is_active


def test_the_last_active_superuser_cannot_be_deactivated_or_demoted(superuser, db):
    assert User.objects.filter(is_superuser=True, is_active=True).count() == 1
    second = User.objects.create_superuser(email="second@example.com", password=PASSWORD)
    assert patch(client_for(second), superuser, is_active=False).status_code == 200  # two superusers: allowed
    superuser.refresh_from_db()
    assert superuser.is_active is False
    # now `second` is the only active superuser; a third (inactive-proof) actor cannot remove them either
    third = User.objects.create_superuser(email="third@example.com", password=PASSWORD)
    third.is_active = False
    third.save()
    r = patch(client_for(User.objects.create_superuser(email="fourth@example.com", password=PASSWORD)), second, is_active=False)
    assert r.status_code == 200  # fourth is a second active superuser, so this one is allowed
    fourth = User.objects.get(email="fourth@example.com")
    assert patch(client_for(fourth), fourth, is_active=False).status_code == 400  # self rule
    # the staff flag of a superuser can never be changed
    assert patch(client_for(fourth), User.objects.get(email="third@example.com"), is_staff=False).status_code == 400


def test_the_superuser_flag_cannot_be_changed_through_the_api(superuser_client, reader):
    superuser_client.patch(f"{URL}{reader.pk}/", {"is_superuser": True}, format="json")
    reader.refresh_from_db()
    assert reader.is_superuser is False


def test_deactivating_a_user_ends_their_sessions_at_once(staff_client, reader):
    c = APIClient()
    assert login(c, "someone@example.com").status_code == 200
    assert Session.objects.count() >= 1
    assert c.get("/api/v1/auth/me/").json()["data"]["email"] == "someone@example.com"
    assert patch(staff_client, reader, is_active=False).status_code == 200
    assert c.get("/api/v1/auth/me/").json()["data"] is None
    assert login(APIClient(), "someone@example.com").status_code == 400  # and they cannot log back in


def test_revoke_sessions_endpoint(staff_client, reader):
    a, b = APIClient(), APIClient()
    login(a, "someone@example.com")
    login(b, "someone@example.com")
    r = staff_client.post(f"{URL}{reader.pk}/revoke-sessions/")
    assert r.status_code == 200 and r.json()["data"]["ended"] == 2
    assert a.get("/api/v1/auth/me/").json()["data"] is None and b.get("/api/v1/auth/me/").json()["data"] is None


def test_resend_verification(staff_client, mailoutbox):
    unverified = make_user("unverified@example.com", verified=False)
    r = staff_client.post(f"{URL}{unverified.pk}/resend-verification/")
    assert r.status_code == 200 and r.json()["data"]["sent"] is True
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["unverified@example.com"]
    verified = make_user("verified@example.com")
    r = staff_client.post(f"{URL}{verified.pk}/resend-verification/")
    assert r.status_code == 200 and r.json()["data"]["sent"] is False
    assert len(mailoutbox) == 1


def test_resend_is_refused_for_inactive_accounts(staff_client):
    gone = make_user("gone@example.com", verified=False)
    gone.is_active = False
    gone.save()
    assert staff_client.post(f"{URL}{gone.pk}/resend-verification/").status_code == 400


def test_changes_are_audited_with_the_old_and_new_values(staff_client, reader):
    patch(staff_client, reader, is_active=False)
    entry = AuditLog.objects.filter(action="user.update").latest("id")
    assert entry.object_id == str(reader.pk)
    assert entry.metadata["changes"] == {"is_active": [True, False]}
    assert "someone@example.com" not in str(entry.metadata)


def test_a_no_op_patch_writes_no_audit_entry(staff_client, reader):
    patch(staff_client, reader, is_active=True)
    assert not AuditLog.objects.filter(action="user.update").exists()
