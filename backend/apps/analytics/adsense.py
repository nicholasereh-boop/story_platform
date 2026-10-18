"""AdSense helpers. Standard library only (no new dependency), nothing here runs on its own.

  count_ads_in_html(html)        how many AdSense ad units one page's HTML places (and how many of them were filled)
  count_ads_on_pages(urls)       the same for several pages, fetched over HTTP(S)
  count_ads_shown(days=30)       how many ads Google says it SHOWED, from the AdSense Management API (impressions)

Two different numbers, on purpose: "placed" is what your pages ask for, "shown" is what Google actually served. Expect
"shown" to differ (ad blockers, unfilled slots, bots, visitors who leave before the ad loads).

IMPORTANT: this React site renders in the browser, so fetching a page's raw HTML (count_ads_on_pages) sees only the empty
shell. Give count_ads_in_html the RENDERED html (for example from a headless browser) or the source of a template/component.

The impressions call needs a Google Cloud project with the AdSense Management API enabled and an OAuth refresh token with the
read-only scope https://www.googleapis.com/auth/adsense.readonly. Keep these four values on the server only (backend/.env):
  ADSENSE_ACCOUNT_ID      e.g. pub-1234567890123456
  ADSENSE_CLIENT_ID, ADSENSE_CLIENT_SECRET, ADSENSE_REFRESH_TOKEN
"""
import json
import os
import re
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ADSENSE_API = "https://adsense.googleapis.com/v2"
TOKEN_URL = "https://oauth2.googleapis.com/token"
MAX_PAGE_BYTES = 2 * 1024 * 1024  # never read more than 2 MB of a page
ACCOUNT_RE = re.compile(r"^(?:accounts/)?(pub-\d{6,20})$")
PUBLISHER_RE = re.compile(r"ca-pub-\d{6,20}")
METRICS = {"IMPRESSIONS", "AD_REQUESTS", "CLICKS", "PAGE_VIEWS", "ESTIMATED_EARNINGS"}


class AdSenseError(Exception):
    """Anything that stops a count: bad input, missing settings, a Google error. The message never contains a secret."""


# --------------------------------------------------------------------------- ads placed on a page
class _AdParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units = []  # one dict per <ins class="adsbygoogle">
        self.script_found = False
        self.publisher_ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = {k.lower(): (v or "") for k, v in attrs}
        if tag == "ins" and "adsbygoogle" in attrs.get("class", "").split():
            self.units.append({"slot": attrs.get("data-ad-slot", ""), "status": attrs.get("data-ad-status", "")})
            self.publisher_ids.update(PUBLISHER_RE.findall(attrs.get("data-ad-client", "")))
        elif tag == "script" and "googlesyndication.com/pagead/js/adsbygoogle.js" in attrs.get("src", ""):
            self.script_found = True
            self.publisher_ids.update(PUBLISHER_RE.findall(attrs.get("src", "")))


def count_ads_in_html(html):
    """Count the AdSense ad units in one page of HTML.

    Returns {"ad_units": n, "filled": n, "unfilled": n, "slots": [...], "publisher_ids": [...], "script_found": bool,
             "auto_ads_possible": bool}.
    "filled" and "unfilled" come from the data-ad-status attribute Google writes onto an ad unit AFTER it loads, so they are
    only meaningful for rendered HTML. "auto_ads_possible" means the AdSense script is present: with Auto ads, Google can add
    ads that have no <ins> tag in your own markup, and those cannot be counted here.
    """
    parser = _AdParser()
    parser.feed(html if isinstance(html, str) else "")
    parser.close()
    filled = sum(1 for unit in parser.units if unit["status"] == "filled")
    unfilled = sum(1 for unit in parser.units if unit["status"] == "unfilled")
    return {
        "ad_units": len(parser.units),
        "filled": filled,
        "unfilled": unfilled,
        "slots": [unit["slot"] for unit in parser.units if unit["slot"]],
        "publisher_ids": sorted(parser.publisher_ids),
        "script_found": parser.script_found,
        "auto_ads_possible": parser.script_found,
    }


def _download(url, timeout):
    request = Request(url, headers={"User-Agent": "StoryBoard-ad-counter/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 (scheme checked by the caller)
        raw = response.read(MAX_PAGE_BYTES + 1)
    if len(raw) > MAX_PAGE_BYTES:
        raise AdSenseError("The page is larger than 2 MB.")
    return raw.decode("utf-8", errors="replace")


def count_ads_on_pages(urls, allowed_hosts=None, timeout=10, fetch=_download):
    """Count ad units on several pages. Returns {"total": n, "pages": [{"url", "ad_units", ...} or {"url", "error"}]}.

    Only http and https are accepted. Pass allowed_hosts={"example.com"} to stop the function fetching any other host (use it
    whenever the list of urls could come from user input). One bad page never stops the others."""
    pages, total = [], 0
    for url in urls:
        parsed = urlparse(str(url))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            pages.append({"url": str(url), "error": "Only http and https addresses are allowed."})
            continue
        if allowed_hosts is not None and parsed.hostname.lower() not in {h.lower() for h in allowed_hosts}:
            pages.append({"url": str(url), "error": "That host is not allowed."})
            continue
        try:
            result = count_ads_in_html(fetch(str(url), timeout))
        except AdSenseError as exc:
            pages.append({"url": str(url), "error": str(exc)})
        except (URLError, OSError, ValueError) as exc:
            pages.append({"url": str(url), "error": f"Could not load the page ({type(exc).__name__})."})
        else:
            total += result["ad_units"]
            pages.append({"url": str(url), **result})
    return {"total": total, "pages": pages}


# --------------------------------------------------------------------------- ads shown (Google's own numbers)
def refresh_access_token(client_id, client_secret, refresh_token, timeout=15):
    """Trade the long-lived refresh token for a short-lived access token."""
    body = urlencode({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    request = Request(TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            token = json.loads(response.read().decode("utf-8")).get("access_token")
    except HTTPError as exc:
        raise AdSenseError(f"Google refused the AdSense login (HTTP {exc.code}). Check the client id, secret and refresh token.") from None
    except (URLError, OSError, ValueError):
        raise AdSenseError("Could not reach Google to log in to AdSense.") from None
    if not token:
        raise AdSenseError("Google did not return an access token.")
    return token


def fetch_adsense_report(account_id, access_token, start, end, metrics=("IMPRESSIONS",), timeout=20):
    """Call AdSense Management API v2 reports:generate and return {metric: number} totals for start..end (dates, inclusive)."""
    match = ACCOUNT_RE.match(str(account_id or "").strip())
    if not match:
        raise AdSenseError("ADSENSE_ACCOUNT_ID must look like pub-1234567890123456.")
    wanted = [m.upper() for m in metrics]
    if not wanted or any(m not in METRICS for m in wanted):
        raise AdSenseError(f"Unknown metric. Allowed: {', '.join(sorted(METRICS))}.")
    if end < start:
        raise AdSenseError("The end date is before the start date.")
    params = [
        ("dateRange", "CUSTOM"),
        ("startDate.year", start.year), ("startDate.month", start.month), ("startDate.day", start.day),
        ("endDate.year", end.year), ("endDate.month", end.month), ("endDate.day", end.day),
    ] + [("metrics", m) for m in wanted]
    url = f"{ADSENSE_API}/accounts/{match.group(1)}/reports:generate?{urlencode(params)}"
    request = Request(url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AdSenseError(f"AdSense answered with an error (HTTP {exc.code}).") from None
    except (URLError, OSError, ValueError):
        raise AdSenseError("Could not reach the AdSense API.") from None
    names = [h.get("name") for h in data.get("headers", [])]
    cells = [c.get("value", "0") for c in (data.get("totals") or {}).get("cells", [])]
    totals = {name: _number(value) for name, value in zip(names, cells)}
    return {metric: totals.get(metric, 0) for metric in wanted}


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return int(number) if number.is_integer() else number


def count_ads_shown(days=30, today=None, environ=None, report=fetch_adsense_report, token=refresh_access_token):
    """How many ads Google SHOWED on the site in the last `days` days (1 to 365, ending yesterday), as an integer.

    Reads the four ADSENSE_* values from the environment. Raises AdSenseError with a plain message when a setting is missing."""
    environ = os.environ if environ is None else environ
    if not isinstance(days, int) or not 1 <= days <= 365:
        raise AdSenseError("days must be a whole number from 1 to 365.")
    settings = {key: (environ.get(key) or "").strip() for key in ("ADSENSE_ACCOUNT_ID", "ADSENSE_CLIENT_ID", "ADSENSE_CLIENT_SECRET", "ADSENSE_REFRESH_TOKEN")}
    missing = [key for key, value in settings.items() if not value]
    if missing:
        raise AdSenseError(f"Missing settings: {', '.join(missing)}.")
    end = (today or date.today()) - timedelta(days=1)  # today's numbers are incomplete
    start = end - timedelta(days=days - 1)
    access = token(settings["ADSENSE_CLIENT_ID"], settings["ADSENSE_CLIENT_SECRET"], settings["ADSENSE_REFRESH_TOKEN"])
    return int(report(settings["ADSENSE_ACCOUNT_ID"], access, start, end, ("IMPRESSIONS",))["IMPRESSIONS"])
