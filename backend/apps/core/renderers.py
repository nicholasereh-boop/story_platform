from rest_framework.renderers import JSONRenderer


class EnvelopeRenderer(JSONRenderer):
    """Wraps every API response as {"data", "pagination", "errors", "message"}."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        status_code = getattr(response, "status_code", 200)
        if status_code == 204:
            return b""
        if status_code >= 400:
            if not (isinstance(data, dict) and "errors" in data):
                data = {"errors": data, "message": None}
            payload = {"data": None, **data}
        elif isinstance(data, dict) and set(data) == {"results", "pagination"}:
            payload = {"data": data["results"], "pagination": data["pagination"]}
        else:
            payload = {"data": data}
        return super().render(payload, accepted_media_type, renderer_context)
