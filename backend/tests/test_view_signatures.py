"""Guard: every routed API handler must accept the URL's `version` argument.

The API is versioned in the path (`/api/v1/...`, see config/urls.py), so Django passes `version="v1"` to every handler. A
handler written as `def post(self, request, slug)` therefore crashes with a 500 (`got an unexpected keyword argument
'version'`) on every request. This test walks the real URL table and fails for any handler that cannot take it.
"""
import inspect

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

HANDLERS = ("get", "post", "put", "patch", "delete")


def routed_view_classes():
    seen = {}

    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                cls = getattr(p.callback, "cls", None) or getattr(p.callback, "view_class", None)
                route = prefix + str(p.pattern)
                # Only the versioned API: third-party views (allauth under /accounts/) are not routed with a version.
                if cls is not None and hasattr(cls, "http_method_names") and "(?P<version>" in route:
                    seen.setdefault(cls, route)

    walk(get_resolver().url_patterns)
    return seen


def accepts_version(func):
    params = inspect.signature(func).parameters.values()
    return any(p.kind is p.VAR_KEYWORD or p.name == "version" for p in params)


def test_every_routed_handler_accepts_the_version_argument():
    problems = []
    for cls, route in routed_view_classes().items():
        for name in HANDLERS:
            handler = getattr(cls, name, None)
            if handler is not None and not accepts_version(handler):
                problems.append(f"{cls.__module__}.{cls.__name__}.{name}  (route {route})")
    assert not problems, "These handlers crash with a 500 under /api/v1/ (add **kwargs):\n  " + "\n  ".join(sorted(problems))


def test_the_guard_really_sees_the_engagement_views():
    names = {cls.__name__ for cls in routed_view_classes()}
    assert {"StoryLikeView", "StoryCommentsView", "CommentDetailView", "AdminCommentDetailView"} <= names
