def display_name(user):
    """A user's public name, with no extra query when `profile` was select_related."""
    if user is None:
        return None
    profile = getattr(user, "profile", None)  # missing profile raises an AttributeError subclass -> None
    return profile.display_name if profile and profile.display_name else user.email.split("@")[0]
