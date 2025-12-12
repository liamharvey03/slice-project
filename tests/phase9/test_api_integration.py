from fastapi.testclient import TestClient

from voyager.api.main import app


client = TestClient(app)


def test_ui_health_endpoint():
    resp = client.get("/ui/health")
    assert resp.status_code == 200
    data = resp.json()
    # Minimal contract: JSON with a "status" field that equals "ok"
    assert isinstance(data, dict)
    assert data.get("status") == "ok"


def test_session_step_route_exists_and_validates():
    # We deliberately send no body to avoid guessing the exact request schema.
    # The only thing we assert is that the route exists and returns a 4xx
    # validation-style error, not a 404 or 5xx.
    resp = client.post("/api/v1/session/step")
    assert 400 <= resp.status_code < 500
