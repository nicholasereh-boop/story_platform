from rest_framework.views import exception_handler


def _first_message(data):
    """Pull a human-readable sentence out of DRF's error structures."""
    if isinstance(data, dict):
        for key in ("detail", "non_field_errors"):
            if key in data:
                return _first_message(data[key])
        return None
    if isinstance(data, (list, tuple)):
        return _first_message(data[0]) if data else None
    return None if data is None else str(data)


def api_exception_handler(exc, context):
    """Same envelope for every error: {"data": null, "errors": ..., "message": "..."}."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    message = _first_message(response.data) or "Please correct the highlighted fields."
    response.data = {"errors": response.data, "message": message}
    return response
