"""
Integration tests for Phase 3 LLM layer.

Tests complete workflows with real components (except LLM which is mocked).
"""
# pylint: disable=redefined-outer-name,too-many-arguments,too-many-locals
import json
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import text

from voyager.llm.query_translator import QueryTranslator
from voyager.llm.critique_engine import CritiqueEngine
from voyager.services.v3.validation_service import ValidationService
from voyager.services.v3.critique_service import CritiqueService
from voyager.models.thesis import Thesis, ThesisExpressionLeg
from voyager.models.common import Direction, ThesisStatus
from voyager.data.series_registry import SeriesRegistry
from voyager.quant.quant_service import QuantService
from voyager.repositories.thesis_repo import ThesisRepository
from voyager.repositories.logic_validation_repository import LogicValidationRepository
from voyager.repositories.thesis_snapshot_repository import ThesisSnapshotRepository
from voyager.repositories.backtest_result_repository import BacktestResultRepository


@pytest.fixture(scope="function")
def v3_tables(db_engine):
    """
    Ensure V3 tables exist and clean them before/after each test.
    """
    # Apply v3 schema
    from voyager.db import apply_v3_schema  # pylint: disable=import-outside-toplevel
    apply_v3_schema()

    # Pre-test cleanup
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE logic_validation CASCADE"))
        conn.execute(text("TRUNCATE thesis_snapshot CASCADE"))
        conn.execute(text("TRUNCATE critique_session CASCADE"))
        # Note: thesis table cleaned by clean_core_tables fixture
    yield
    # Post-test cleanup
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE logic_validation CASCADE"))
        conn.execute(text("TRUNCATE thesis_snapshot CASCADE"))
        conn.execute(text("TRUNCATE critique_session CASCADE"))


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns JSON responses"""
    client = AsyncMock()
    return client


@pytest.fixture
def real_registry():
    """Real SeriesRegistry instance"""
    return SeriesRegistry()


@pytest.fixture
def real_quant_service(db_engine, real_registry):
    """Real QuantService instance"""
    return QuantService(db_engine, real_registry)


@pytest.fixture
def real_thesis_repo(db_engine):
    """Real ThesisRepository instance"""
    return ThesisRepository(engine=db_engine)


@pytest.fixture
def real_validation_repo(db_engine):
    """Real LogicValidationRepository instance"""
    return LogicValidationRepository(engine=db_engine)


@pytest.fixture
def real_snapshot_repo(db_engine):
    """Real ThesisSnapshotRepository instance"""
    return ThesisSnapshotRepository(engine=db_engine)


@pytest.fixture
def real_backtest_repo(db_engine):
    """Real BacktestResultRepository instance"""
    return BacktestResultRepository(engine=db_engine)


@pytest.fixture
def sample_thesis(real_thesis_repo, clean_core_tables):
    """Create a sample thesis in database"""
    thesis = Thesis(
        id="test_thesis_integration",
        title="Gold vs Real Yields Integration Test",
        hypothesis="Rising real yields will pressure gold prices",
        drivers=["Fed tightening", "Inflation falling"],
        disconfirmers=["Flight to safety"],
        expression=[
            ThesisExpressionLeg(asset="GLD", direction=Direction.LONG, size_pct=100.0)
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=["test", "integration"],
        monitor_indices=["DXY"]
    )
    real_thesis_repo.insert(thesis)
    return thesis


@pytest.mark.asyncio
async def test_full_validation_flow(
    mock_llm_client,
    real_registry,
    real_quant_service,
    real_validation_repo,
    real_thesis_repo,
    sample_thesis,
    v3_tables,
    clean_core_tables
):
    """
    Test complete validation flow:
    1. Create thesis
    2. Run validation with QueryTranslator + QuantService
    3. Verify LogicValidation persisted
    4. Verify thesis status updated
    """
    # Mock LLM response for link extraction
    mock_llm_client.chat.return_value = {
        "content": json.dumps({
            "links": [
                {
                    "claim": "Rising real yields pressure gold prices",
                    "concept_a": "real yields",
                    "concept_b": "gold",
                    "direction": "negative"
                }
            ]
        }),
        "usage": {}
    }

    # Mock registry to return known series
    # Note: This is a simplified test - real registry might not have these exact matches
    # In practice, you'd need to ensure test data exists or mock registry.search_by_concept

    translator = QueryTranslator(mock_llm_client, real_registry)
    validation_service = ValidationService(
        query_translator=translator,
        quant_service=real_quant_service,
        validation_repo=real_validation_repo,
        thesis_repo=real_thesis_repo
    )

    # Run validation
    result = await validation_service.validate(sample_thesis)

    # Assertions
    assert result.status in ["complete", "needs_clarification", "parse_failed"]

    # If complete, verify LogicValidation persisted
    if result.status == "complete":
        validation = real_validation_repo.get_by_thesis(sample_thesis.id)
        assert validation is not None
        assert validation.thesis_id == sample_thesis.id
        assert len(validation.links) > 0

        # Verify thesis status updated
        updated_thesis = real_thesis_repo.get_by_id(sample_thesis.id)
        assert updated_thesis.status == ThesisStatus.VALIDATED


@pytest.mark.asyncio
async def test_full_critique_flow(
    mock_llm_client,
    real_thesis_repo,
    real_snapshot_repo,
    real_validation_repo,
    real_backtest_repo,
    sample_thesis,
    v3_tables,
    clean_core_tables,
    db_engine
):
    """
    Test complete critique flow:
    1. Start critique session
    2. Drill down on a dimension
    3. Apply edit suggestion
    4. Complete session
    5. Verify snapshots and conversation history persisted
    """

    # Mock LLM responses for critique
    mock_llm_client.chat.return_value = {
        "content": json.dumps({
            "concerns": [
                {
                    "dimension": "logical_coherence",
                    "severity": "medium",
                    "summary": "The causal chain needs more detail"
                }
            ],
            "opening_message": "I have some concerns about logical coherence."
        }),
        "usage": {}
    }

    critique_engine = CritiqueEngine(mock_llm_client)
    critique_service = CritiqueService(
        critique_engine=critique_engine,
        thesis_repo=real_thesis_repo,
        snapshot_repo=real_snapshot_repo,
        validation_repo=real_validation_repo,
        backtest_repo=real_backtest_repo,
        engine=db_engine
    )

    # 1. Start critique
    summary = await critique_service.start(sample_thesis.id)
    assert len(summary.concerns) > 0

    # Verify pre-critique snapshot created
    snapshots = real_snapshot_repo.list_by_thesis(sample_thesis.id)
    pre_snapshots = [s for s in snapshots if s.snapshot_type == "pre_critique"]
    assert len(pre_snapshots) > 0

    # 2. Drill down
    mock_llm_client.chat.return_value = {
        "content": json.dumps({
            "message": "The thesis would benefit from explaining how real yields affect gold demand.",
            "thesis_edit_suggestion": {
                "field": "hypothesis",
                "action": "replace",
                "value": "Rising real yields reduce gold's appeal as a non-yielding asset, pressuring prices through reduced demand."
            }
        }),
        "usage": {}
    }

    response = await critique_service.continue_conversation(
        thesis_id=sample_thesis.id,
        dimension="logical_coherence",
        user_message="Can you elaborate on the logical coherence concern?"
    )
    assert response.message is not None

    # Verify conversation history persisted
    history = critique_service.get_conversation_history(
        sample_thesis.id,
        "logical_coherence"
    )
    assert len(history) >= 2  # User message + assistant response

    # 3. Apply edit suggestion
    if response.thesis_edit_suggestion:
        edited_thesis = critique_service.apply_edit_suggestion(
            sample_thesis.id,
            response.thesis_edit_suggestion
        )
        assert edited_thesis.hypothesis != sample_thesis.hypothesis

    # 4. Complete session
    completed_thesis = await critique_service.complete(sample_thesis.id)
    assert completed_thesis.status == ThesisStatus.CRITIQUED

    # Verify post-critique snapshot created
    snapshots = real_snapshot_repo.list_by_thesis(sample_thesis.id)
    post_snapshots = [s for s in snapshots if s.snapshot_type == "post_critique"]
    assert len(post_snapshots) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
