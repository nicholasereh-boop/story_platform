"""Log redaction.

Nothing secret should reach the logs in the first place; this filter is the safety net. It rewrites every log
record (message AND traceback text) before any handler formats it:
  - values of password / token / secret / key / session / cookie style fields ("password=abc", '"token": "abc"')
  - Authorization and Cookie headers, and "Bearer ..." tokens
  - every e-mail address (also when URL-encoded as %40), because addresses show up in query strings and bodies
Wire it to a handler with {"filters": ["redact"]} (see LOGGING in config/settings/base.py).
"""
import logging
import re

REDACTED = "[REDACTED]"

_SENSITIVE_NAMES = (
    r"password\w*|passwd|pwd|new_password|current_password|token|access_token|refresh_token|secret\w*|api[_-]?key|"
    r"sessionid|csrftoken|csrfmiddlewaretoken|authorization|http_authorization|cookie|http_cookie|set-cookie|"
    r"recovery_code|code|key|signature"
)
# name=value, name: value, "name": "value", 'name': 'value'  (value runs to a delimiter)
_PAIR = re.compile(
    r"""(?ix)
    (?P<name>["']?\b(?:%s)\b["']?)
    (?P<sep>\s*[:=]\s*)
    (?!\[REDACTED\])
    (?P<value>"[^"]*"|'[^']*'|[^\s&,;}\]\)]+)
    """ % _SENSITIVE_NAMES
)
_HEADER_LINE = re.compile(r"(?im)\b(authorization|cookie|set-cookie|x-csrftoken)\b\s*:\s*[^\r\n]*")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+(?:@|%40)[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


def redact(text):
    """Return `text` with secrets and e-mail addresses replaced. Safe to call on any string."""
    if not text:
        return text
    text = _HEADER_LINE.sub(lambda m: f"{m.group(1)}: {REDACTED}", text)
    text = _BEARER.sub(f"Bearer {REDACTED}", text)

    def pair(match):
        value = match.group("value")
        quote = value[0] if value[:1] in ("'", '"') else ""
        return f"{match.group('name')}{match.group('sep')}{quote}{REDACTED}{quote}"

    text = _PAIR.sub(pair, text)
    return _EMAIL.sub("[email]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # a broken format string must not hide the record
            message = str(record.msg)
        record.msg = redact(message)
        record.args = None
        # Pre-render the traceback so it can be redacted too (the formatter reuses record.exc_text).
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return True
