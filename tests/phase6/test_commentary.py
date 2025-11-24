import pytest

from slice.intelligence.commentary import CommentaryEngine
from slice.session.models import SessionResponse


class FakeContextBuilder:
    def __init__(self):
        self.daily_called = 0
        self.to_return = {
            "recent_observations": [
                {"observation_id": 1, "text": "obs A"},
                {"observation_id": 2, "text": "obs B"},
            ],
            "risk_snapshot": {"snapshot_label": "test"},
        }

    def build_daily_context(self):
        self.daily_called += 1
        return self.to_return


class FakeOrchestrator:
    def __init__(self):
        self.last_user_text = None
        self.last_include_memory = None
        self.last_include_risk = None

    async def run_concise(
        self,
        user_text: str,
        *,
        include_memory: bool = True,
        include_risk: bool = True,
    ) -> SessionResponse:
        self.last_user_text = user_text
        self.last_include_memory = include_memory
        self.last_include_risk = include_risk

        return SessionResponse(
            observation_id=42,
            llm_response="commentary",
            memory_context=None,
            risk_snapshot=None,
        )


@pytest.mark.asyncio
async def test_generate_daily_basic_flow():
    ctx_builder = FakeContextBuilder()
    orch = FakeOrchestrator()
    engine = CommentaryEngine(context_builder=ctx_builder, orchestrator=orch)

    resp = await engine.generate_daily(
        include_memory=False,
        include_risk=True,
    )

    # Response passthrough
    assert resp.observation_id == 42
    assert resp.llm_response == "commentary"

    # Context builder was invoked
    assert ctx_builder.daily_called == 1

    # Orchestrator flags
    assert orch.last_include_memory is False
    assert orch.last_include_risk is True

    ut = orch.last_user_text
    assert "Phase 6 – Daily Commentary" in ut
    assert "context:" in ut
    # serialized context should contain observations and risk
    assert "obs A" in ut
    assert "obs B" in ut
    assert "snapshot_label" in ut


@pytest.mark.asyncio
async def test_generate_daily_extra_instructions():
    ctx_builder = FakeContextBuilder()
    orch = FakeOrchestrator()
    engine = CommentaryEngine(context_builder=ctx_builder, orchestrator=orch)

    await engine.generate_daily(
        extra_instructions="Focus on macro themes over single names.",
    )

    ut = orch.last_user_text
    assert "Additional instructions from the user:" in ut
    assert "macro themes over single names" in ut


@pytest.mark.asyncio
async def test_generate_weekly_includes_week_label():
    ctx_builder = FakeContextBuilder()
    orch = FakeOrchestrator()
    engine = CommentaryEngine(context_builder=ctx_builder, orchestrator=orch)

    resp = await engine.generate_weekly(
        week_label="2025-11-17 to 2025-11-23",
        include_memory=False,
        include_risk=False,
    )

    assert resp.observation_id == 42
    assert resp.llm_response == "commentary"

    ut = orch.last_user_text
    assert "Phase 6 – Weekly Commentary" in ut
    assert "Week label: 2025-11-17 to 2025-11-23" in ut
    assert "context:" in ut
    # context should still be serialized
    assert "obs A" in ut
    assert "snapshot_label" in ut
    assert orch.last_include_memory is False
    assert orch.last_include_risk is False