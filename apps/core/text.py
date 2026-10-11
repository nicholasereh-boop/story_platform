"""Plain-text cleaning for short user-supplied fields (display names, bios, image captions).

These fields are shown as TEXT everywhere (React escapes them), so cleaning is defence in depth, not the only
protection. The rules:
  - control characters are removed (newlines and tabs only where the field allows them),
  - invisible characters that can disguise text are removed: bidirectional overrides (U+202A-U+202E, U+2066-U+2069),
    the byte-order mark (U+FEFF) and the Unicode line/paragraph separators (U+2028, U+2029),
  - markup-looking text is refused: "<" and ">" are not allowed at all.
"""
import re
import unicodedata

from rest_framework import serializers

# Characters that reorder or hide text. (U+200D, the zero-width joiner, is kept: emoji sequences need it.)
_STRIP = {chr(c) for c in (0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF, 0x2028, 0x2029)}

MARKUP_MESSAGE = "Please remove the characters < and > (formatting is not supported here)."


def strip_unsafe_chars(value, *, multiline=False):
    """Remove control and disguising characters. Single-line text also has its whitespace collapsed."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for ch in text:
        if ch in _STRIP:
            continue
        if unicodedata.category(ch) == "Cc":
            if multiline and ch == "\n":
                out.append(ch)
            else:
                out.append(" ")  # a tab or newline inside a single-line field becomes a space
            continue
        out.append(ch)
    cleaned = "".join(out)
    if multiline:
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
        return cleaned.strip()
    return re.sub(r" {2,}", " ", cleaned).strip()


def clean_plain_text(value, *, max_length, multiline=False, allow_blank=True):
    """Clean `value` and validate it. Raises a DRF ValidationError (so serializers can call it directly)."""
    text = strip_unsafe_chars(value, multiline=multiline)
    if "<" in text or ">" in text:
        raise serializers.ValidationError(MARKUP_MESSAGE)
    if len(text) > max_length:
        raise serializers.ValidationError(f"Use {max_length} characters or fewer.")
    if not text and not allow_blank:
        raise serializers.ValidationError("This field may not be blank.")
    return text


def sanitize_external_text(value, *, max_length):
    """For text from outside (for example a Google profile name): never raises, just removes what is unsafe."""
    return strip_unsafe_chars(value).replace("<", "").replace(">", "")[:max_length].strip()
