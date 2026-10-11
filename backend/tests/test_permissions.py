from io import StringIO
from types import SimpleNamespace

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.core.permissions import IsOwnerOrStaff, IsStaffUser, IsSuperUser, IsVerifiedEmail

from .conftest import PASSWORD

User = get_user_model()
PING = "/api/v1/admin/ping/"


def req(user=None):
    return SimpleNamespace(user=user or SimpleNamespace(is_authenticated=False))


# ---- admin ping ------------------------------------------------------------------------
def test_ping_denies_anonymous_in_standard_envelope(client, db):
    r = client.get(PING)
    assert r.status_code in (401, 403)
    body = r.json()
    assert body["data"] is None and "errors" in body and "message" in body


def test_ping_denies_normal_user(client, user):
    client.force_authenticate(user)
    assert client.get(PING).status_code == 403


def test_ping_allows_staff(client, staff):
    client.force_authenticate(staff)
    r = client.get(PING)
    assert r.status_code == 200
    assert r.json() == {"data": {"admin": True}}


def test_ping_denies_deactivated_staff(client, staff):
    staff.is_active = False
    staff.save()
    client.force_authenticate(staff)
    assert client.get(PING).status_code in (401, 403)


# ---- permission classes -----------------------------------------------------------------
def test_is_staff_user_and_is_super_user(user, staff):
    admin = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
    assert not IsStaffUser().has_permission(req(user), None)
    assert IsStaffUser().has_permission(req(staff), None)
    assert not IsSuperUser().has_permission(req(staff), None)  # staff cannot grant staff
    assert IsSuperUser().has_permission(req(admin), None)


def test_owner_or_staff_object_permission(user, staff):
    other = User.objects.create_user(email="other@example.com", password=PASSWORD)
    perm = IsOwnerOrStaff()
    assert perm.has_object_permission(req(user), None, SimpleNamespace(user=user))
    assert perm.has_object_permission(req(user), None, SimpleNamespace(created_by=user))
    assert not perm.has_object_permission(req(other), None, SimpleNamespace(user=user))
    assert perm.has_object_permission(req(staff), None, SimpleNamespace(user=user))
    assert not perm.has_object_permission(req(), None, SimpleNamespace(user=user))


def test_is_verified_email(user):
    assert not IsVerifiedEmail().has_permission(req(user), None)
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    assert IsVerifiedEmail().has_permission(req(user), None)


# ---- create_admin command --------------------------------------------------------------
def test_create_admin_creates_and_upgrades(db, monkeypatch):
    answers = iter(["Sup3r-secret-pass!", "Sup3r-secret-pass!"] * 2)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    call_command("create_admin", "Boss@Example.com", stdout=StringIO())
    boss = User.objects.get(email="boss@example.com")
    assert boss.is_staff and boss.is_superuser and boss.check_password("Sup3r-secret-pass!")
    assert EmailAddress.objects.filter(user=boss, verified=True).exists()
    # running again upgrades the same account instead of failing
    call_command("create_admin", "boss@example.com", stdout=StringIO())
    assert User.objects.filter(email__iexact="boss@example.com").count() == 1
