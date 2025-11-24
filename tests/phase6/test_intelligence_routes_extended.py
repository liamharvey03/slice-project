# tests/phase6/test_intelligence_routes_extended.py

"""
Extra route-level tests for Phase 6 intelligence endpoints.

These don’t rely on a global app. They build a local FastAPI app with the
intelligence router and override dependencies with fakes.
"""

from typing import Any, Dict, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import slice.api.intelligence_routes as routes_mod
from slice.session.models import SessionResponse


# -----------------------------
# Fakes (same interface as in routes)
# -----------------------------


class FakeThesisReviewer:
    def __init__(self) -> None:
        self.last_args: Optional[Dict[str, Any]] = None

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
            observation_id=10,
            llm_response="ext-review",
            memory_context=None,
            risk_snapshot=None,
        )


class FakeConsistencyChecker:
    def __init__(self) -> None:
        self.last_args: Optional[Dict[str, Any]] = None

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
            observation_id=11,
            llm_response="ext-consistency",
            memory_context=None,
            risk_snapshot=None,
        )


class FakeIntuitionEngine:
    def __init__(self) -> None:
        self.last_args: Optional[Dict[str, Any]] = None

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
            observation_id=12,
            llm_response="ext-answer",
            memory_context=None,
            risk_snapshot=None,
        )


class FakeCommentaryEngine:
    def __init__(self) -> None:
        self.last_daily_args: Optional[Dict[str, Any]] = None
        self.last_weekly_args: Optional[Dict[str, Any]] = None

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
            observation_id=13,
            llm_response="ext-daily",
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
            observation_id=14,
            llm_response="ext-weekly",
            memory_context=None,
            risk_snapshot=None,
        )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_mod.router)

    fake_reviewer = FakeThesisReviewer()
    fake_checker = FakeConsistencyChecker()
    fake_intel_engine = FakeIntuitionEngine()
    fake_commentary_engine = FakeCommentaryEngine()

    app.dependency_overrides[routes_mod.get_thesis_reviewer] = lambda: fake_reviewer
    app.dependency_overrides[routes_mod.get_consistency_checker] = lambda: fake_checker
    app.dependency_overrides[routes_mod.get_intuition_engine] = lambda: fake_intel_engine
    app.dependency_overrides[routes_mod.get_commentary_engine] = (
        lambda: fake_commentary_engine
    )

    app.state.fake_reviewer = fake_reviewer
    app.state.fake_checker = fake_checker
    app.state.fake_intel_engine = fake_intel_engine
    app.state.fake_commentary_engine = fake_commentary_engine

    return TestClient(app)


def test_review_thesis_ext_shape(client: TestClient):
    resp = client.post(
        "/api/v1/intel/thesis/review",
        json={
            "thesis_id": 99,
            "include_memory": True,
            "include_risk": True,
            "extra_instructions": "Extra test.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Basic SessionResponse shape
    assert "observation_id" in data
    assert "llm_response" in data


def test_intuition_qa_ext_shape(client: TestClient):
    resp = client.post(
        "/api/v1/intel/qa",
        json={
            "question": "Test question",
            "k": 3,
            "include_memory": False,
            "include_risk": False,
            "extra_instructions": None,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "observation_id" in data
    assert "llm_response" in data


def test_weekly_commentary_ext_shape(client: TestClient):
    resp = client.post(
        "/api/v1/intel/commentary/weekly",
        json={
            "week_label": "test-week",
            "include_memory": False,
            "include_risk": True,
            "extra_instructions": "Highlight big picture.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "observation_id" in data
    assert "llm_response" in data