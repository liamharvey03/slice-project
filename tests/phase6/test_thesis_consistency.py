import pytest

from voyager.intelligence.thesis_consistency import ThesisConsistencyChecker
from voyager.session.models import SessionResponse


class FakeContextBuilder:
    def __init__(self, output):
        self.output = output
        self.called = False

    def build_multi_thesis_context(self):
        self.called = True
        return self.output


class FakeOrchestrator:
    def __init__(self):
        self.last_user_text = None
        self.last_include_memory = None
        self.last_include_risk = None

    async def run_analyst(
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
            observation_id=77,
            llm_response="ok",
            memory_context=None,
            risk_snapshot=None,
        )


@pytest.mark.asyncio
async def test_consistency_checker_basic_flow():
    # Arrange
    ctx = {"theses": [{"thesis_id": 1}, {"thesis_id": 2}]}
    ctx_builder = FakeContextBuilder(output=ctx)
    orchestrator = FakeOrchestrator()
    checker = ThesisConsistencyChecker(ctx_builder, orchestrator)

    # Act
    resp = await checker.analyze(include_memory=False, include_risk=False)

    # Assert response passthrough
    assert resp.observation_id == 77
    assert resp.llm_response == "ok"

    # Assert context builder was invoked
    assert ctx_builder.called is True

    # Inspect orchestrator call
    assert orchestrator.last_include_memory is False
    assert orchestrator.last_include_risk is False

    ut = orchestrator.last_user_text
    assert "Cross-Thesis Consistency Review" in ut
    assert '"thesis_id": 1' in ut or '"thesis_id": 1,' in ut
    assert '"thesis_id": 2' in ut or '"thesis_id": 2,' in ut
    assert "context:" in ut


@pytest.mark.asyncio
async def test_consistency_checker_allows_extra_instructions():
    ctx = {"theses": [{"thesis_id": 3}]}
    ctx_builder = FakeContextBuilder(output=ctx)
    orchestrator = FakeOrchestrator()
    checker = ThesisConsistencyChecker(ctx_builder, orchestrator)

    await checker.analyze(extra_instructions="Focus on timing conflicts.")

    ut = orchestrator.last_user_text
    assert "Additional user instructions:" in ut
    assert "timing conflicts" in ut