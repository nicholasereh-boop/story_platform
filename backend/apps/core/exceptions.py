import logging
import secrets

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

SERVER_ERROR_MESSAGE = "Something went wrong on our side. Please try again later."


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


def new_error_id():
    """Short reference that is shown to the user and written next to the stack trace in the server log."""
    return secrets.token_hex(4)


def server_error_response(exc, request=None):
    """The production answer to an unexpected exception: the standard envelope, a generic message and an error id.
    The traceback goes to the log (redacted), never to the client."""
    error_id = new_error_id()
    method = getattr(request, "method", "?")
    path = getattr(request, "path", "?")
    logger.error("Unhandled error %s on %s %s", error_id, method, path, exc_info=exc)
    message = f"{SERVER_ERROR_MESSAGE} (reference {error_id})"
    return Response({"errors": {"detail": message, "error_id": error_id}, "message": message}, status=500)


def api_exception_handler(exc, context):
    """Same envelope for every error: {"data": null, "errors": ..., "message": "..."}.

    Unexpected exceptions (bugs) become a generic 500 envelope with an error id when DEBUG is off. With DEBUG on, Django's
    own debug page is kept for developers.
    """
    response = exception_handler(exc, context)
    if response is None:
        if settings.DEBUG:
            return None
        return server_error_response(exc, context.get("request"))
    message = _first_message(response.data) or "Please correct the highlighted fields."
    response.data = {"errors": response.data, "message": message}
    return response
