"""Who is this reader? A logged-in user, or an anonymous visitor recognised by their Django session.

Anonymous visitors have no account, so their likes and comments are tied to `request.session.session_key`.
A session is only created when the visitor WRITES something (like / comment), never on a plain page view.
Used by both the reactions and the comments apps so the two behave the same way.
"""


def get_visitor(request, create=False):
    """Return (user, session_key). Exactly one of them is set, or both are None.

    - logged-in reader  -> (user, None)
    - anonymous visitor -> (None, session_key)   (the key is created on demand when `create` is True)
    - anonymous visitor with no session yet and create=False -> (None, None)
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user, None
    session = getattr(request, "session", None)
    if session is None:  # session middleware missing: nothing to tie an anonymous reader to
        return None, None
    key = session.session_key
    if key is None and create:
        session["visitor"] = True  # make sure the session is non-empty so the cookie is really sent
        session.save()
        key = session.session_key
    return None, key


def is_owner(obj, user, session_key):
    """True when this reader (user or session) is the one who created `obj` (a Like or a Comment)."""
    if user is not None:
        return obj.user_id == user.id
    return bool(session_key) and obj.user_id is None and obj.session_key == session_key
