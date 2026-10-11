import pytest
from rest_framework.exceptions import ValidationError

from apps.stories.content import asset_ids, clean_content, empty_doc, has_content, plain_text, youtube_id

VID = "dQw4w9WgXcQ"


def doc(*blocks):
    return {"type": "doc", "content": list(blocks)}


def para(text, marks=None):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return {"type": "paragraph", "content": [node]}


def link(href):
    return [{"type": "link", "attrs": {"href": href}}]


def nested(depth):
    node = {"type": "paragraph"}
    for _ in range(depth):
        node = {"type": "blockquote", "content": [node]}
    return doc(node)


def test_valid_document_passes_unchanged():
    d = doc(para("Hello"), {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Title"}]})
    assert clean_content(d) == d


def test_empty_doc_is_valid():
    assert clean_content(empty_doc())["type"] == "doc"


@pytest.mark.parametrize("bad", [None, [], "text", {"type": "paragraph"}, {"content": []}])
def test_root_must_be_a_doc(bad):
    with pytest.raises(ValidationError):
        clean_content(bad)


def test_unknown_node_rejected():
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "script"}))
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "iframe", "attrs": {"src": "https://evil.example"}}))


def test_unknown_mark_rejected():
    with pytest.raises(ValidationError):
        clean_content(doc(para("x", [{"type": "code"}])))


@pytest.mark.parametrize("href", ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<b>x</b>", "ftp://x.example", "/relative", "https://a b.example", "https://x.example\n"])
def test_unsafe_links_rejected(href):
    with pytest.raises(ValidationError):
        clean_content(doc(para("x", link(href))))


@pytest.mark.parametrize("href", ["https://example.com/a?b=c", "http://example.com", "mailto:me@example.com", "HTTPS://EXAMPLE.COM"])
def test_safe_links_accepted(href):
    cleaned = clean_content(doc(para("x", link(href))))
    assert cleaned["content"][0]["content"][0]["marks"] == link(href)


def test_link_marks_drop_extra_attributes():
    marks = [{"type": "link", "attrs": {"href": "https://example.com", "target": "_self", "onclick": "x()"}}]
    cleaned = clean_content(doc(para("x", marks)))
    assert cleaned["content"][0]["content"][0]["marks"] == link("https://example.com")


def test_unknown_attributes_are_dropped():
    d = doc({"type": "paragraph", "attrs": {"onclick": "x()", "style": "color:red", "textAlign": "center"}, "content": [{"type": "text", "text": "a"}]})
    assert clean_content(d)["content"][0]["attrs"] == {"textAlign": "center"}
    plain = clean_content(doc({"type": "paragraph", "attrs": {"onclick": "x()"}}))
    assert "attrs" not in plain["content"][0]


def test_invalid_alignment_and_heading_level():
    assert "attrs" not in clean_content(doc({"type": "paragraph", "attrs": {"textAlign": "evil"}}))["content"][0]
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "heading", "attrs": {"level": 7}}))
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "heading", "attrs": {"level": True}}))


@pytest.mark.parametrize("src", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?feature=share&v={VID}",
    f"https://m.youtube.com/watch?v={VID}&t=5",
    f"https://youtu.be/{VID}?t=3",
    f"https://www.youtube.com/embed/{VID}",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube-nocookie.com/embed/{VID}",
])
def test_youtube_url_variants_give_the_same_video_id(src):
    cleaned = clean_content(doc({"type": "youtube", "attrs": {"src": src, "width": 640, "onload": "x()"}}))
    assert cleaned["content"][0] == {"type": "youtube", "attrs": {"videoId": VID}}


def test_youtube_accepts_video_id_directly():
    assert clean_content(doc({"type": "youtube", "attrs": {"videoId": VID}}))["content"][0]["attrs"] == {"videoId": VID}


@pytest.mark.parametrize("src", [
    f"https://evil.example/watch?v={VID}",
    f"https://youtube.com.evil.example/watch?v={VID}",
    f"http://www.youtube.com/watch?v={VID}",  # https only
    "https://www.youtube.com/watch?v=short",
    "",
])
def test_non_youtube_sources_rejected(src):
    assert youtube_id(src) is None
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "youtube", "attrs": {"src": src}}))


def test_image_extra_attributes_dropped_and_defaults_applied():
    d = doc({"type": "image", "attrs": {"assetId": 5, "src": "https://evil.example/x.png", "style": "x", "onclick": "y", "alt": "A cat"}})
    assert clean_content(d)["content"][0]["attrs"] == {"assetId": 5, "alt": "A cat", "caption": "", "align": "center", "size": "full"}


def test_image_options_validated():
    d = doc({"type": "image", "attrs": {"assetId": 1, "align": "left", "size": "small", "caption": "c"}})
    attrs = clean_content(d)["content"][0]["attrs"]
    assert (attrs["align"], attrs["size"], attrs["caption"]) == ("left", "small", "c")
    odd = clean_content(doc({"type": "image", "attrs": {"assetId": 1, "align": "float", "size": "huge"}}))["content"][0]["attrs"]
    assert (odd["align"], odd["size"]) == ("center", "full")


@pytest.mark.parametrize("asset_id", ["5", 0, -1, True, None, 1.5])
def test_bad_image_asset_id_rejected(asset_id):
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "image", "attrs": {"assetId": asset_id}}))
    with pytest.raises(ValidationError):
        clean_content(doc({"type": "image"}))


def test_depth_limit():
    clean_content(nested(11))  # innermost paragraph sits at depth 12: allowed
    with pytest.raises(ValidationError):
        clean_content(nested(12))


def test_node_count_limit():
    with pytest.raises(ValidationError):
        clean_content(doc(*[{"type": "paragraph"} for _ in range(5001)]))


def test_text_node_length_limit():
    clean_content(doc(para("a" * 20000)))
    with pytest.raises(ValidationError):
        clean_content(doc(para("a" * 20001)))


def test_oversized_document_rejected():
    big = doc(*[para("a" * 20000) for _ in range(60)])  # ~1.2 MB, each node individually fine
    with pytest.raises(ValidationError) as exc:
        clean_content(big)
    assert "too large" in str(exc.value)


def test_plain_text_and_has_content():
    d = doc(para("Hello"), {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "World"}]})
    assert plain_text(d) == "Hello\nWorld"
    assert plain_text(None) == ""
    assert has_content(d)
    assert not has_content(empty_doc())
    assert not has_content(doc(para("   ")))
    assert has_content(doc({"type": "youtube", "attrs": {"videoId": VID}}))
    assert has_content(doc({"type": "image", "attrs": {"assetId": 3}}))


def test_asset_ids():
    d = doc({"type": "image", "attrs": {"assetId": 3}}, {"type": "blockquote", "content": [{"type": "image", "attrs": {"assetId": 8}}]})
    assert asset_ids(d) == {3, 8}
