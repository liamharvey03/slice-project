import json
import pytest

from slice.intelligence.portfolio_diagnostics import run_portfolio_diagnostics


class _FakeRiskSnapshot:
    def dict(self):
        return {"volatility": 0.18, "max_drawdown": 0.22}


class _FakeDataAccess:
    def __init__(self, with_risk: bool = True):
        self._with_risk = with_risk
        self.get_risk_snapshot_called = 0

    def get_risk_snapshot(self):
        self.get_risk_snapshot_called += 1
        if not self._with_risk:
            return None
        return _FakeRiskSnapshot()


class _FakeSessionResponse:
    def __init__(self, payload):
        self.payload = payload


class _FakeOrchestratorClient:
    def __init__(self):
        self.run_analyst_called = 0
        self.last_user_text = None
        self.last_context = None

    async def run_analyst(
        self,
        user_text: str,
        *,
        include_memory: bool = True,
        include_risk: bool = True,
    ):
        self.run_analyst_called += 1
        self.last_user_text = user_text
        _, ctx_str = user_text.split("context:", 1)
        ctx = json.loads(ctx_str.strip())
        self.last_context = ctx
        has_risk = bool(ctx.get("risk_profile"))
        return _FakeSessionResponse(
            {
                "context_kind": ctx.get("kind"),
                "has_risk_profile": has_risk,
            }
        )


@pytest.mark.asyncio
async def test_run_portfolio_diagnostics_with_risk():
    data_access = _FakeDataAccess(with_risk=True)
    orchestrator = _FakeOrchestratorClient()

    result = await run_portfolio_diagnostics(
        data_access=data_access,
        orchestrator=orchestrator,
        extra_instructions="Highlight major concentrations.",
    )

    assert data_access.get_risk_snapshot_called == 1
    assert orchestrator.run_analyst_called == 1

    ctx = orchestrator.last_context
    assert ctx["kind"] == "portfolio_diagnostics_context"
    assert ctx["risk_profile"] is not None

    assert isinstance(result, _FakeSessionResponse)
    assert result.payload["context_kind"] == "portfolio_diagnostics_context"
    assert result.payload["has_risk_profile"] is True


@pytest.mark.asyncio
async def test_run_portfolio_diagnostics_without_risk():
    data_access = _FakeDataAccess(with_risk=False)
    orchestrator = _FakeOrchestratorClient()

    result = await run_portfolio_diagnostics(
        data_access=data_access,
        orchestrator=orchestrator,
        extra_instructions=None,
    )

    assert data_access.get_risk_snapshot_called == 1
    assert orchestrator.run_analyst_called == 1

    ctx = orchestrator.last_context
    assert ctx["kind"] == "portfolio_diagnostics_context"
    # we expect an empty or None risk_profile when no snapshot is present
    assert ctx["risk_profile"] in (None, {}, [])

    assert isinstance(result, _FakeSessionResponse)
    assert result.payload["has_risk_profile"] is False
