import pytest

from slice.intelligence.thesis_reviewer import ThesisReviewer
from slice.session.models import SessionResponse


class FakeContextBuilder:
    def __init__(self, context, raises: bool = False):
        self.context = context
        self.raises = raises
        self.last_thesis_id = None

    def build_thesis_context(self, thesis_id: int):
        self.last_thesis_id = thesis_id
        return self.context


class FakeOrchestratorClient:
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
        # Return a minimal, valid SessionResponse
        return SessionResponse(
            observation_id=123,
            llm_response="ok",
            memory_context=None,
            risk_snapshot=None,
        )


@pytest.mark.asyncio
async def test_review_thesis_happy_path():
    # Arrange
    context = {
        "thesis": {"thesis_id": 1},
        "observations": [{"observation_id": 10}],
        "risk_snapshot": {"snapshot_label": "test"},
    }
    ctx_builder = FakeContextBuilder(context=context)
    orchestrator = FakeOrchestratorClient()
    reviewer = ThesisReviewer(ctx_builder, orchestrator)

    # Act
    resp = await reviewer.review_thesis(
        thesis_id=1,
        include_memory=True,
        include_risk=False,
    )

    # Assert: response is passed through from orchestrator
    assert resp.observation_id == 123
    assert resp.llm_response == "ok"

    # Assert: context builder call
    assert ctx_builder.last_thesis_id == 1

    # Assert: orchestrator call
    assert orchestrator.last_include_memory is True
    assert orchestrator.last_include_risk is False

    # Basic shape check on the constructed user_text
    ut = orchestrator.last_user_text
    assert "Phase 6 – Thesis Review Request" in ut
    assert '"thesis_id": 1' in ut or '"thesis_id": 1,' in ut
    assert '"observation_id": 10' in ut or '"observation_id": 10,' in ut
    assert "risk_snapshot" in ut
    assert "context:" in ut


@pytest.mark.asyncio
async def test_review_thesis_missing_thesis_raises():
    ctx_builder = FakeContextBuilder(context={"error": "thesis_not_found"})
    orchestrator = FakeOrchestratorClient()
    reviewer = ThesisReviewer(ctx_builder, orchestrator)

    with pytest.raises(ValueError) as excinfo:
        await reviewer.review_thesis(thesis_id=999)

    assert "Thesis 999 not found" in str(excinfo.value)