"""GitHub import: repository parsing, host allow-list, manual redirects, token handling, size cap."""
import pytest
import requests

from apps.source_marketplace.services import github

OK_ZIP = b"PK\x05\x06" + b"\x00" * 18


class Resp:
    def __init__(self, status=200, headers=None, body=OK_ZIP):
        self.status_code, self.headers, self._body, self.closed = status, headers or {}, body, False

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, headers=None, **kw):
        self.calls.append((url, dict(headers or {}), kw))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.mark.parametrize("value,ref,expected", [
    ("acme/shop", "", ("acme", "shop", "")),
    ("https://github.com/acme/shop", "", ("acme", "shop", "")),
    ("https://github.com/acme/shop.git", "", ("acme", "shop", "")),
    ("https://www.github.com/acme/shop/tree/feature/x", "", ("acme", "shop", "feature/x")),
    ("acme/shop", "v1.2.0", ("acme", "shop", "v1.2.0")),
    ("  acme/my.repo_name-2  ", "main", ("acme", "my.repo_name-2", "main")),
])
def test_parse_accepts_normal_repositories(value, ref, expected):
    assert github.parse_repository(value, ref) == expected


@pytest.mark.parametrize("value", [
    "", "acme", "http://github.com/acme/shop", "https://evil.example/acme/shop", "https://github.com.evil.example/acme/shop",
    "https://github.com@evil.example/acme/shop", "acme/../etc", "-acme/shop", "acme/shop;rm", "file:///etc/passwd", "../../x",
])
def test_parse_rejects_everything_else(value):
    with pytest.raises(github.GitHubImportError):
        github.parse_repository(value)


@pytest.mark.parametrize("ref", ["../main", "a..b", "/abs", "x" * 101, "bad ref", "ref;ls", "main/"])
def test_parse_rejects_dangerous_refs(ref):
    with pytest.raises(github.GitHubImportError):
        github.parse_repository("acme/shop", ref)


def test_token_shape_is_checked_and_blank_means_public():
    assert github.clean_token("") == "" and github.clean_token(None) == ""
    assert github.clean_token("github_pat_ABC123def456") == "github_pat_ABC123def456"
    for bad in ["has space token1", "tok\nen12345678", "short", "ghp_$(whoami)abcdef"]:
        with pytest.raises(github.GitHubImportError):
            github.clean_token(bad)


def test_public_download_follows_only_the_codeload_redirect_and_never_sends_the_token_there():
    s = Session(Resp(302, {"Location": "https://codeload.github.com/acme/shop/legacy.zip/refs/heads/main"}), Resp(200))
    out = github.download_zipball("acme", "shop", "main", "github_pat_SECRETTOKEN123", session=s)
    assert out.read() == OK_ZIP
    first, second = s.calls
    assert first[0] == "https://api.github.com/repos/acme/shop/zipball/main" and first[1]["Authorization"] == "Bearer github_pat_SECRETTOKEN123"
    assert second[0].startswith("https://codeload.github.com/") and "Authorization" not in second[1]
    assert all(c[2]["allow_redirects"] is False and c[2]["timeout"] for c in s.calls)


@pytest.mark.parametrize("location", [
    "https://evil.example/x.zip", "http://codeload.github.com/x.zip", "https://127.0.0.1/x.zip", "https://169.254.169.254/latest/meta-data",
    "https://codeload.github.com.evil.example/x.zip", "https://user@codeload.github.com/x.zip", "https://codeload.github.com:8443/x.zip",
    "file:///etc/passwd", "",
])
def test_a_redirect_anywhere_else_stops_the_import_and_is_never_requested(location):
    s = Session(Resp(302, {"Location": location}))
    with pytest.raises(github.GitHubImportError, match="do not allow"):
        github.download_zipball("acme", "shop", session=s)
    assert len(s.calls) == 1  # the bad address was NOT fetched


def test_redirect_loops_are_capped():
    loop = [Resp(302, {"Location": "https://codeload.github.com/x"}) for _ in range(10)]
    with pytest.raises(github.GitHubImportError, match="too many"):
        github.download_zipball("acme", "shop", session=Session(*loop))


@pytest.mark.parametrize("status,headers,text", [
    (404, {}, "private"), (401, {}, "token"), (403, {"X-RateLimit-Remaining": "0"}, "rate limit"), (429, {}, "rate limit"),
    (403, {}, "refused"), (500, {}, "try again"),
])
def test_friendly_errors_that_never_contain_the_token(status, headers, text):
    token = "github_pat_NEVERSHOWTHIS99"
    with pytest.raises(github.GitHubImportError) as err:
        github.download_zipball("acme", "shop", token=token, session=Session(Resp(status, headers)))
    assert text in err.value.message.lower() and token not in err.value.message


def test_size_cap_applies_to_the_declared_and_the_streamed_size():
    with pytest.raises(github.GitHubImportError, match="larger"):
        github.download_zipball("acme", "shop", max_bytes=10, session=Session(Resp(200, {"Content-Length": "999"})))
    with pytest.raises(github.GitHubImportError, match="larger"):
        github.download_zipball("acme", "shop", max_bytes=10, session=Session(Resp(200, {}, body=b"x" * 500)))  # header absent or lying


def test_network_failures_become_a_friendly_error():
    with pytest.raises(github.GitHubImportError, match="Could not reach"):
        github.download_zipball("acme", "shop", session=Session(requests.ConnectionError("boom")))
