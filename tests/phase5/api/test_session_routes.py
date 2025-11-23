from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.slice.api.session_routes import router
from src.slice.session.models import SessionResponse


def make_app():
    app = FastAPI()
    app.include_router(router)
    return app


def test_session_step_basic(monkeypatch):
    # Patch SessionOrchestrator.run_session → return predictable SessionResponse
    async def fake_run(self, text, options):
        return SessionResponse(
            observation_id=123,
            llm_response="ok",
            memory_context={"items": []},
            risk_snapshot=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=None,
        )

    # Patch method on the class (must patch the class, not instance)
    monkeypatch.setattr(
        "src.slice.api.session_routes.SessionOrchestrator.run_session",
        fake_run,
    )

    client = TestClient(make_app())

    payload = {
        "text": "hello",
        "options": {
            "mode": "STANDARD",
            "use_memory": True,
            "use_risk": False,
            "max_memory_items": 5,
            "risk_for_thesis_id": None,
            "risk_for_portfolio_id": None,
        },
    }

    resp = client.post("/api/v1/session/step", json=payload)

    assert resp.status_code == 200

    body = resp.json()
    assert body["observation_id"] == 123
    assert body["llm_response"] == "ok"
    assert body["memory_context"] == {"items": []}
    assert body["risk_snapshot"] is None