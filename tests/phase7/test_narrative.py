import json
import pytest

from slice.intelligence.narrative import run_narrative_coherence


class _FakeThesis:
    def __init__(self, thesis_id: int):
        self.thesis_id = thesis_id

    def dict(self):
        return {"thesis_id": self.thesis_id, "title": f"Thesis {self.thesis_id}"}


class _FakeRiskSnapshot:
    def dict(self):
        return {"volatility": 0.2}


class _FakeDataAccess:
    def __init__(self, n_theses: int = 2, with_risk: bool = True):
        self._theses = [_FakeThesis(i + 1) for i in range(n_theses)]
        self._with_risk = with_risk

        self.get_all_theses_called = 0
        self.get_risk_snapshot_called = 0

    def get_all_theses(self):
        self.get_all_theses_called += 1
        return self._theses

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
        return _FakeSessionResponse(
            {
                "context_kind": ctx.get("kind"),
                "n_theses": len(ctx.get("theses", [])),
                "has_risk": bool(
                    ctx.get("macro_view", {}).get("risk_snapshot")
                ),
            }
        )


@pytest.mark.asyncio
async def test_run_narrative_coherence_happy_path():
    data_access = _FakeDataAccess(n_theses=3, with_risk=True)
    orchestrator = _FakeOrchestratorClient()

    result = await run_narrative_coherence(
        data_access=data_access,
        orchestrator=orchestrator,
        window_label="weekly-2025-11-24",
        extra_instructions="Emphasize regime shifts.",
    )

    assert data_access.get_all_theses_called == 1
    assert data_access.get_risk_snapshot_called == 1

    assert orchestrator.run_analyst_called == 1
    ctx = orchestrator.last_context
    assert ctx["kind"] == "narrative_coherence_context"
    assert len(ctx["theses"]) == 3
    assert ctx["macro_view"]["risk_snapshot"] is not None

    assert isinstance(result, _FakeSessionResponse)
    assert result.payload["context_kind"] == "narrative_coherence_context"
    assert result.payload["n_theses"] == 3
    assert result.payload["has_risk"] is True
