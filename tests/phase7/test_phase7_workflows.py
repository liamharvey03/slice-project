import json
import pytest

from voyager.intelligence.long_horizon import run_long_horizon_analysis
from voyager.intelligence.strategy import run_strategy_recommendation
from voyager.intelligence.portfolio_diagnostics import run_portfolio_diagnostics
from voyager.intelligence.narrative import run_narrative_coherence


class _FakeThesis:
    def __init__(self, thesis_id: int):
        self.thesis_id = thesis_id

    def dict(self):
        return {"thesis_id": self.thesis_id}


class _FakeRiskSnapshot:
    def dict(self):
        return {"volatility": 0.15}


class _SharedDataAccess:
    """
    Shared fake DataAccess that multiple engines can hit.
    Tracks call counts across engines so we can assert that
    each engine uses the expected methods and nothing blows up.
    """

    def __init__(self):
        self._theses = [_FakeThesis(1), _FakeThesis(2)]
        self._risk = _FakeRiskSnapshot()

        self.calls = {
            "get_thesis": 0,
            "get_all_theses": 0,
            "get_observations_for_thesis": 0,
            "get_recent_observations": 0,
            "get_risk_snapshot": 0,
        }

    def get_thesis(self, thesis_id: int):
        self.calls["get_thesis"] += 1
        return self._theses[0]

    def get_all_theses(self):
        self.calls["get_all_theses"] += 1
        return self._theses

    def get_observations_for_thesis(self, thesis_id: int):
        self.calls["get_observations_for_thesis"] += 1
        return []

    def get_recent_observations(self, limit: int = 10):
        self.calls["get_recent_observations"] += 1
        return []

    def get_risk_snapshot(self):
        self.calls["get_risk_snapshot"] += 1
        return self._risk


class _FakeSessionResponse:
    def __init__(self, tag: str, payload: dict):
        self.tag = tag
        self.payload = payload


class _RecordingOrchestrator:
    """
    Orchestrator fake that records calls from multiple engines.
    Parses context JSON out of user_text.
    """

    def __init__(self):
        self.calls = []

    async def run_analyst(
        self,
        user_text: str,
        *,
        include_memory: bool = True,
        include_risk: bool = True,
    ):
        # Extract context and its kind
        _, ctx_str = user_text.split("context:", 1)
        ctx = json.loads(ctx_str.strip())
        tag = ctx.get("kind", "unknown")
        record = {
            "tag": tag,
            "user_text": user_text,
            "context": ctx,
            "include_memory": include_memory,
            "include_risk": include_risk,
        }
        self.calls.append(record)
        return _FakeSessionResponse(tag=tag, payload=record)


@pytest.mark.asyncio
async def test_long_horizon_then_strategy_workflow():
    data_access = _SharedDataAccess()
    orchestrator = _RecordingOrchestrator()

    lh_resp = await run_long_horizon_analysis(
        thesis_id=1,
        horizon_months=12,
        data_access=data_access,
        orchestrator=orchestrator,
    )

    strat_resp = await run_strategy_recommendation(
        data_access=data_access,
        orchestrator=orchestrator,
        extra_instructions="Lean into carry trades.",
    )

    assert len(orchestrator.calls) == 2
    assert orchestrator.calls[0]["tag"] == "long_horizon_context"
    assert orchestrator.calls[1]["tag"] == "strategy_context"

    assert data_access.calls["get_thesis"] >= 1
    assert data_access.calls["get_all_theses"] >= 1
    assert data_access.calls["get_risk_snapshot"] >= 1

    assert isinstance(lh_resp, _FakeSessionResponse)
    assert isinstance(strat_resp, _FakeSessionResponse)


@pytest.mark.asyncio
async def test_diagnostics_then_narrative_workflow():
    data_access = _SharedDataAccess()
    orchestrator = _RecordingOrchestrator()

    diag_resp = await run_portfolio_diagnostics(
        data_access=data_access,
        orchestrator=orchestrator,
        extra_instructions="Flag drawdown risks.",
    )

    narr_resp = await run_narrative_coherence(
        data_access=data_access,
        orchestrator=orchestrator,
        window_label="weekly-2025-11-24",
        extra_instructions="Connect risk to positioning.",
    )

    assert len(orchestrator.calls) == 2
    assert orchestrator.calls[0]["tag"] == "portfolio_diagnostics_context"
    assert orchestrator.calls[1]["tag"] == "narrative_coherence_context"

    assert data_access.calls["get_risk_snapshot"] >= 2

    assert isinstance(diag_resp, _FakeSessionResponse)
    assert isinstance(narr_resp, _FakeSessionResponse)
