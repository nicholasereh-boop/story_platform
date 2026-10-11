from rest_framework.test import APIClient


def test_health_returns_200():
    response = APIClient().get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}


def test_unknown_route_returns_404_in_standard_format():
    response = APIClient().get("/api/v1/does-not-exist/")
    assert response.status_code == 404
    body = response.json()
    assert body["data"] is None
    assert "errors" in body and "message" in body


def test_cors_allows_frontend_and_rejects_unknown_origin(settings):
    client = APIClient()
    allowed = client.get("/api/v1/health/", HTTP_ORIGIN=settings.FRONTEND_URL)
    assert allowed["Access-Control-Allow-Origin"] == settings.FRONTEND_URL
    rejected = client.get("/api/v1/health/", HTTP_ORIGIN="http://evil.example")
    assert "Access-Control-Allow-Origin" not in rejected
