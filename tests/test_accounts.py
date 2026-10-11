import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from .conftest import PASSWORD, register_payload

User = get_user_model()
URL = "/api/v1/auth/"


def login(client, email="reader@example.com", password=PASSWORD):
    return client.post(URL + "login/", {"email": email, "password": password}, format="json")


# ---- registration -------------------------------------------------------------
# Phase 10 (B1) changed this rule on purpose: register always answers 202 "check your email" and never logs anyone in,
# so the form cannot be used to find out which addresses have an account.
def test_register_creates_user_profile_and_sends_verification_but_does_not_log_in(client, db):
    r = client.post(URL + "register/", register_payload("New@Example.com"), format="json")
    assert r.status_code == 202
    assert r.json()["data"] is None and "Check your email" in r.json()["message"]
    user = User.objects.get(email="new@example.com")
    assert user.profile.display_name == "Nia"
    assert client.get(URL + "me/").json()["data"] is None  # not logged in
    assert len(mail.outbox) >= 1


def test_duplicate_email_with_different_case_creates_nothing_and_looks_the_same(client, user):
    r = client.post(URL + "register/", register_payload("READER@example.com"), format="json")
    assert r.status_code == 202
    assert User.objects.filter(email__iexact="reader@example.com").count() == 1
    assert any(m.to == ["reader@example.com"] for m in mail.outbox)  # the owner gets a notice instead


def test_database_rejects_case_insensitive_duplicates(db):
    User.objects.create_user(email="a@example.com", password=PASSWORD)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(email="A@Example.com", password=PASSWORD)


def test_email_is_lowercased_and_stripped_on_save(db):
    u = User.objects.create_user(email="  Mixed@Example.COM ", password=PASSWORD)
    assert u.email == "mixed@example.com"


@pytest.mark.parametrize("weak", ["short", "a1b2c3d4e", "password1234"])
def test_weak_password_is_rejected(client, db, weak):
    r = client.post(URL + "register/", {"email": "w@example.com", "password": weak}, format="json")
    assert r.status_code == 400
    assert "password" in r.json()["errors"]


def test_register_cannot_create_staff(client, db):
    client.post(URL + "register/", register_payload("sneaky@example.com", is_staff=True, is_superuser=True), format="json")
    u = User.objects.get(email="sneaky@example.com")
    assert not u.is_staff and not u.is_superuser


def test_register_is_rate_limited(db):
    for i in range(10):
        r = APIClient().post(URL + "register/", register_payload(f"user{i}@example.com"), format="json")
        assert r.status_code == 202
    r = APIClient().post(URL + "register/", register_payload("one-too-many@example.com"), format="json")
    assert r.status_code == 429
    assert r.json()["data"] is None and "message" in r.json()


# ---- login / logout / me -----------------------------------------------------------
def test_login_ok_and_me(client, user):
    r = login(client)
    assert r.status_code == 200
    assert client.get(URL + "me/").json()["data"]["email"] == "reader@example.com"


def test_wrong_password_and_unknown_email_give_identical_errors(user):
    wrong_pw = login(APIClient(), password="Wrong-password-1")
    unknown = login(APIClient(), email="nobody@example.com")
    assert wrong_pw.status_code == unknown.status_code == 400
    assert wrong_pw.json() == unknown.json()
    assert wrong_pw.json()["message"] == "Incorrect email or password."


def test_me_is_null_for_anonymous(client, db):
    assert client.get(URL + "me/").json() == {"data": None}


def test_patch_me_updates_profile_but_not_email_or_staff(client, user):
    login(client)
    r = client.patch(URL + "me/", {"display_name": "Zed", "bio": "Hi", "email": "evil@example.com", "is_staff": True}, format="json")
    assert r.status_code == 200
    data = r.json()["data"]
    assert (data["display_name"], data["bio"]) == ("Zed", "Hi")
    user.refresh_from_db()
    assert user.email == "reader@example.com" and user.is_staff is False


def test_patch_me_requires_login(client, db):
    assert client.patch(URL + "me/", {"bio": "x"}, format="json").status_code in (401, 403)


def test_logout_ends_the_session(client, user):
    login(client)
    assert client.post(URL + "logout/").status_code == 200
    assert client.get(URL + "me/").json() == {"data": None}


def test_logout_enforces_csrf_for_logged_in_users(user):
    c = APIClient(enforce_csrf_checks=True)
    login(c)  # anonymous POST: no CSRF needed; Django issues a CSRF cookie on login
    assert c.post(URL + "logout/").status_code == 403
    token = c.cookies["csrftoken"].value
    assert c.post(URL + "logout/", HTTP_X_CSRFTOKEN=token).status_code == 200


def test_inactive_user_cannot_log_in(client, user):
    user.is_active = False
    user.save()
    r = login(client)
    assert r.status_code == 400
    assert r.json()["message"] == "Incorrect email or password."


def test_disabling_a_user_kills_existing_sessions(client, user):
    login(client)
    user.is_active = False
    user.save()
    assert client.get(URL + "me/").json() == {"data": None}


# ---- lockout ------------------------------------------------------------------------
def test_login_locks_out_after_five_failures(user):
    c = APIClient()
    for _ in range(5):
        assert login(c, password="Wrong-password-1").status_code == 400
    r = login(c, password="Wrong-password-1")
    assert r.status_code == 429
    assert "Retry-After" in r
    assert "message" in r.json()
    assert login(c).status_code == 429  # even the right password is refused while locked


def test_successful_login_clears_the_failure_counter(user):
    c = APIClient()
    for _ in range(3):
        login(c, password="Wrong-password-1")
    assert login(c).status_code == 200
    c2 = APIClient()
    for _ in range(4):
        assert login(c2, password="Wrong-password-1").status_code == 400  # counter restarted, not locked


# ---- password reset -----------------------------------------------------------------------
def test_reset_request_answers_the_same_for_known_and_unknown_emails(user):
    known = APIClient().post(URL + "password/reset/", {"email": "reader@example.com"}, format="json")
    sent = len(mail.outbox)
    unknown = APIClient().post(URL + "password/reset/", {"email": "ghost@example.com"}, format="json")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert sent == 1 and len(mail.outbox) == 1  # nothing sent for the unknown address


def test_reset_confirm_changes_password_and_kills_old_sessions(user):
    old_session = APIClient()
    login(old_session)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    new_pw = "Brand-new-passw0rd!"
    r = APIClient().post(URL + "password/reset/confirm/", {"uid": uid, "token": token, "password": new_pw}, format="json")
    assert r.status_code == 200
    assert login(APIClient(), password=PASSWORD).status_code == 400  # old password dead
    assert login(APIClient(), password=new_pw).status_code == 200
    assert old_session.get(URL + "me/").json() == {"data": None}  # old session invalidated


def test_reset_confirm_rejects_bad_token_and_weak_password(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    bad = APIClient().post(URL + "password/reset/confirm/", {"uid": uid, "token": "nope", "password": "Brand-new-passw0rd!"}, format="json")
    assert bad.status_code == 400
    token = default_token_generator.make_token(user)
    weak = APIClient().post(URL + "password/reset/confirm/", {"uid": uid, "token": token, "password": "short"}, format="json")
    assert weak.status_code == 400 and "password" in weak.json()["errors"]


# ---- email verification -----------------------------------------------------------------
def test_email_verification_flow(client, db):
    client.post(URL + "register/", register_payload("verify@example.com"), format="json")
    body = mail.outbox[0].body
    key = re.search(r"verify-email\?key=([^\s&]+)", body).group(1)
    r = APIClient().post(URL + "email/verify/", {"key": key}, format="json")
    assert r.status_code == 200
    assert login(client, "verify@example.com").status_code == 200  # registering does not log in: do it now
    assert client.get(URL + "me/").json()["data"]["email_verified"] is True


def test_email_verify_rejects_garbage_key(db):
    assert APIClient().post(URL + "email/verify/", {"key": "garbage"}, format="json").status_code == 400


def test_email_resend_requires_login(client, db):
    assert client.post(URL + "email/resend/").status_code in (401, 403)


# ---- google / allauth configuration ------------------------------------------------------
def test_google_provider_is_configured_and_loads_without_credentials(settings):
    app = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]
    assert "client_id" in app and "secret" in app  # may be empty strings: must not crash startup
    assert "allauth.socialaccount.providers.google" in settings.INSTALLED_APPS
    assert reverse("google_login")
