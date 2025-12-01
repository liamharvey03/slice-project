"""
E3: Contract tests for llm_daily_summary tool.

Tests:
- Happy path DTO parsing
- Thesis reference validation (filters hallucinated IDs)
- Insufficient context behavior
- Metrics recording
"""
import asyncio
import json
import pytest

from slice.llm.tools import llm_daily_summary
from slice.models.llm_inputs import DailyContext, Alert
from slice.models.llm_outputs import DailySummary
from slice.models.portfolio import PortfolioSnapshot, PortfolioTotals, Position
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.observation import Observation
from slice.models.common import Direction, ThesisStatus, Sentiment
from slice.llm.metrics import llm_stats, reset_stats
from datetime import date, datetime


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


def make_test_thesis(id: str) -> Thesis:
    """Create a minimal test thesis."""
    return Thesis(
        id=id,
        title=f"Thesis {id}",
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


def make_test_context() -> DailyContext:
    """Create a minimal test daily context."""
    portfolio = PortfolioSnapshot(
        positions=[],
        totals=PortfolioTotals(
            portfolio_value=1000.0,
            gross_exposure=0.0,
            net_exposure=0.0,
        ),
    )

    return DailyContext(
        date=date.today(),
        portfolio_snapshot=portfolio,
        alerts=[],
        observations=[],
        active_theses=[
            make_test_thesis("T1"),
            make_test_thesis("T2"),
        ],
    )


@pytest.mark.asyncio
async def test_llm_daily_summary_happy_path():
    """Happy path: valid JSON returns DailySummary with valid thesis references."""
    reset_stats()

    response_json = json.dumps({
        "key_narratives": ["Market volatility increased", "Fed signals rate cuts"],
        "risk_highlights": ["High concentration risk"],
        "thesis_references": ["T1", "T2"],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    context = make_test_context()

    result = await llm_daily_summary(context, orchestrator)

    assert isinstance(result, DailySummary)
    assert len(result.key_narratives) == 2
    assert result.thesis_references == ["T1", "T2"]
    assert result.insufficient_context is False

    # Verify metrics
    stats = llm_stats["daily_summary"]
    assert stats.calls == 1
    assert stats.errors == 0


@pytest.mark.asyncio
async def test_llm_daily_summary_thesis_reference_validation_filters_hallucinated():
    """Hallucinated thesis IDs are filtered and insufficient_context set."""
    reset_stats()

    response_json = json.dumps({
        "key_narratives": ["Test narrative"],
        "risk_highlights": [],
        "thesis_references": ["T1", "T999"],  # T999 doesn't exist
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    context = make_test_context()

    result = await llm_daily_summary(context, orchestrator)

    # T999 should be filtered out
    assert result.thesis_references == ["T1"]
    # insufficient_context should be True because we dropped a reference
    assert result.insufficient_context is True


@pytest.mark.asyncio
async def test_llm_daily_summary_thesis_reference_deduplication():
    """Duplicate thesis references are deduplicated while preserving order."""
    reset_stats()

    response_json = json.dumps({
        "key_narratives": [],
        "risk_highlights": [],
        "thesis_references": ["T1", "T2", "T1"],  # T1 appears twice
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    context = make_test_context()

    result = await llm_daily_summary(context, orchestrator)

    # Should dedupe while preserving order
    assert result.thesis_references == ["T1", "T2"]
    assert result.insufficient_context is False  # No hallucination, just dupes


@pytest.mark.asyncio
async def test_llm_daily_summary_insufficient_context_empty_context():
    """Empty context should result in insufficient_context=True."""
    reset_stats()

    response_json = json.dumps({
        "key_narratives": [],
        "risk_highlights": [],
        "thesis_references": [],
        "insufficient_context": True,
    })

    orchestrator = MockOrchestrator(response_json)
    context = DailyContext(
        date=date.today(),
        portfolio_snapshot=PortfolioSnapshot(
            positions=[],
            totals=PortfolioTotals(
                portfolio_value=0.0,
                gross_exposure=0.0,
                net_exposure=0.0,
            ),
        ),
        alerts=[],
        observations=[],
        active_theses=[],
    )

    result = await llm_daily_summary(context, orchestrator)

    assert result.insufficient_context is True
    assert result.thesis_references == []


@pytest.mark.asyncio
async def test_llm_daily_summary_prompt_contains_context_data():
    """Verify prompt wiring: thesis IDs and portfolio data appear in constructed prompt."""
    reset_stats()

    response_json = json.dumps({
        "key_narratives": [],
        "risk_highlights": [],
        "thesis_references": [],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    context = make_test_context()

    await llm_daily_summary(context, orchestrator)

    # Get the prompt that was passed to orchestrator
    assert len(orchestrator.calls) == 1
    prompt, _ = orchestrator.calls[0]

    # Verify sentinel inputs from context appear in prompt
    assert "T1" in prompt  # thesis ID
    assert "T2" in prompt  # thesis ID
    assert "Thesis T1" in prompt  # thesis title
    assert "1000.00" in prompt  # portfolio value

