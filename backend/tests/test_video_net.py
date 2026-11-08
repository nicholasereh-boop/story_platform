"""The safe-fetch helper adapters must use: public addresses only, allow-listed hosts, checked redirects, size and time caps."""
import os

import pytest
import requests

from apps.video_tools.services import net

OK = lambda host, port=443: {"93.184.216.34"}  # noqa: E731  a public address


class Resp:
    def __init__(self, status=200, headers=None, body=b"data"):
        self.status_code, self.headers, self.body = status, headers or {}, body

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]

    def close(self):
        pass


class Sess:
    def __init__(self, *responses):
        self.responses, self.urls = list(responses), []

    def get(self, url, **kw):
        self.urls.append(url)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.mark.parametrize("ip,public", [
    ("93.184.216.34", True), ("8.8.8.8", True), ("2606:4700:4700::1111", True),
    ("127.0.0.1", False), ("10.1.2.3", False), ("172.16.0.1", False), ("192.168.1.1", False), ("169.254.169.254", False),
    ("0.0.0.0", False), ("100.64.0.1", False), ("224.0.0.1", False), ("::1", False), ("fe80::1", False), ("fc00::1", False),
    ("::ffff:127.0.0.1", False), ("::ffff:10.0.0.1", False), ("not an ip", False), ("", False),
])
def test_public_address_rules(ip, public):
    assert net.is_public_ip(ip) is public


def test_resolution_must_be_public_for_every_address(monkeypatch):
    import socket
    answer = lambda addrs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443)) for a in addrs]  # noqa: E731
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: answer(["93.184.216.34", "10.0.0.1"]))
    with pytest.raises(net.UnsafeTarget):
        net.resolve_public("cdn.example")  # one private answer is enough to refuse (DNS-rebinding style mixes)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: answer(["93.184.216.34"]))
    assert net.resolve_public("cdn.example") == {"93.184.216.34"}
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(socket.gaierror()))
    with pytest.raises(net.UnsafeTarget):
        net.resolve_public("nope.invalid")


@pytest.mark.parametrize("url", [
    "http://cdn.example/a", "https://evil.example/a", "https://cdn.example.evil.example/a", "https://user@cdn.example/a",
    "https://cdn.example:8443/a", "file:///etc/passwd", "https://127.0.0.1/a", "ftp://cdn.example/a",
])
def test_check_target_refuses_everything_off_the_allow_list(url):
    with pytest.raises(net.UnsafeTarget):
        net.check_target(url, {"cdn.example"}, OK)


def test_download_writes_the_file(tmp_path):
    dest = tmp_path / "f.bin"
    n = net.download_to_file("https://cdn.example/a", str(dest), allowed_hosts={"cdn.example"}, max_bytes=100, session=Sess(Resp(body=b"hello")), resolver=OK)
    assert n == 5 and dest.read_bytes() == b"hello"


@pytest.mark.parametrize("location", ["https://169.254.169.254/latest/meta-data", "http://cdn.example/a", "https://evil.example/a", "file:///etc/passwd"])
def test_a_redirect_to_an_unsafe_place_is_never_requested(tmp_path, location):
    s = Sess(Resp(302, {"Location": location}))
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(tmp_path / "f"), allowed_hosts={"cdn.example"}, max_bytes=100, session=s, resolver=OK)
    assert err.value.code == "unsafe_target" and s.urls == ["https://cdn.example/a"]


def test_a_host_that_resolves_to_a_private_address_is_refused_even_if_allow_listed(tmp_path):
    def private(host, port=443):
        raise net.UnsafeTarget("private")
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(tmp_path / "f"), allowed_hosts={"cdn.example"}, max_bytes=100, session=Sess(Resp()), resolver=private)
    assert err.value.code == "unsafe_target"


def test_size_cap_redirect_cap_errors_and_partial_files_removed(tmp_path):
    dest = tmp_path / "f"
    kw = dict(allowed_hosts={"cdn.example"}, resolver=OK)
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(dest), max_bytes=10, session=Sess(Resp(body=b"x" * 500)), **kw)
    assert err.value.code == "too_large" and not os.path.exists(dest)  # partial output deleted
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(dest), max_bytes=10, session=Sess(Resp(headers={"Content-Length": "999"})), **kw)
    assert err.value.code == "too_large"
    loop = [Resp(302, {"Location": "https://cdn.example/b"}) for _ in range(8)]
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(dest), max_bytes=10, session=Sess(*loop), **kw)
    assert err.value.code == "redirects"
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(dest), max_bytes=10, session=Sess(Resp(403)), **kw)
    assert err.value.code == "not_provided"
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(dest), max_bytes=10, session=Sess(requests.ConnectionError("x")), **kw)
    assert err.value.code == "unreachable"


def test_the_deadline_stops_a_slow_download(tmp_path, monkeypatch):
    ticks = iter([0, 0, 1000, 2000, 3000])
    monkeypatch.setattr(net.time, "monotonic", lambda: next(ticks))
    with pytest.raises(net.FetchFailed) as err:
        net.download_to_file("https://cdn.example/a", str(tmp_path / "f"), allowed_hosts={"cdn.example"}, max_bytes=10**6,
                             deadline_seconds=60, session=Sess(Resp(body=b"x" * 1000000)), resolver=OK)
    assert err.value.code == "timeout" and not os.path.exists(tmp_path / "f")
