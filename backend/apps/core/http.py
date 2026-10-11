"""Small HTTP helpers."""
from django.utils.cache import patch_cache_control, patch_vary_headers


def mark_per_user(response, request):
    """Responses that may differ per reader must never be shared by a cache.

    `Vary: Cookie` always (anonymous and logged-in readers get different bodies); `Cache-Control: private`
    whenever the body was personalised (liked_by_me, own pending comments).
    """
    patch_vary_headers(response, ["Cookie"])
    if request.user and request.user.is_authenticated:
        patch_cache_control(response, private=True)
    return response
