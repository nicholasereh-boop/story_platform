"""Helpers for the source marketplace tests: in-memory ZIPs, a fake Paystack, ready-made users and projects."""
import hashlib
import hmac
import io
import json
import warnings
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.source_marketplace.models import SourceProject
from apps.source_marketplace.services import payments

API = "/api/v1/"
MP = API + "marketplace/"
SECRET = "sk_test_unit_test_secret_value"


def make_zip(files, *, root=None, extra_infos=()):
    """Bytes of a ZIP. `files` maps name -> str/bytes. `extra_infos` is a list of (ZipInfo, bytes) written as-is."""
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                zf.writestr(f"{root}/{name}" if root else name, content)
            for info, content in extra_infos:
                zf.writestr(info, content)
    return buf.getvalue()


def zip_upload(files=None, name="project.zip", **kwargs):
    files = files if files is not None else {"index.html": "<h1>hello</h1>", "src/app.js": "console.log(1)"}
    return SimpleUploadedFile(name, make_zip(files, **kwargs), content_type="application/zip")


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def signed(body: dict, secret=SECRET):
    raw = json.dumps(body).encode()
    return raw, hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()


class FakePaystack:
    """Stands in for payments.PaystackClient. Tests set `.result` to what Paystack should say about a transaction."""

    def __init__(self):
        self.initialized = []
        self.verified = []
        self.result = None  # dict overriding fields of the verify answer
        self.fail_verify = False
        self.fail_initialize = False

    def initialize(self, **kwargs):
        if self.fail_initialize:
            raise payments.PaystackError("down", 502)
        self.initialized.append(kwargs)
        return {"authorization_url": f"https://checkout.paystack.com/{kwargs['reference']}", "access_code": "x", "reference": kwargs["reference"]}

    def verify(self, reference):
        self.verified.append(reference)
        if self.fail_verify:
            raise payments.PaystackError("down", 502)
        match = next((i for i in self.initialized if i["reference"] == reference), None)
        base = {"status": "success", "reference": reference, "id": 4242,
                "amount": match["amount_minor"] if match else 0, "currency": match["currency"] if match else "USD"}
        return {**base, **(self.result or {})}


@pytest.fixture
def private_dirs(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MARKETPLACE_PRIVATE_ROOT = str(tmp_path / "private")
    settings.PAYSTACK_SECRET_KEY = SECRET
    return tmp_path


@pytest.fixture
def paystack(monkeypatch, private_dirs):
    fake = FakePaystack()
    monkeypatch.setattr(payments, "get_client", lambda: fake)
    return fake


@pytest.fixture
def seller(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="seller@example.com", password="Correct-horse-battery-9")


@pytest.fixture
def buyer(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="buyer@example.com", password="Correct-horse-battery-9")


@pytest.fixture
def other_seller(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email="other@example.com", password="Correct-horse-battery-9")


def new_project(client, **overrides):
    body = {"title": "Shop Template", "description": "A complete shop with cart and checkout pages for small stores.", **overrides}
    r = client.post(MP + "projects/", body, format="json")
    assert r.status_code == 201, r.content
    return r.json()["data"]


def upload(client, project_id, kind="frontend", files=None, **extra):
    return client.post(MP + f"projects/{project_id}/upload/", {"kind": kind, "file": zip_upload(files), **extra}, format="multipart")


def publish(project_id, **fields):
    """Force a project live (skips review) with the given prices; for tests of buying and downloading."""
    SourceProject.objects.filter(pk=project_id).update(status="published", **fields)
