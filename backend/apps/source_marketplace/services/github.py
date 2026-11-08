"""Import a repository from GitHub as a ZIP.

Safety rules (see docs/extension road map/ARCHITECTURE.md):
  * only api.github.com is called, and only codeload.github.com may be followed from its redirect: no other host,
    scheme or port is ever contacted, whatever the seller types;
  * redirects are followed by hand, one hop at a time, each hop re-checked;
  * the seller's access token (needed only for a private repository) is sent to api.github.com ALONE, is never
    stored, never logged, never put in an error message and never returned. Use a read-only, single-repository,
    short-lived token;
  * the download is streamed with a hard byte limit.
"""
import re
import tempfile
from urllib.parse import quote, urlparse

import requests
from django.conf import settings

API_HOST = "api.github.com"
DOWNLOAD_HOSTS = {"codeload.github.com"}
MAX_REDIRECTS = 3
OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
REF_RE = re.compile(r"^[A-Za-z0-9._/\-]{1,100}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{10,255}$")
URL_RE = re.compile(r"^https://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:/(?:tree|blob)/([^\s#?]+))?/?$")


class GitHubImportError(Exception):
    """Safe to show to the seller."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_repository(value, ref=""):
    """("owner", "repo", "ref") from `owner/repo` or a github.com URL. Raises GitHubImportError when it is neither."""
    text = str(value or "").strip()
    ref = str(ref or "").strip()
    url_ref = ""
    match = URL_RE.match(text)
    if match:
        owner, repo, url_ref = match.group(1), match.group(2), match.group(3) or ""
    else:
        pair = re.fullmatch(r"([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?", text)
        if not pair:
            raise GitHubImportError("Enter a repository as owner/name or as a https://github.com/owner/name address.")
        owner, repo = pair.group(1), pair.group(2)
    ref = ref or url_ref
    if not OWNER_RE.match(owner) or not REPO_RE.match(repo) or repo in (".", ".."):
        raise GitHubImportError("That repository name is not valid.")
    if ref and (not REF_RE.match(ref) or ".." in ref or ref.startswith("/") or ref.endswith("/")):
        raise GitHubImportError("That branch, tag or commit name is not valid.")
    return owner, repo, ref


def clean_token(value):
    token = str(value or "").strip()
    if not token:
        return ""
    if not TOKEN_RE.match(token):
        raise GitHubImportError("That access token does not look right. Paste only the token itself.")
    return token


def _allowed(url):
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and parts.port in (None, 443) and not parts.username and host in ({API_HOST} | DOWNLOAD_HOSTS)


def download_zipball(owner, repo, ref="", token="", *, session=None, max_bytes=None, timeout=None):
    """Download the repository ZIP into a temporary file and return it (positioned at 0). The caller closes it."""
    session = session or requests.Session()
    max_bytes = int(max_bytes or settings.MARKETPLACE_MAX_ARCHIVE_BYTES)
    timeout = timeout or int(settings.MARKETPLACE_GITHUB_TIMEOUT)
    url = f"https://{API_HOST}/repos/{quote(owner)}/{quote(repo)}/zipball" + (f"/{quote(ref, safe='/')}" if ref else "")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ResourceBoard-importer"}
    bearer = f"Bearer {token}" if token else None

    response = None
    try:
        for hop in range(MAX_REDIRECTS + 1):
            if not _allowed(url):
                raise GitHubImportError("GitHub sent us somewhere we do not allow, so the import was stopped.", 502)
            hop_headers = dict(headers)
            if bearer and urlparse(url).hostname == API_HOST:  # the token never travels to the download host
                hop_headers["Authorization"] = bearer
            response = session.get(url, headers=hop_headers, stream=True, allow_redirects=False, timeout=timeout)
            if response.status_code in (301, 302, 303, 307, 308):
                url = response.headers.get("Location", "")
                response.close()
                continue
            break
        else:
            raise GitHubImportError("GitHub redirected too many times.", 502)

        status = response.status_code
        if status == 404:
            raise GitHubImportError(
                "Repository or branch not found. If it is private, add an access token that can read it.", 404
            )
        if status == 401:
            raise GitHubImportError("GitHub did not accept the access token.", 400)
        if status in (403, 429):
            if response.headers.get("X-RateLimit-Remaining") == "0" or status == 429:
                raise GitHubImportError("GitHub's rate limit was reached. Wait a while, or add an access token.", 429)
            raise GitHubImportError("GitHub refused access to this repository.", 403)
        if status != 200:
            raise GitHubImportError("GitHub could not provide the repository right now. Try again later.", 502)

        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise GitHubImportError("The repository is larger than the upload limit.", 413)
        out = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        received = 0
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                received += len(chunk)
                if received > max_bytes:
                    raise GitHubImportError("The repository is larger than the upload limit.", 413)
                out.write(chunk)
        except Exception:
            out.close()
            raise
        out.seek(0)
        return out
    except requests.RequestException:
        raise GitHubImportError("Could not reach GitHub. Try again in a moment.", 502)
    finally:
        if response is not None:
            response.close()
