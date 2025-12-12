import pytest

from voyager.intelligence.intuition_qa import IntuitionQAEngine
from voyager.session.models import SessionResponse


class FakeMemoryService:
    def __init__(self):
        self.last_question = None
        self.last_k = None
        self.to_return = [
            {"observation_id": 1, "text": "obs A"},
            {"observation_id": 2, "text": "obs B"},
        ]

    def recall(self, question: str, k: int):
        self.last_question = question
        self.last_k = k
        return self.to_return


class FakeContextBuilder:
    def __init__(self):
        self.last_question = None
        self.last_recalled = None

    def build_intuition_context(self, question: str, recalled_obs: list[dict]):
        self.last_question = question
        self.last_recalled = recalled_obs
        return {
            "question": question,
            "recalled": recalled_obs,
            "dummy": True,
        }


class FakeOrchestrator:
    def __init__(self):
        self.last_user_text = None
        self.last_include_memory = None
        self.last_include_risk = None

    async def run_standard(
        self,
        user_text: str,
        *,
        include_memory: bool = True,
        include_risk: bool = False,
    ) -> SessionResponse:
        self.last_user_text = user_text
        self.last_include_memory = include_memory
        self.last_include_risk = include_risk

        return SessionResponse(
            observation_id=999,
            llm_response="answer",
            memory_context=None,
            risk_snapshot=None,
        )


@pytest.mark.asyncio
async def test_intuition_qa_basic_flow():
    mem = FakeMemoryService()
    ctx = FakeContextBuilder()
    orch = FakeOrchestrator()
    engine = IntuitionQAEngine(memory_service=mem, context_builder=ctx, orchestrator=orch)

    resp = await engine.answer(
        "why did we like this trade?",
        k=7,
        include_memory=False,
        include_risk=False,
    )

    # Response passthrough
    assert resp.observation_id == 999
    assert resp.llm_response == "answer"

    # Memory recall call
    assert mem.last_question == "why did we like this trade?"
    assert mem.last_k == 7

    # Context builder usage
    assert ctx.last_question == "why did we like this trade?"
    assert ctx.last_recalled == mem.to_return

    # Orchestrator usage
    assert orch.last_include_memory is False
    assert orch.last_include_risk is False

    ut = orch.last_user_text
    assert "Phase 6 – Intuition Q&A" in ut
    assert "context:" in ut
    # Sanity check that recalled obs content appears in serialized JSON
    assert "obs A" in ut
    assert "obs B" in ut


@pytest.mark.asyncio
async def test_intuition_qa_extra_instructions_included():
    mem = FakeMemoryService()
    ctx = FakeContextBuilder()
    orch = FakeOrchestrator()
    engine = IntuitionQAEngine(memory_service=mem, context_builder=ctx, orchestrator=orch)

    await engine.answer(
        "test question",
        extra_instructions="Focus on risk management aspects.",
    )

    ut = orch.last_user_text
    assert "Additional instructions from the user:" in ut
    assert "risk management aspects" in ut