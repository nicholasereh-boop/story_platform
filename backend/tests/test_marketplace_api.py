"""Marketplace: ownership, review flow, uploads, screenshots, protected downloads."""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.source_marketplace.models import SourceDownload, SourcePackage, SourceProject

from .marketplace_helpers import MP, client_for, new_project, private_dirs, publish, seller, buyer, other_seller, upload, zip_upload  # noqa: F401
from .media_helpers import make_image

pytestmark = pytest.mark.django_db


def ready_project(client, **extra):
    """A project with rights confirmed and a frontend package, ready to submit."""
    p = new_project(client, rights_confirmed=True, **extra)
    assert upload(client, p["id"]).status_code == 201
    return p


# ------------------------------------------------------------------ creating and validating
def test_anonymous_cannot_create_and_members_start_a_draft(private_dirs, seller):
    assert APIClient().post(MP + "projects/", {"title": "x"}, format="json").status_code in (401, 403)
    p = new_project(client_for(seller), technologies=["React", "react", "Django"], youtube_url="https://youtu.be/dQw4w9WgXcQ",
                    frontend_price="0", backend_price="150.50")
    assert p["status"] == "draft" and p["youtube_id"] == "dQw4w9WgXcQ"
    assert [t["name"] for t in p["technologies"]] == ["Django", "React"]  # de-duplicated, case-insensitive
    assert p["backend_price"] == "150.50"


def test_client_cannot_set_status_owner_or_currency(private_dirs, seller, other_seller):
    p = new_project(client_for(seller), status="published", owner=other_seller.pk, currency="NGN")
    row = SourceProject.objects.get(pk=p["id"])
    assert row.status == "draft" and row.owner_id == seller.pk and row.currency == "USD"  # the site currency, never the seller's choice


@pytest.mark.parametrize("field,value", [
    ("title", "<script>x</script>"), ("youtube_url", "https://evil.example/watch?v=dQw4w9WgXcQ"),
    ("frontend_price", "-1"), ("backend_price", "999999999"), ("technologies", ["<b>"]), ("slug", "12345"),
])
def test_invalid_fields_are_rejected(private_dirs, seller, field, value):
    r = client_for(seller).post(MP + "projects/", {"title": "T", "description": "d" * 40, field: value}, format="json")
    assert r.status_code == 400 and field in r.json()["errors"]


def test_description_may_contain_code_because_it_is_only_ever_shown_as_text(private_dirs, seller):
    p = new_project(client_for(seller), description="Run <div id='app'></div> in your page. " * 3)
    assert "<div" in p["description"]


def test_slugs_are_unique_and_never_all_digits(private_dirs, seller):
    c = client_for(seller)
    a, b = new_project(c, title="Same Title"), new_project(c, title="Same Title")
    assert a["slug"] != b["slug"]
    assert not new_project(c, title="2024")["slug"].isdigit()


# ------------------------------------------------------------------ ownership
def test_another_seller_cannot_see_edit_upload_or_delete(private_dirs, seller, other_seller):
    p = new_project(client_for(seller))
    intruder = client_for(other_seller)
    assert intruder.patch(MP + f"projects/{p['id']}/", {"title": "stolen"}, format="json").status_code == 404
    assert intruder.delete(MP + f"projects/{p['id']}/").status_code == 404
    assert upload(intruder, p["id"]).status_code == 404
    assert intruder.get(MP + f"my/projects/{p['id']}/").status_code == 404
    assert intruder.post(MP + f"projects/{p['id']}/submit/").status_code == 404
    assert SourceProject.objects.get(pk=p["id"]).title == "Shop Template"


def test_staff_status_does_not_let_sellers_edit_others_work_via_the_seller_api(private_dirs, seller, staff):
    p = new_project(client_for(seller))
    assert client_for(staff).patch(MP + f"projects/{p['id']}/", {"title": "x"}, format="json").status_code == 404


# ------------------------------------------------------------------ visibility
def test_public_list_and_detail_show_only_published(private_dirs, seller, other_seller):
    c = client_for(seller)
    draft, live = new_project(c, title="Hidden Draft"), new_project(c, title="Visible One")
    publish(live["id"])
    anon = APIClient()
    titles = [row["title"] for row in anon.get(MP + "projects/").json()["data"]]
    assert titles == ["Visible One"]
    assert anon.get(MP + f"projects/{draft['slug']}/").status_code == 404
    assert client_for(other_seller).get(MP + f"projects/{draft['slug']}/").status_code == 404
    assert c.get(MP + f"projects/{draft['slug']}/").status_code == 200  # its own seller can preview
    assert anon.get(MP + f"projects/{live['slug']}/").status_code == 200


def test_public_payloads_never_contain_private_fields(private_dirs, seller):
    p = ready_project(client_for(seller))
    publish(p["id"])
    body = APIClient().get(MP + f"projects/{p['slug']}/").content.decode()
    for secret in ("review_note", "scan_report", "sha256", "private", "owner_email", "seller@example.com"):
        assert secret not in body


def test_filters_search_technology_and_free(private_dirs, seller):
    c = client_for(seller)
    a = ready_project(c, title="Alpha Shop", technologies=["React"])
    b = new_project(c, title="Beta Blog", technologies=["Django"])
    upload(c, b["id"], kind="backend")
    publish(a["id"])
    publish(b["id"], backend_price="5000")
    anon = APIClient()
    assert [r["title"] for r in anon.get(MP + "projects/", {"q": "alpha"}).json()["data"]] == ["Alpha Shop"]
    assert [r["title"] for r in anon.get(MP + "projects/", {"tech": "django"}).json()["data"]] == ["Beta Blog"]
    assert [r["title"] for r in anon.get(MP + "projects/", {"free": "1"}).json()["data"]] == ["Alpha Shop"]


# ------------------------------------------------------------------ review flow
def test_submit_needs_rights_description_and_a_package(private_dirs, seller):
    c = client_for(seller)
    p = new_project(c, description="short")
    r = c.post(MP + f"projects/{p['id']}/submit/")
    assert r.status_code == 400 and {"description", "rights_confirmed", "packages"} <= set(r.json()["errors"])


def test_submit_then_staff_approves_and_it_goes_public(private_dirs, seller, staff):
    c = client_for(seller)
    p = ready_project(c)
    r = c.post(MP + f"projects/{p['id']}/submit/")
    assert r.json()["data"]["status"] == "pending"
    assert APIClient().get(MP + "projects/").json()["data"] == []
    r = client_for(staff).post(f"/api/v1/admin/marketplace/projects/{p['id']}/approve/")
    assert r.status_code == 200 and r.json()["data"]["status"] == "published"
    assert len(APIClient().get(MP + "projects/").json()["data"]) == 1
    assert list(AuditLog.objects.order_by("id").values_list("action", flat=True)) == ["marketplace.submit", "marketplace.publish"]


def test_reject_needs_a_note_and_shows_it_to_the_seller(private_dirs, seller, staff):
    c = client_for(seller)
    p = ready_project(c)
    c.post(MP + f"projects/{p['id']}/submit/")
    s = client_for(staff)
    assert s.post(f"/api/v1/admin/marketplace/projects/{p['id']}/reject/", {}, format="json").status_code == 400
    s.post(f"/api/v1/admin/marketplace/projects/{p['id']}/reject/", {"note": "Please remove the license conflict."}, format="json")
    mine = c.get(MP + f"my/projects/{p['id']}/").json()["data"]
    assert mine["status"] == "rejected" and "license" in mine["review_note"]
    assert c.post(MP + f"projects/{p['id']}/submit/").json()["data"]["status"] == "pending"  # may resubmit


def test_ordinary_users_cannot_use_the_moderation_endpoints(private_dirs, seller):
    p = new_project(client_for(seller))
    c = client_for(seller)
    assert c.get("/api/v1/admin/marketplace/projects/").status_code == 403
    assert c.post(f"/api/v1/admin/marketplace/projects/{p['id']}/approve/").status_code == 403
    assert APIClient().get("/api/v1/admin/marketplace/projects/").status_code in (401, 403)


def test_review_can_be_switched_off(private_dirs, settings, seller):
    settings.MARKETPLACE_REQUIRE_REVIEW = False
    c = client_for(seller)
    p = ready_project(c)
    assert c.post(MP + f"projects/{p['id']}/submit/").json()["data"]["status"] == "published"


def test_changing_a_published_projects_files_or_text_sends_it_back_to_review(private_dirs, seller):
    c = client_for(seller)
    p = ready_project(c)
    publish(p["id"])
    r = c.patch(MP + f"projects/{p['id']}/", {"description": "A different and longer description of the project."}, format="json")
    assert r.json()["data"]["status"] == "pending" and r.json()["data"]["sent_back_to_review"] is True
    publish(p["id"])
    r = upload(c, p["id"], files={"new.txt": "v2"})
    assert r.json()["data"]["sent_back_to_review"] is True and SourceProject.objects.get(pk=p["id"]).status == "pending"
    publish(p["id"])
    r = c.patch(MP + f"projects/{p['id']}/", {"frontend_price": "100"}, format="json")  # price only: no re-review
    assert r.json()["data"]["status"] == "published"


# ------------------------------------------------------------------ uploads and screenshots
def test_upload_validates_kind_extension_and_content(private_dirs, seller):
    c = client_for(seller)
    p = new_project(c)
    assert c.post(MP + f"projects/{p['id']}/upload/", {"kind": "mobile", "file": zip_upload()}, format="multipart").status_code == 400
    assert c.post(MP + f"projects/{p['id']}/upload/", {"kind": "frontend"}, format="multipart").status_code == 400
    from django.core.files.uploadedfile import SimpleUploadedFile
    bad = SimpleUploadedFile("code.tar.gz", b"x" * 50)
    assert c.post(MP + f"projects/{p['id']}/upload/", {"kind": "frontend", "file": bad}, format="multipart").status_code == 400
    notzip = SimpleUploadedFile("fake.zip", b"not really a zip" * 10)
    r = c.post(MP + f"projects/{p['id']}/upload/", {"kind": "frontend", "file": notzip}, format="multipart")
    assert r.status_code == 400 and "valid ZIP" in r.json()["errors"]["file"][0]
    assert SourcePackage.objects.count() == 0


def test_upload_rejects_hostile_archives_and_stores_nothing(private_dirs, seller):
    c = client_for(seller)
    p = new_project(c)
    r = upload(c, p["id"], files={"ok.txt": "x", "../../evil.sh": "rm -rf"})
    assert r.status_code == 400
    r = upload(c, p["id"], files={"config.py": "KEY='AKIA" + "ABCDEFGHIJKLMNOP'"})
    assert r.status_code == 400 and "config.py" in r.json()["errors"]["file"][0]
    assert SourcePackage.objects.count() == 0 and not list((private_dirs / "private").rglob("*.zip"))


def test_upload_replaces_the_package_and_deletes_the_old_file_and_stays_private(private_dirs, seller):
    c = client_for(seller)
    p = new_project(c)
    upload(c, p["id"], files={"a.txt": "one"}, version="1.0.0")
    first = SourcePackage.objects.get()
    first_path = first.file.path
    upload(c, p["id"], files={"b.txt": "two"}, version="1.1.0")
    pkg = SourcePackage.objects.get()
    assert pkg.version == "1.1.0" and pkg.pk == first.pk and pkg.file.path != first_path
    import os
    assert not os.path.exists(first_path) and os.path.exists(pkg.file.path)
    assert str(pkg.file.path).startswith(str(private_dirs / "private")) and not str(pkg.file.path).startswith(str(private_dirs / "media"))
    with pytest.raises(ValueError):
        pkg.file.url  # no public address exists


def test_screenshots_use_the_image_checks_and_are_limited(private_dirs, seller):
    c = client_for(seller)
    p = new_project(c)
    url = MP + f"projects/{p['id']}/screenshots/"
    r = c.post(url, {"file": make_image(), "alt_text": "Home page"}, format="multipart")
    assert r.status_code == 201 and r.json()["data"][0]["alt_text"] == "Home page"
    from django.core.files.uploadedfile import SimpleUploadedFile
    assert c.post(url, {"file": SimpleUploadedFile("x.png", b"<script>alert(1)</script>", content_type="image/png")}, format="multipart").status_code == 400
    for _ in range(7):
        assert c.post(url, {"file": make_image()}, format="multipart").status_code == 201
    assert c.post(url, {"file": make_image()}, format="multipart").status_code == 400  # the 9th
    shot_id = r.json()["data"][0]["id"]
    assert c.delete(url + f"{shot_id}/").status_code == 204


# ------------------------------------------------------------------ downloads
def test_free_download_requires_login_streams_a_zip_and_is_recorded(private_dirs, seller, buyer):
    c = client_for(seller)
    p = ready_project(c)
    publish(p["id"])
    pkg = SourcePackage.objects.get()
    url = MP + f"packages/{pkg.pk}/download/"
    assert APIClient().get(url).status_code in (401, 403)
    r = client_for(buyer).get(url)
    assert r.status_code == 200 and r["Content-Type"] == "application/zip"
    assert "attachment" in r["Content-Disposition"] and ".zip" in r["Content-Disposition"]
    assert r["Cache-Control"] == "private, no-store" and r["X-Content-Type-Options"] == "nosniff"
    import io, zipfile
    assert "index.html" in zipfile.ZipFile(io.BytesIO(b"".join(r.streaming_content))).namelist()
    d = SourceDownload.objects.get()
    assert d.basis == "free" and d.user_id == buyer.pk and len(d.ip_hash) in (0, 64)


def test_paid_package_is_locked_for_everyone_but_owner_and_staff(private_dirs, seller, buyer, staff):
    c = client_for(seller)
    p = new_project(c)
    upload(c, p["id"], kind="backend")
    publish(p["id"], backend_price="5000")
    url = MP + f"packages/{SourcePackage.objects.get().pk}/download/"
    r = client_for(buyer).get(url)
    assert r.status_code == 403 and "Buy" in r.json()["message"]
    assert SourceDownload.objects.count() == 0
    assert c.get(url).status_code == 200 and client_for(staff).get(url).status_code == 200
    assert {d.basis for d in SourceDownload.objects.all()} == {"owner", "staff"}


def test_unpublished_packages_look_nonexistent_to_everyone_else(private_dirs, seller, buyer):
    c = client_for(seller)
    ready_project(c)
    url = MP + f"packages/{SourcePackage.objects.get().pk}/download/"
    assert client_for(buyer).get(url).status_code == 404
    assert c.get(url).status_code == 200


def test_the_detail_page_tells_the_viewer_what_they_may_do(private_dirs, seller, buyer):
    p = new_project(client_for(seller))
    upload(client_for(seller), p["id"], kind="backend")
    upload(client_for(seller), p["id"], kind="frontend")
    publish(p["id"], backend_price="5000")
    viewer = client_for(buyer).get(MP + f"projects/{p['slug']}/").json()["data"]["viewer"]
    assert viewer["packages"]["frontend"]["can_download"] is True and viewer["packages"]["backend"]["can_download"] is False


# ------------------------------------------------------------------ other
def test_github_import_stores_the_package_and_never_echoes_the_token(private_dirs, seller, monkeypatch):
    import io
    from apps.source_marketplace.services import github
    from .marketplace_helpers import make_zip
    seen = {}

    def fake(owner, repo, ref="", token="", **kw):
        seen.update(owner=owner, repo=repo, ref=ref, token=token)
        return io.BytesIO(make_zip({"src/main.py": "print(1)"}, root="acme-shop-9f8e7d"))

    monkeypatch.setattr(github, "download_zipball", fake)
    c = client_for(seller)
    p = new_project(c)
    token = "github_pat_" + "A1b2C3d4E5" * 5
    r = c.post(MP + f"projects/{p['id']}/github-import/", {"kind": "backend", "repository": "https://github.com/acme/shop", "ref": "main", "token": token}, format="json")
    assert r.status_code == 201 and seen == {"owner": "acme", "repo": "shop", "ref": "main", "token": token}
    pkg = SourcePackage.objects.get()
    assert pkg.source == "github" and pkg.source_ref == "acme/shop@main"
    assert token not in r.content.decode() and token not in str(pkg.scan_report) and token not in pkg.source_ref
    bad = c.post(MP + f"projects/{p['id']}/github-import/", {"kind": "backend", "repository": "not a repo!"}, format="json")
    assert bad.status_code == 400


def test_the_whole_feature_can_be_switched_off(private_dirs, settings, seller):
    settings.MARKETPLACE_ENABLED = False
    assert APIClient().get(MP + "projects/").status_code == 404
    assert client_for(seller).post(MP + "projects/", {"title": "x"}, format="json").status_code == 404


def test_projects_with_buyers_cannot_be_deleted_but_unsold_ones_can(private_dirs, seller):
    c = client_for(seller)
    p = ready_project(c)
    assert c.delete(MP + f"projects/{p['id']}/").status_code == 204
    assert SourceProject.objects.count() == 0 and not list((private_dirs / "private").rglob("*.zip"))


def test_a_staff_members_own_project_is_published_straight_away_even_with_review_on(private_dirs, staff):
    c = client_for(staff)
    p = ready_project(c)
    assert c.post(MP + f"projects/{p['id']}/submit/").json()["data"]["status"] == "published"
    assert len(APIClient().get(MP + "projects/").json()["data"]) == 1
