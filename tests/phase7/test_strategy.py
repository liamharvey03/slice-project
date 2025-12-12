import json
import pytest

from voyager.intelligence.strategy import run_strategy_recommendation


class _FakeThesis:
    def __init__(self, thesis_id: int):
        self.thesis_id = thesis_id

    def dict(self):
        return {"thesis_id": self.thesis_id}


class _FakeRiskSnapshot:
    def dict(self):
        return {"var_95": 0.09}


class _FakeDataAccess:
    def __init__(self):
        self.get_all_theses_called = 0
        self.get_risk_snapshot_called = 0

    def get_all_theses(self):
        self.get_all_theses_called += 1
        return [_FakeThesis(1), _FakeThesis(2)]

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
        return _FakeSessionResponse(
            {
                "context_kind": ctx.get("kind"),
                "n_theses": len(ctx.get("theses", [])),
            }
        )


@pytest.mark.asyncio
async def test_run_strategy_recommendation_embeds_context():
    data_access = _FakeDataAccess()
    orchestrator = _FakeOrchestratorClient()

    result = await run_strategy_recommendation(
        data_access=data_access,
        orchestrator=orchestrator,
        extra_instructions="Lean into carry.",
    )

    assert data_access.get_all_theses_called == 1
    assert data_access.get_risk_snapshot_called == 1

    assert orchestrator.run_analyst_called == 1
    ctx = orchestrator.last_context
    assert ctx["kind"] == "strategy_context"
    assert len(ctx["theses"]) == 2

    assert isinstance(result, _FakeSessionResponse)
    assert result.payload["context_kind"] == "strategy_context"
