"""
E3: Contract tests for llm_review_thesis tool.

Tests:
- Happy path DTO parsing
- Insufficient context behavior
- Malformed JSON handling
- Metrics recording
"""
import asyncio
import json
import pytest

from slice.llm.tools import llm_review_thesis, LLMOutputError
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.evaluation import ThesisEvaluationResult, EquityPoint, ScenarioImpact
from slice.models.llm_outputs import ThesisReview
from slice.models.common import Direction, ThesisStatus
from slice.llm.metrics import llm_stats, reset_stats
from datetime import datetime


class MockOrchestrator:
    """Mock orchestrator that returns canned responses."""

    def __init__(self, response_json: str, latency_ms: int = 100):
        self.response_json = response_json
        self.latency_ms = latency_ms
        self.calls = []

    async def run_session(self, text: str, options):
        self.calls.append((text, options))
        from slice.session.models import SessionResponse

        return SessionResponse(
            observation_id=None,
            llm_response=self.response_json,
            latency_ms=self.latency_ms,
        )


def make_test_thesis() -> Thesis:
    """Create a minimal test thesis."""
    return Thesis(
        id="T1",
        title="Test Thesis",
        hypothesis="Test hypothesis",
        drivers=["driver1"],
        disconfirmers=["disconf1"],
        expression=[
            ThesisExpressionLeg(
                asset="GLD",
                direction=Direction.LONG,
                size_pct=100.0,
            )
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
    )


def make_test_evaluation() -> ThesisEvaluationResult:
    """Create a minimal test evaluation."""
    return ThesisEvaluationResult(
        performance={
            "total_return": 10.0,
            "cagr": 5.0,
            "volatility": 15.0,
            "sharpe": 0.5,
            "max_drawdown": 5.0,
        },
        timeseries=[
            EquityPoint(date=datetime.now(), value=1.0),
        ],
        risk_metrics={
            "max_weight_pct": 100.0,
            "VaR_95": 2.0,
            "max_drawdown_pct": 5.0,
        },
        scenarios=[
            ScenarioImpact(name="All -10%", pnl_abs=-100.0, pnl_pct=-10.0),
            ScenarioImpact(name="All +10%", pnl_abs=100.0, pnl_pct=10.0),
        ],
    )


@pytest.mark.asyncio
async def test_llm_review_thesis_happy_path():
    """Happy path: valid JSON returns ThesisReview DTO."""
    reset_stats()

    response_json = json.dumps({
        "critique": "Plausible but over-concentrated.",
        "questions": ["What if inflation re-accelerates?"],
        "risk_flags": ["Concentration in energy"],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json, latency_ms=500)
    thesis = make_test_thesis()
    evaluation = make_test_evaluation()

    result = await llm_review_thesis(thesis, evaluation, orchestrator)

    assert isinstance(result, ThesisReview)
    assert result.critique == "Plausible but over-concentrated."
    assert len(result.questions) == 1
    assert "inflation" in result.questions[0]
    assert result.insufficient_context is False

    # Verify orchestrator was called with E3-safe options
    assert len(orchestrator.calls) == 1
    _, options = orchestrator.calls[0]
    assert options.skip_ingest is True
    assert options.skip_memory is True
    assert options.skip_risk is True
    assert options.use_memory is False
    assert options.use_risk is False

    # Verify metrics
    stats = llm_stats["thesis_review"]
    assert stats.calls == 1
    assert stats.errors == 0
    assert stats.avg_latency_ms >= 0.0


@pytest.mark.asyncio
async def test_llm_review_thesis_insufficient_context():
    """Insufficient context flag is preserved."""
    reset_stats()

    response_json = json.dumps({
        "critique": "",
        "questions": [],
        "risk_flags": [],
        "insufficient_context": True,
    })

    orchestrator = MockOrchestrator(response_json)
    thesis = make_test_thesis()
    evaluation = make_test_evaluation()

    result = await llm_review_thesis(thesis, evaluation, orchestrator)

    assert result.insufficient_context is True
    assert result.critique == ""
    assert result.questions == []


@pytest.mark.asyncio
async def test_llm_review_thesis_json_with_trailing_garbage():
    """JSON with trailing text is salvaged."""
    reset_stats()

    response_json = '{"critique": "test", "questions": [], "risk_flags": [], "insufficient_context": false} extra text'

    orchestrator = MockOrchestrator(response_json)
    thesis = make_test_thesis()
    evaluation = make_test_evaluation()

    result = await llm_review_thesis(thesis, evaluation, orchestrator)

    assert result.critique == "test"
    stats = llm_stats["thesis_review"]
    assert stats.calls == 1
    assert stats.errors == 0


@pytest.mark.asyncio
async def test_llm_review_thesis_invalid_json_raises():
    """Completely invalid JSON raises LLMOutputError."""
    reset_stats()

    response_json = "Not JSON at all"

    orchestrator = MockOrchestrator(response_json)
    thesis = make_test_thesis()
    evaluation = make_test_evaluation()

    with pytest.raises(LLMOutputError):
        await llm_review_thesis(thesis, evaluation, orchestrator)

    # Verify metrics recorded error
    stats = llm_stats["thesis_review"]
    assert stats.calls == 1
    assert stats.errors == 1


@pytest.mark.asyncio
async def test_llm_review_thesis_missing_fields_raises():
    """Missing required fields raises ValidationError."""
    reset_stats()

    response_json = json.dumps({
        "critique": "test",
        # Missing questions, risk_flags, insufficient_context
    })

    orchestrator = MockOrchestrator(response_json)
    thesis = make_test_thesis()
    evaluation = make_test_evaluation()

    with pytest.raises(Exception):  # Pydantic ValidationError
        await llm_review_thesis(thesis, evaluation, orchestrator)

    # Verify metrics recorded error
    stats = llm_stats["thesis_review"]
    assert stats.calls == 1
    assert stats.errors == 1


@pytest.mark.asyncio
async def test_llm_review_thesis_prompt_contains_thesis_data():
    """Verify prompt wiring: thesis title and metrics appear in constructed prompt."""
    reset_stats()

    response_json = json.dumps({
        "critique": "test",
        "questions": [],
        "risk_flags": [],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    thesis = make_test_thesis()
    evaluation = make_test_evaluation()

    await llm_review_thesis(thesis, evaluation, orchestrator)

    # Get the prompt that was passed to orchestrator
    assert len(orchestrator.calls) == 1
    prompt, _ = orchestrator.calls[0]

    # Verify sentinel inputs from thesis appear in prompt
    assert thesis.title in prompt
    assert thesis.hypothesis in prompt
    assert "GLD" in prompt  # asset from expression
    
    # Verify evaluation metrics appear
    assert "10.00" in prompt  # total_return
    assert "15.00" in prompt  # volatility

