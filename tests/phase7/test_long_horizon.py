import json
import pytest

from slice.intelligence.long_horizon import run_long_horizon_analysis


class _FakeThesis:
    def __init__(self, thesis_id: int):
        self.thesis_id = thesis_id

    def dict(self):
        return {"thesis_id": self.thesis_id, "title": f"Thesis {self.thesis_id}"}


class _FakeRiskSnapshot:
    def dict(self):
        return {"volatility": 0.18}


class _FakeDataAccess:
    def __init__(self):
        self.get_thesis_called = 0
        self.get_risk_snapshot_called = 0

    def get_thesis(self, thesis_id: int):
        self.get_thesis_called += 1
        return _FakeThesis(thesis_id)

    def get_risk_snapshot(self):
        self.get_risk_snapshot_called += 1
        return _FakeRiskSnapshot()


class _FakeSessionResponse:
    def __init__(self, payload):
        self.payload = payload


class _FakeOrchestratorClient:
    def __init__(self):
        self.run_analyst_called = 0
        self.last_user_text = None
        self.last_include_memory = None
        self.last_include_risk = None
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
        self.last_include_memory = include_memory
        self.last_include_risk = include_risk

        # Extract JSON context from the user_text
        _, ctx_str = user_text.split("context:", 1)
        ctx = json.loads(ctx_str.strip())
        self.last_context = ctx

        return _FakeSessionResponse(
            {
                "context_kind": ctx.get("kind"),
                "horizon_months": ctx.get("horizon_months"),
            }
        )


@pytest.mark.asyncio
async def test_run_long_horizon_analysis_embeds_context():
    data_access = _FakeDataAccess()
    orchestrator = _FakeOrchestratorClient()

    result = await run_long_horizon_analysis(
        thesis_id=1,
        horizon_months=12,
        data_access=data_access,
        orchestrator=orchestrator,
    )

    assert data_access.get_thesis_called == 1
    assert data_access.get_risk_snapshot_called == 1

    assert orchestrator.run_analyst_called == 1
    assert orchestrator.last_include_memory is True
    assert orchestrator.last_include_risk is True

    ctx = orchestrator.last_context
    assert ctx["kind"] == "long_horizon_context"
    assert ctx.get("horizon_months") == 12

    assert isinstance(result, _FakeSessionResponse)
    assert result.payload["context_kind"] == "long_horizon_context"
