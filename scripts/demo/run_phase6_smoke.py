# scripts/run_phase6_smoke.py

"""
Phase 6 smoke test: exercise all intelligence routes end-to-end for shape,
without relying on a global app or real LLM/DB.

It:
  - Builds a local FastAPI app
  - Includes the intelligence router
  - Overrides its dependencies with fakes
  - Calls each endpoint and prints the JSON payloads
"""

from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

import voyager.api.intelligence_routes as routes_mod
from voyager.session.models import SessionResponse


# -----------------------------
# Fake engines (same shape as tests)
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
            observation_id=1,
            llm_response="fake-review",
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
            observation_id=2,
            llm_response="fake-consistency",
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
            observation_id=3,
            llm_response="fake-answer",
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
            observation_id=4,
            llm_response="fake-daily",
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
            llm_response="fake-weekly",
            memory_context=None,
            risk_snapshot=None,
        )


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(routes_mod.router)

    fake_reviewer = FakeThesisReviewer()
    fake_checker = FakeConsistencyChecker()
    fake_intel_engine = FakeIntuitionEngine()
    fake_commentary_engine = FakeCommentaryEngine()

    # Override dependencies as FastAPI expects them (functions from routes_mod)
    app.dependency_overrides[routes_mod.get_thesis_reviewer] = lambda: fake_reviewer
    app.dependency_overrides[routes_mod.get_consistency_checker] = lambda: fake_checker
    app.dependency_overrides[routes_mod.get_intuition_engine] = lambda: fake_intel_engine
    app.dependency_overrides[routes_mod.get_commentary_engine] = lambda: fake_commentary_engine

    # Make fakes available if you want to inspect them interactively
    app.state.fake_reviewer = fake_reviewer
    app.state.fake_checker = fake_checker
    app.state.fake_intel_engine = fake_intel_engine
    app.state.fake_commentary_engine = fake_commentary_engine

    return app


def main() -> None:
    app = build_app()
    client = TestClient(app)

    print("=== /api/v1/intel/thesis/review ===")
    r = client.post(
        "/api/v1/intel/thesis/review",
        json={
            "thesis_id": 42,
            "include_memory": True,
            "include_risk": False,
            "extra_instructions": "Be strict.",
        },
    )
    print(r.status_code, r.json())

    print("\n=== /api/v1/intel/thesis/consistency ===")
    r = client.post(
        "/api/v1/intel/thesis/consistency",
        json={
            "include_memory": False,
            "include_risk": False,
            "extra_instructions": "Focus on timing conflicts.",
        },
    )
    print(r.status_code, r.json())

    print("\n=== /api/v1/intel/qa ===")
    r = client.post(
        "/api/v1/intel/qa",
        json={
            "question": "Why did we like this trade?",
            "k": 7,
            "include_memory": False,
            "include_risk": False,
            "extra_instructions": "Explain reasoning clearly.",
        },
    )
    print(r.status_code, r.json())

    print("\n=== /api/v1/intel/commentary/daily ===")
    r = client.post(
        "/api/v1/intel/commentary/daily",
        json={
            "include_memory": False,
            "include_risk": True,
            "extra_instructions": "Focus on macro, not tick-level moves.",
        },
    )
    print(r.status_code, r.json())

    print("\n=== /api/v1/intel/commentary/weekly ===")
    r = client.post(
        "/api/v1/intel/commentary/weekly",
        json={
            "week_label": "2025-11-17 to 2025-11-23",
            "include_memory": False,
            "include_risk": False,
            "extra_instructions": "Highlight regime shifts.",
        },
    )
    print(r.status_code, r.json())

    print("\n✅ Phase 6 smoke completed.")


if __name__ == "__main__":
    main()