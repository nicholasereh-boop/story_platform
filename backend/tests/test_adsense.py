import io
import json
from datetime import date
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from apps.analytics import adsense as ads

PAGE = """
<html><head>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1234567890123456" crossorigin="anonymous"></script>
</head><body>
<ins class="adsbygoogle top" data-ad-client="ca-pub-1234567890123456" data-ad-slot="111" data-ad-status="filled"></ins>
<p>text with the words adsbygoogle in it</p>
<INS CLASS="adsbygoogle" data-ad-slot="222" data-ad-status="unfilled"></INS>
<ins class="not-an-ad"></ins>
<div class="adsbygoogle"></div>
</body></html>
"""


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def reply(payload):
    return FakeResponse(json.dumps(payload).encode())


# ---- ads placed on a page
def test_counts_only_real_ad_units():
    r = ads.count_ads_in_html(PAGE)
    assert r["ad_units"] == 2  # not the plain text, not the <div>, not the other <ins>
    assert (r["filled"], r["unfilled"]) == (1, 1)
    assert r["slots"] == ["111", "222"]
    assert r["publisher_ids"] == ["ca-pub-1234567890123456"]
    assert r["script_found"] and r["auto_ads_possible"]


def test_empty_and_odd_input_gives_zero():
    for value in ("", None, 5, "<p>no ads</p>", "<ins class='adsbygoogle'"):
        assert ads.count_ads_in_html(value)["ad_units"] in (0, 1)
    assert ads.count_ads_in_html("<p>no ads</p>")["ad_units"] == 0
    assert ads.count_ads_in_html("")["script_found"] is False


def test_pages_total_and_errors_do_not_stop_the_rest():
    pages = {"https://a.example/1": PAGE, "https://a.example/2": "<p>none</p>"}

    def fake_fetch(url, timeout):
        if url.endswith("/boom"):
            raise URLError("down")
        return pages[url]

    out = ads.count_ads_on_pages(["https://a.example/1", "https://a.example/boom", "https://a.example/2", "ftp://a.example/x", "file:///etc/passwd"], fetch=fake_fetch)
    assert out["total"] == 2
    by_url = {p["url"]: p for p in out["pages"]}
    assert by_url["https://a.example/1"]["ad_units"] == 2
    assert "URLError" in by_url["https://a.example/boom"]["error"]
    assert by_url["ftp://a.example/x"]["error"].startswith("Only http")
    assert by_url["file:///etc/passwd"]["error"].startswith("Only http")


def test_allowed_hosts_blocks_other_hosts():
    called = []
    out = ads.count_ads_on_pages(["https://evil.example/", "https://ok.example/"], allowed_hosts={"OK.example"}, fetch=lambda u, t: called.append(u) or "")
    assert called == ["https://ok.example/"]
    assert out["pages"][0]["error"] == "That host is not allowed."


# ---- impressions from Google
def test_report_builds_the_right_request_and_reads_totals():
    seen = {}

    def fake_urlopen(request, timeout=0):
        seen["url"], seen["auth"] = request.full_url, request.get_header("Authorization")
        return reply({"headers": [{"name": "IMPRESSIONS"}, {"name": "CLICKS"}], "totals": {"cells": [{"value": "12345"}, {"value": "67"}]}})

    with patch.object(ads, "urlopen", fake_urlopen):
        out = ads.fetch_adsense_report("pub-1234567890123456", "tok", date(2026, 9, 1), date(2026, 9, 30), ("impressions", "clicks"))
    assert out == {"IMPRESSIONS": 12345, "CLICKS": 67}
    assert seen["auth"] == "Bearer tok"
    assert "/accounts/pub-1234567890123456/reports:generate?" in seen["url"]
    assert "startDate.month=9" in seen["url"] and "endDate.day=30" in seen["url"] and seen["url"].count("metrics=") == 2


def test_report_with_no_data_is_zero():
    with patch.object(ads, "urlopen", lambda *a, **k: reply({})):
        assert ads.fetch_adsense_report("accounts/pub-1234567890123456", "t", date(2026, 1, 1), date(2026, 1, 2)) == {"IMPRESSIONS": 0}


@pytest.mark.parametrize("account", ["", "1234", "pub-12", "pub-1234567890/../x", None])
def test_bad_account_ids_are_refused_before_any_request(account):
    with patch.object(ads, "urlopen", side_effect=AssertionError("no request expected")):
        with pytest.raises(ads.AdSenseError):
            ads.fetch_adsense_report(account, "t", date(2026, 1, 1), date(2026, 1, 2))


def test_bad_metric_and_dates_are_refused():
    with pytest.raises(ads.AdSenseError):
        ads.fetch_adsense_report("pub-1234567890123456", "t", date(2026, 1, 1), date(2026, 1, 2), ("EVIL",))
    with pytest.raises(ads.AdSenseError):
        ads.fetch_adsense_report("pub-1234567890123456", "t", date(2026, 2, 1), date(2026, 1, 1))


def test_google_errors_become_plain_messages_without_the_token():
    def deny(*a, **k):
        raise HTTPError("u", 403, "forbidden", {}, io.BytesIO(b"secret-detail"))

    with patch.object(ads, "urlopen", deny):
        with pytest.raises(ads.AdSenseError) as e:
            ads.fetch_adsense_report("pub-1234567890123456", "super-secret-token", date(2026, 1, 1), date(2026, 1, 2))
    assert "403" in str(e.value) and "super-secret-token" not in str(e.value) and "secret-detail" not in str(e.value)


def test_refresh_token_flow_and_failures():
    with patch.object(ads, "urlopen", lambda *a, **k: reply({"access_token": "abc"})):
        assert ads.refresh_access_token("id", "secret", "refresh") == "abc"
    with patch.object(ads, "urlopen", lambda *a, **k: reply({})):
        with pytest.raises(ads.AdSenseError):
            ads.refresh_access_token("id", "secret", "refresh")

    def deny(*a, **k):
        raise HTTPError("u", 400, "bad", {}, io.BytesIO(b""))

    with patch.object(ads, "urlopen", deny):
        with pytest.raises(ads.AdSenseError) as e:
            ads.refresh_access_token("id", "the-client-secret", "the-refresh-token")
    assert "the-client-secret" not in str(e.value) and "the-refresh-token" not in str(e.value)


ENV = {"ADSENSE_ACCOUNT_ID": "pub-1234567890123456", "ADSENSE_CLIENT_ID": "i", "ADSENSE_CLIENT_SECRET": "s", "ADSENSE_REFRESH_TOKEN": "r"}


def test_count_ads_shown_uses_the_last_days_ending_yesterday():
    calls = {}

    def fake_report(account, token, start, end, metrics):
        calls.update(account=account, token=token, start=start, end=end, metrics=metrics)
        return {"IMPRESSIONS": 4321.0}

    n = ads.count_ads_shown(days=7, today=date(2026, 10, 15), environ=ENV, report=fake_report, token=lambda *a: "access")
    assert n == 4321 and isinstance(n, int)
    assert (calls["start"], calls["end"]) == (date(2026, 10, 8), date(2026, 10, 14))
    assert calls["token"] == "access" and calls["metrics"] == ("IMPRESSIONS",)


def test_count_ads_shown_reports_missing_settings_and_bad_days():
    with pytest.raises(ads.AdSenseError) as e:
        ads.count_ads_shown(environ={"ADSENSE_ACCOUNT_ID": "pub-1234567890123456"})
    assert "ADSENSE_CLIENT_SECRET" in str(e.value)
    for bad in (0, 366, "30", True and 0):
        with pytest.raises(ads.AdSenseError):
            ads.count_ads_shown(days=bad, environ=ENV)
