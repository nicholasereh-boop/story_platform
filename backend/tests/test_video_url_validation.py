"""Link validation: the five platforms' real link shapes, and everything that must be refused."""
import pytest

from apps.video_tools.services.url_validation import InvalidVideoUrl, parse_video_url

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url,provider,content_id,canonical,short", [
    (f"https://www.youtube.com/watch?v={VID}", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://youtube.com/watch?v={VID}&t=42s&list=PLx&utm_source=a", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://m.youtube.com/watch?feature=share&v={VID}", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://youtu.be/{VID}?si=trackingtoken", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://www.youtube.com/shorts/{VID}", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://www.youtube.com/live/{VID}", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://www.youtube.com/embed/{VID}", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    ("https://www.facebook.com/watch/?v=1234567890123", "facebook", "1234567890123", "https://www.facebook.com/watch/?v=1234567890123", False),
    ("https://www.facebook.com/reel/1234567890123?mibextid=x", "facebook", "1234567890123", "https://www.facebook.com/reel/1234567890123", False),
    ("https://www.facebook.com/SomePage/videos/1234567890123/", "facebook", "1234567890123", "https://www.facebook.com/watch/?v=1234567890123", False),
    ("https://web.facebook.com/SomePage/videos/title-slug/1234567890123", "facebook", "1234567890123", "https://www.facebook.com/watch/?v=1234567890123", False),
    ("https://m.facebook.com/video.php?v=1234567890123", "facebook", "1234567890123", "https://www.facebook.com/watch/?v=1234567890123", False),
    ("https://fb.watch/abcDEF12_x/", "facebook", "abcDEF12_x", "https://fb.watch/abcDEF12_x/", True),
    ("https://www.facebook.com/share/v/1AbCdEfGhI/", "facebook", "1AbCdEfGhI", "https://www.facebook.com/share/v/1AbCdEfGhI/", True),
    ("https://www.instagram.com/reel/C1a2B3c4D5e/?igsh=abc", "instagram", "C1a2B3c4D5e", "https://www.instagram.com/reel/C1a2B3c4D5e/", False),
    ("https://www.instagram.com/someone/reel/C1a2B3c4D5e/", "instagram", "C1a2B3c4D5e", "https://www.instagram.com/reel/C1a2B3c4D5e/", False),
    ("https://instagram.com/p/C1a2B3c4D5e", "instagram", "C1a2B3c4D5e", "https://www.instagram.com/p/C1a2B3c4D5e/", False),
    ("https://www.instagram.com/tv/C1a2B3c4D5e/", "instagram", "C1a2B3c4D5e", "https://www.instagram.com/tv/C1a2B3c4D5e/", False),
    ("https://www.tiktok.com/@some.user_1/video/7234567890123456789?is_from_webapp=1", "tiktok", "7234567890123456789", "https://www.tiktok.com/@some.user_1/video/7234567890123456789", False),
    ("https://vm.tiktok.com/ZMabc123/", "tiktok", "ZMabc123", "https://vm.tiktok.com/ZMabc123/", True),
    ("https://www.tiktok.com/t/ZTabc123/", "tiktok", "ZTabc123", "https://www.tiktok.com/t/ZTabc123/", True),
    ("https://x.com/someone/status/1234567890123456789", "x", "1234567890123456789", "https://x.com/someone/status/1234567890123456789", False),
    ("https://twitter.com/someone/status/1234567890123456789?s=20&t=abc", "x", "1234567890123456789", "https://x.com/someone/status/1234567890123456789", False),
    ("https://mobile.twitter.com/someone/status/1234567890123456789/video/1", "x", "1234567890123456789", "https://x.com/someone/status/1234567890123456789", False),
    ("https://x.com/i/status/1234567890123456789", "x", "1234567890123456789", "https://x.com/i/status/1234567890123456789", False),
    ("  https://WWW.YouTube.com/watch?v=" + VID + "  ", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://www.youtube.com./watch?v={VID}", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
    (f"https://www.youtube.com:443/watch?v={VID}", "youtube", VID, f"https://www.youtube.com/watch?v={VID}", False),
])
def test_real_link_shapes_are_recognised_and_reduced_to_a_canonical_link(url, provider, content_id, canonical, short):
    p = parse_video_url(url)
    assert (p.provider, p.content_id, p.canonical_url, p.needs_resolution) == (provider, content_id, canonical, short)
    assert "utm" not in p.canonical_url and "?si=" not in p.canonical_url and "igsh" not in p.canonical_url  # tracking parameters never travel on


@pytest.mark.parametrize("url,code", [
    # not https / not a web link at all
    ("http://www.youtube.com/watch?v=" + VID, "scheme"), ("ftp://www.youtube.com/watch?v=" + VID, "scheme"),
    ("javascript:alert(1)", "scheme"), ("file:///etc/passwd", "scheme"), ("data:text/html,<script>alert(1)</script>", "scheme"),
    ("//www.youtube.com/watch?v=" + VID, "scheme"), ("www.youtube.com/watch?v=" + VID, "scheme"), ("youtube.com", "scheme"),
    # hosts that merely LOOK like a platform
    ("https://youtube.com.evil.example/watch?v=" + VID, "unsupported_host"), ("https://evil.example/youtube.com/watch?v=" + VID, "unsupported_host"),
    ("https://notyoutube.com/watch?v=" + VID, "unsupported_host"), ("https://youtube.com.attacker.io/", "unsupported_host"),
    ("https://evilyoutu.be/" + VID, "unsupported_host"), ("https://youtu.be.evil.example/" + VID, "unsupported_host"),
    ("https://fb.watch.evil.example/abcd/", "unsupported_host"), ("https://xx.com/a/status/12345678", "unsupported_host"),
    ("https://cdn.youtube.com/watch?v=" + VID, "unsupported_host"), ("https://drive.google.com/file/d/abc", "unsupported_host"),
    # credentials, ports, IPs and other address tricks
    ("https://www.youtube.com@evil.example/watch?v=" + VID, "credentials"), ("https://user:pass@www.youtube.com/watch?v=" + VID, "credentials"),
    ("https://www.youtube.com:8443/watch?v=" + VID, "port"), ("https://www.youtube.com:80/watch?v=" + VID, "port"),
    ("https://127.0.0.1/watch?v=" + VID, "ip_address"), ("https://169.254.169.254/latest/meta-data/", "ip_address"),
    ("https://[::1]/watch?v=" + VID, "ip_address"), ("https://10.0.0.5/", "ip_address"), ("https://2130706433/", "unsupported_host"),
    ("https://0x7f.0.0.1/", "unsupported_host"), ("https://localhost/", "unsupported_host"),
    ("https://www.yоutube.com/watch?v=" + VID, "host"),  # Cyrillic "о": a look-alike, not ASCII
    ("https://www.youtube.com\u3002evil.example/", "host"),
    # control characters, whitespace, backslashes, encoded tricks
    ("https://www.youtube.com/watch?v=" + VID + "\nHost: evil", "malformed"), ("https://www.youtube.com/wa tch?v=" + VID, "malformed"),
    ("https://www.youtube.com\\@evil.example/watch?v=" + VID, "malformed"), ("https://www.youtube.com/watch?v=" + VID + "\x00", "malformed"),
    ("https://www.youtube.com/%2e%2e/watch?v=" + VID, "unsupported_link"), ("https://www.youtube.com//watch?v=" + VID, "unsupported_link"),
    ("https://www.youtube.com/shorts/../" + VID, "unsupported_link"),
    # the right platform, but not a single video
    ("https://www.youtube.com/", "unsupported_link"), ("https://www.youtube.com/@somechannel", "unsupported_link"),
    ("https://www.youtube.com/playlist?list=PLabc", "unsupported_link"), ("https://www.youtube.com/watch?v=short", "unsupported_link"),
    ("https://www.youtube.com/watch?v=" + VID + "x", "unsupported_link"), ("https://www.facebook.com/SomePage", "unsupported_link"),
    ("https://www.instagram.com/someone/", "unsupported_link"), ("https://www.tiktok.com/@someone", "unsupported_link"),
    ("https://x.com/someone", "unsupported_link"), ("https://x.com/someone/status/abc", "unsupported_link"),
    ("https://x.com/this_username_is_way_too_long/status/1234567890", "unsupported_link"),
    # nonsense
    ("", "malformed"), ("   ", "malformed"), ("not a url", "malformed"), ("https://", "host"), ("https:///watch?v=" + VID, "host"),
    ("https://www.youtube.com/watch?v=" + VID + "&" + "a=" * 2000, "malformed"),
])
def test_everything_else_is_refused_with_a_stable_code(url, code):
    with pytest.raises(InvalidVideoUrl) as err:
        parse_video_url(url)
    assert err.value.code == code and err.value.message


@pytest.mark.parametrize("value", [None, 123, ["https://youtu.be/dQw4w9WgXcQ"], {"url": "x"}, b"https://youtu.be/dQw4w9WgXcQ"])
def test_non_strings_are_refused(value):
    with pytest.raises(InvalidVideoUrl):
        parse_video_url(value)


def test_validation_never_touches_the_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    parse_video_url("https://youtu.be/dQw4w9WgXcQ")
    with pytest.raises(InvalidVideoUrl):
        parse_video_url("https://evil.example/")
