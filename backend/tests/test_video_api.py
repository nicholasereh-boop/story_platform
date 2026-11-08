"""Video tools API: inspect, the closed-by-default capability gate, job lifecycle, ownership, limits, cleanup."""
import os
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.video_tools.models import DownloadArtifact, DownloadJob, ProviderCapability
from apps.video_tools.services import download_jobs

from .marketplace_helpers import client_for

pytestmark = pytest.mark.django_db
V = "/api/v1/video-tools/"
YT = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
OK = "tests.video_helpers.OkAdapter"


@pytest.fixture(autouse=True)
def video_env(settings, tmp_path):
    settings.VIDEO_TOOLS_PRIVATE_ROOT = str(tmp_path / "video")
    settings.VIDEO_TOOLS_RUN_INLINE = True
    settings.VIDEO_TOOLS_ADAPTERS = {}
    return tmp_path


@pytest.fixture
def member(db):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(email="viewer@example.com", password="Correct-horse-battery-9")


@pytest.fixture
def stranger(db):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user(email="stranger@example.com", password="Correct-horse-battery-9")


def enable(settings, adapter=OK, provider="youtube"):
    settings.VIDEO_TOOLS_ADAPTERS = {provider: adapter}
    ProviderCapability.objects.update_or_create(provider=provider, defaults={"download_enabled": True})


def request_download(user, url=YT, **body):
    return client_for(user).post(V + "downloads/", {"url": url, "authorization_confirmed": True, **body}, format="json")


# ------------------------------------------------------------------ inspect
@pytest.mark.parametrize("url,provider,label", [
    (YT, "youtube", "YouTube"), ("https://www.facebook.com/watch/?v=1234567890123", "facebook", "Facebook"),
    ("https://www.instagram.com/reel/C1a2B3c4D5e/", "instagram", "Instagram"),
    ("https://www.tiktok.com/@someone/video/7234567890123456789", "tiktok", "TikTok"),
    ("https://x.com/someone/status/1234567890123456789", "x", "X"),
])
def test_every_platform_is_identified_and_inspect_only_by_default(url, provider, label):
    r = APIClient().post(V + "inspect/", {"url": url}, format="json")  # no login needed to inspect
    d = r.json()["data"]
    assert r.status_code == 200 and d["provider"] == provider and d["provider_label"] == label
    assert d["download"]["available"] is False and "No permitted download method" in d["download"]["reason"]
    assert d["guidance"] and "watermark" in d["notice"].lower() and "never removes" in d["notice"]
    assert d["canonical_url"].startswith("https://")


def test_inspect_rejects_bad_links_with_a_clear_message():
    for bad in ["", "http://youtu.be/dQw4w9WgXcQ", "https://evil.example/x", "https://127.0.0.1/", "javascript:alert(1)"]:
        r = APIClient().post(V + "inspect/", {"url": bad}, format="json")
        assert r.status_code == 400 and r.json()["errors"]["url"]
    assert APIClient().post(V + "inspect/", {}, format="json").status_code == 400


def test_inspect_reports_short_links_and_never_resolves_them(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    d = APIClient().post(V + "inspect/", {"url": "https://vm.tiktok.com/ZMabc123/"}, format="json").json()["data"]
    assert d["needs_resolution"] is True


def test_a_reviewed_adapter_alone_is_not_enough_staff_must_switch_it_on(settings):
    settings.VIDEO_TOOLS_ADAPTERS = {"youtube": OK}
    d = APIClient().post(V + "inspect/", {"url": YT}, format="json").json()["data"]["download"]
    assert d["available"] is False and "not been enabled" in d["reason"]
    enable(settings)
    d = APIClient().post(V + "inspect/", {"url": YT}, format="json").json()["data"]["download"]
    assert d["available"] is True and [f["key"] for f in d["formats"]] == ["mp4", "mp3"] and "official" in d["method"]


def test_an_unconfigured_adapter_or_one_registered_for_the_wrong_provider_is_unavailable(settings):
    enable(settings, "tests.video_helpers.WrongProviderAdapter")  # claims "tiktok" but registered under "youtube"
    assert APIClient().post(V + "inspect/", {"url": YT}, format="json").json()["data"]["download"]["available"] is False
    enable(settings)
    from tests.video_helpers import OkAdapter
    OkAdapter.configured = False
    try:
        d = APIClient().post(V + "inspect/", {"url": YT}, format="json").json()["data"]["download"]
        assert d["available"] is False and "temporarily" in d["reason"]
    finally:
        OkAdapter.configured = True


# ------------------------------------------------------------------ requesting a download
def test_downloads_need_a_login_and_the_authorisation_tick(settings, member):
    enable(settings)
    assert APIClient().post(V + "downloads/", {"url": YT, "authorization_confirmed": True}, format="json").status_code in (401, 403)
    c = client_for(member)
    for body in ({"url": YT}, {"url": YT, "authorization_confirmed": False}):
        r = c.post(V + "downloads/", body, format="json")
        assert r.status_code == 400 and "authorization_confirmed" in r.json()["errors"]
    assert DownloadJob.objects.count() == 0


def test_closed_providers_refuse_with_the_reason_and_create_nothing(member):
    r = request_download(member)
    assert r.status_code == 422 and r.json()["errors"]["code"] == "provider_unavailable" and "No permitted download method" in r.json()["message"]
    assert DownloadJob.objects.count() == 0


def test_full_happy_path_status_file_and_the_stored_link_is_canonical_only(settings, member):
    enable(settings)
    r = request_download(member, url=YT + "&utm_source=x&si=tracker", format="mp3")
    d = r.json()["data"]
    assert r.status_code == 202 and d["status"] == "done" and d["format_key"] == "mp3"
    job = DownloadJob.objects.get()
    assert job.source_url == YT and "tracker" not in job.source_url and job.authorization_confirmed_at
    assert d["artifact"]["filename"] == "My Video_.mp4" and d["artifact"]["size_bytes"] == 900  # path tricks in the name are gone
    c = client_for(member)
    assert c.get(V + f"downloads/{job.pk}/").json()["data"]["status"] == "done"
    f = c.get(V + f"downloads/{job.pk}/file/")
    assert f.status_code == 200 and b"".join(f.streaming_content).startswith(b"FAKEVIDEO")
    assert "attachment" in f["Content-Disposition"] and f["Cache-Control"] == "private, no-store" and f["X-Content-Type-Options"] == "nosniff"
    art = DownloadArtifact.objects.get()
    assert os.path.exists(art.file.path) and str(art.file.path).startswith(str(settings.VIDEO_TOOLS_PRIVATE_ROOT))
    with pytest.raises(ValueError):
        art.file.url


def test_validation_and_format_and_short_link_rules(settings, member):
    enable(settings)
    assert request_download(member, url="https://evil.example/x").status_code == 400
    assert request_download(member, format="avi").json()["errors"]["code"] == "bad_format"
    assert request_download(member, url="https://youtu.be/dQw4w9WgXcQ").status_code == 202


def test_short_links_are_refused_for_downloading_with_instructions(settings, member):
    class TikTokOk(__import__("tests.video_helpers", fromlist=["OkAdapter"]).OkAdapter):
        provider = "tiktok"
    import tests.video_helpers as h
    h.TikTokOk = TikTokOk
    enable(settings, "tests.video_helpers.TikTokOk", "tiktok")
    r = request_download(member, url="https://vm.tiktok.com/ZMabc123/")
    assert r.status_code == 400 and r.json()["errors"]["code"] == "short_link"


# ------------------------------------------------------------------ failures never leak
def test_an_adapter_that_refuses_gives_the_persons_message(settings, member):
    enable(settings, "tests.video_helpers.RefusingAdapter")
    d = request_download(member).json()["data"]
    assert d["status"] == "failed" and d["error_code"] == "not_permitted" and "not allowed downloads" in d["error_message"] and d["artifact"] is None


def test_an_adapter_crash_shows_a_generic_message_and_logs_no_url(settings, member, caplog):
    enable(settings, "tests.video_helpers.CrashingAdapter")
    d = request_download(member).json()["data"]
    assert d["status"] == "failed" and d["error_code"] == "unexpected"
    assert "internal.example" not in str(d) and "token=abc" not in str(d)
    assert "youtube.com/watch" not in caplog.text  # the log line has the job id and provider only


def test_results_outside_the_work_folder_or_too_big_are_refused(settings, member):
    enable(settings, "tests.video_helpers.EscapingAdapter")
    assert request_download(member).json()["data"]["error_code"] == "bad_result"
    settings.VIDEO_TOOLS_MAX_FILE_BYTES = 1000
    enable(settings, "tests.video_helpers.OversizeAdapter")
    assert request_download(member).json()["data"]["error_code"] == "bad_size"
    assert DownloadArtifact.objects.count() == 0


def test_switching_a_provider_off_before_a_queued_job_runs_stops_it(settings, member, monkeypatch):
    enable(settings)
    monkeypatch.setattr(download_jobs, "enqueue", lambda job: None)  # leave it queued
    job_id = request_download(member).json()["data"]["id"]
    ProviderCapability.objects.update(download_enabled=False)
    job = download_jobs.run_job(job_id)
    assert job.status == "failed" and job.error_code == "provider_unavailable" and not DownloadArtifact.objects.exists()


def test_a_job_can_only_be_claimed_once(settings, member, monkeypatch):
    enable(settings)
    monkeypatch.setattr(download_jobs, "enqueue", lambda job: None)
    job_id = request_download(member).json()["data"]["id"]
    assert download_jobs.run_job(job_id).status == "done"
    assert download_jobs.run_job(job_id) is None and DownloadArtifact.objects.count() == 1


# ------------------------------------------------------------------ ownership
def test_other_people_cannot_see_fetch_or_delete_a_job(settings, member, stranger):
    enable(settings)
    job_id = request_download(member).json()["data"]["id"]
    s = client_for(stranger)
    assert s.get(V + f"downloads/{job_id}/").status_code == 404
    assert s.get(V + f"downloads/{job_id}/file/").status_code == 404
    assert s.delete(V + f"downloads/{job_id}/").status_code == 404
    assert APIClient().get(V + f"downloads/{job_id}/file/").status_code in (401, 403)
    assert s.get(V + "downloads/").json()["data"] == []
    assert DownloadArtifact.objects.get().deleted_at is None


def test_job_ids_are_not_guessable_numbers(settings, member):
    enable(settings)
    job_id = request_download(member).json()["data"]["id"]
    assert len(job_id) == 36 and job_id.count("-") == 4
    assert client_for(member).get(V + "downloads/1/").status_code == 404


# ------------------------------------------------------------------ limits
def test_active_job_and_daily_limits(settings, member, monkeypatch):
    enable(settings)
    monkeypatch.setattr(download_jobs, "enqueue", lambda job: None)  # jobs stay queued = "active"
    assert request_download(member).status_code == 202 and request_download(member).status_code == 202
    r = request_download(member)
    assert r.status_code == 429 and r.json()["errors"]["code"] == "too_many_active"
    DownloadJob.objects.update(status="done")
    settings.VIDEO_TOOLS_MAX_JOBS_PER_DAY = 2
    r = request_download(member)
    assert r.status_code == 429 and r.json()["errors"]["code"] == "daily_limit"


def test_limits_are_per_person(settings, member, stranger, monkeypatch):
    enable(settings)
    monkeypatch.setattr(download_jobs, "enqueue", lambda job: None)
    for _ in range(2):
        request_download(member)
    assert request_download(member).status_code == 429 and request_download(stranger).status_code == 202


def test_request_rate_limit(settings, member):
    from django.core.cache import cache
    enable(settings)
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK}
    from rest_framework.throttling import SimpleRateThrottle
    SimpleRateThrottle.THROTTLE_RATES = {**SimpleRateThrottle.THROTTLE_RATES, "video_download": "2/hour"}
    try:
        cache.clear()
        codes = [request_download(member, url=f"https://youtu.be/dQw4w9WgX{c}Q").status_code for c in "abcd"]
        assert codes == [202, 202, 429, 429]
    finally:
        SimpleRateThrottle.THROTTLE_RATES["video_download"] = "10/hour"


# ------------------------------------------------------------------ cancel, expiry, cleanup
def test_delete_cancels_a_queued_job_and_removes_a_finished_file(settings, member, monkeypatch):
    enable(settings)
    c = client_for(member)
    monkeypatch.setattr(download_jobs, "enqueue", lambda job: None)
    queued = request_download(member).json()["data"]["id"]
    assert c.delete(V + f"downloads/{queued}/").status_code == 204
    assert DownloadJob.objects.get(pk=queued).status == "cancelled"
    assert download_jobs.run_job(queued) is None  # a cancelled job never runs
    monkeypatch.undo()
    done = request_download(member, url="https://youtu.be/aaaaaaaaaaa").json()["data"]["id"]
    path = DownloadArtifact.objects.get(job_id=done).file.path
    assert os.path.exists(path) and c.delete(V + f"downloads/{done}/").status_code == 204
    assert not os.path.exists(path) and DownloadJob.objects.get(pk=done).status == "expired"
    assert c.get(V + f"downloads/{done}/file/").status_code == 404


def test_expired_files_are_refused_at_once_and_removed_by_cleanup(settings, member):
    enable(settings)
    job_id = request_download(member).json()["data"]["id"]
    art = DownloadArtifact.objects.get()
    path = art.file.path
    DownloadArtifact.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert client_for(member).get(V + f"downloads/{job_id}/file/").status_code == 404  # even before cleanup runs
    assert os.path.exists(path)
    result = download_jobs.cleanup()
    assert result["files_removed"] == 1 and not os.path.exists(path)
    assert DownloadJob.objects.get(pk=job_id).status == "expired" and client_for(member).get(V + f"downloads/{job_id}/").json()["data"]["artifact"] is None
    assert download_jobs.cleanup()["files_removed"] == 0  # idempotent


def test_cleanup_fails_stuck_jobs_and_forgets_old_records(settings, member, monkeypatch):
    enable(settings)
    monkeypatch.setattr(download_jobs, "enqueue", lambda job: None)
    stuck = request_download(member).json()["data"]["id"]
    DownloadJob.objects.filter(pk=stuck).update(created_at=timezone.now() - timedelta(seconds=settings.VIDEO_TOOLS_TIMEOUT_SECONDS * 3))
    assert download_jobs.cleanup()["stuck_failed"] == 1
    assert DownloadJob.objects.get(pk=stuck).error_code == "timeout"
    DownloadJob.objects.filter(pk=stuck).update(created_at=timezone.now() - timedelta(days=settings.VIDEO_TOOLS_JOB_RETENTION_DAYS + 1))
    assert download_jobs.cleanup()["jobs_forgotten"] == 1 and DownloadJob.objects.count() == 0


def test_if_the_queue_is_down_the_job_fails_cleanly_instead_of_hanging(settings, member, monkeypatch):
    enable(settings)
    settings.VIDEO_TOOLS_RUN_INLINE = False
    import apps.video_tools.tasks as tasks
    monkeypatch.setattr(tasks.process_download_job, "delay", lambda *a: (_ for _ in ()).throw(ConnectionError("redis down")))
    d = request_download(member).json()["data"]
    assert d["status"] == "failed" and d["error_code"] == "queue_unavailable"


def test_management_command_runs(settings, member):
    from django.core.management import call_command
    from io import StringIO
    out = StringIO()
    call_command("cleanup_video_downloads", stdout=out)
    assert "files_removed=0" in out.getvalue()


def test_the_feature_can_be_switched_off(settings, member):
    settings.VIDEO_TOOLS_ENABLED = False
    assert APIClient().post(V + "inspect/", {"url": YT}, format="json").status_code == 404
    assert client_for(member).get(V + "downloads/").status_code == 404
