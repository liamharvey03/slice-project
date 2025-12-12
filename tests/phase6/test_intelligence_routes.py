import pytest
from typing import Optional
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voyager.api.intelligence_routes import router
import voyager.api.intelligence_routes as routes_mod
from voyager.session.models import SessionResponse


class FakeThesisReviewer:
    def __init__(self):
        self.last_args = None

    async def review_thesis(
        self,
        thesis_id: int,
        *,
        include_memory: bool,
        include_risk: bool,
        extra_instructions: Optional[str],
    ) -> SessionResponse:
        self.last_args = {
            "thesis_id": thesis_id,
            "include_memory": include_memory,
            "include_risk": include_risk,
            "extra_instructions": extra_instructions,
        }
        return SessionResponse(
            observation_id=1,
            llm_response="review",
            memory_context=None,
            risk_snapshot=None,
        )


class FakeConsistencyChecker:
    def __init__(self):
        self.last_args = None

    async def analyze(
        self,
        *,
        include_memory: bool,
        include_risk: bool,
        extra_instructions: Optional[str],
    ) -> SessionResponse:
        self.last_args = {
            "include_memory": include_memory,
            "include_risk": include_risk,
            "extra_instructions": extra_instructions,
        }
        return SessionResponse(
            observation_id=2,
            llm_response="consistency",
            memory_context=None,
            risk_snapshot=None,
        )


class FakeIntuitionEngine:
    def __init__(self):
        self.last_args = None

    async def answer(
        self,
        question: str,
        *,
        k: int,
        include_memory: bool,
        include_risk: bool,
        extra_instructions: Optional[str],
    ) -> SessionResponse:
        self.last_args = {
            "question": question,
            "k": k,
            "include_memory": include_memory,
            "include_risk": include_risk,
            "extra_instructions": extra_instructions,
        }
        return SessionResponse(
            observation_id=3,
            llm_response="answer",
            memory_context=None,
            risk_snapshot=None,
        )


class FakeCommentaryEngine:
    def __init__(self):
        self.last_daily_args = None
        self.last_weekly_args = None

    async def generate_daily(
        self,
        *,
        include_memory: bool,
        include_risk: bool,
        extra_instructions: Optional[str],
    ) -> SessionResponse:
        self.last_daily_args = {
            "include_memory": include_memory,
            "include_risk": include_risk,
            "extra_instructions": extra_instructions,
        }
        return SessionResponse(
            observation_id=4,
            llm_response="daily",
            memory_context=None,
            risk_snapshot=None,
        )

    async def generate_weekly(
        self,
        *,
        week_label: Optional[str],
        include_memory: bool,
        include_risk: bool,
        extra_instructions: Optional[str],
    ) -> SessionResponse:
        self.last_weekly_args = {
            "week_label": week_label,
            "include_memory": include_memory,
            "include_risk": include_risk,
            "extra_instructions": extra_instructions,
        }
        return SessionResponse(
            observation_id=5,
            llm_response="weekly",
            memory_context=None,
            risk_snapshot=None,
        )


@pytest.fixture
def app():
    # Construct fakes
    fake_reviewer = FakeThesisReviewer()
    fake_checker = FakeConsistencyChecker()
    fake_intel_engine = FakeIntuitionEngine()
    fake_commentary_engine = FakeCommentaryEngine()

    app = FastAPI()
    app.include_router(router)

    # Override FastAPI dependencies using the original dependency functions
    app.dependency_overrides[routes_mod.get_thesis_reviewer] = lambda: fake_reviewer
    app.dependency_overrides[routes_mod.get_consistency_checker] = lambda: fake_checker
    app.dependency_overrides[routes_mod.get_intuition_engine] = lambda: fake_intel_engine
    app.dependency_overrides[routes_mod.get_commentary_engine] = (
        lambda: fake_commentary_engine
    )

    # Expose fakes for assertions
    app.state.fake_reviewer = fake_reviewer
    app.state.fake_checker = fake_checker
    app.state.fake_intel_engine = fake_intel_engine
    app.state.fake_commentary_engine = fake_commentary_engine

    return app


def test_review_thesis_route(app):
    client = TestClient(app)

    payload = {
        "thesis_id": 42,
        "include_memory": True,
        "include_risk": False,
        "extra_instructions": "Be strict.",
    }
    resp = client.post("/api/v1/intel/thesis/review", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["observation_id"] == 1
    assert data["llm_response"] == "review"

    fr = app.state.fake_reviewer
    assert fr.last_args["thesis_id"] == 42
    assert fr.last_args["include_memory"] is True
    assert fr.last_args["include_risk"] is False
    assert fr.last_args["extra_instructions"] == "Be strict."


def test_consistency_route(app):
    client = TestClient(app)

    payload = {
        "include_memory": False,
        "include_risk": False,
        "extra_instructions": "Focus on timing conflicts.",
    }
    resp = client.post("/api/v1/intel/thesis/consistency", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["observation_id"] == 2
    assert data["llm_response"] == "consistency"

    fc = app.state.fake_checker
    assert fc.last_args["include_memory"] is False
    assert fc.last_args["include_risk"] is False
    assert "timing conflicts" in fc.last_args["extra_instructions"]


def test_intuition_qa_route(app):
    client = TestClient(app)

    payload = {
        "question": "Why did we like this trade?",
        "k": 7,
        "include_memory": False,
        "include_risk": False,
        "extra_instructions": "Explain reasoning clearly.",
    }
    resp = client.post("/api/v1/intel/qa", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["observation_id"] == 3
    assert data["llm_response"] == "answer"

    fe = app.state.fake_intel_engine
    assert fe.last_args["question"] == "Why did we like this trade?"
    assert fe.last_args["k"] == 7
    assert fe.last_args["include_memory"] is False
    assert fe.last_args["include_risk"] is False
    assert "reasoning clearly" in fe.last_args["extra_instructions"]


def test_daily_commentary_route(app):
    client = TestClient(app)

    payload = {
        "include_memory": False,
        "include_risk": True,
        "extra_instructions": "Focus on macro, not tick-level moves.",
    }
    resp = client.post("/api/v1/intel/commentary/daily", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["observation_id"] == 4
    assert data["llm_response"] == "daily"

    fce = app.state.fake_commentary_engine
    args = fce.last_daily_args
    assert args["include_memory"] is False
    assert args["include_risk"] is True
    assert "macro" in args["extra_instructions"]


def test_weekly_commentary_route(app):
    client = TestClient(app)

    payload = {
        "week_label": "2025-11-17 to 2025-11-23",
        "include_memory": False,
        "include_risk": False,
        "extra_instructions": "Highlight regime shifts.",
    }
    resp = client.post("/api/v1/intel/commentary/weekly", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["observation_id"] == 5
    assert data["llm_response"] == "weekly"

    fce = app.state.fake_commentary_engine
    args = fce.last_weekly_args
    assert args["week_label"] == "2025-11-17 to 2025-11-23"
    assert args["include_memory"] is False
    assert args["include_risk"] is False
    assert "Highlight regime shifts." in args["extra_instructions"]