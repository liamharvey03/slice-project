"""
E3: Contract tests for llm_cross_theses tool.

Tests:
- Happy path DTO parsing
- Insufficient context behavior
- Malformed JSON handling
- Metrics recording
"""
import asyncio
import json
import pytest

from voyager.llm.tools import llm_cross_theses, LLMOutputError
from voyager.models.thesis import Thesis, ThesisExpressionLeg
from voyager.models.llm_outputs import CrossThesisReport
from voyager.models.common import Direction, ThesisStatus
from voyager.llm.metrics import llm_stats, reset_stats


def make_test_thesis(id: str, title: str) -> Thesis:
    """Create a minimal test thesis."""
    return Thesis(
        id=id,
        title=title,
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


class MockOrchestrator:
    """Mock orchestrator that returns canned responses."""

    def __init__(self, response_json: str, latency_ms: int = 100):
        self.response_json = response_json
        self.latency_ms = latency_ms
        self.calls = []

    async def run_session(self, text: str, options):
        self.calls.append((text, options))
        from voyager.session.models import SessionResponse

        return SessionResponse(
            observation_id=None,
            llm_response=self.response_json,
            latency_ms=self.latency_ms,
        )


@pytest.mark.asyncio
async def test_llm_cross_theses_happy_path():
    """Happy path: valid JSON returns CrossThesisReport DTO."""
    reset_stats()

    response_json = json.dumps({
        "overlaps": ["Both focus on inflation"],
        "contradictions": ["T1 bullish, T2 bearish"],
        "gaps": ["No coverage of energy sector"],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json, latency_ms=300)
    theses = [
        make_test_thesis("T1", "Thesis 1"),
        make_test_thesis("T2", "Thesis 2"),
    ]

    result = await llm_cross_theses(theses, orchestrator)

    assert isinstance(result, CrossThesisReport)
    assert len(result.overlaps) == 1
    assert "inflation" in result.overlaps[0]
    assert len(result.contradictions) == 1
    assert result.insufficient_context is False

    # Verify orchestrator was called with E3-safe options
    assert len(orchestrator.calls) == 1
    _, options = orchestrator.calls[0]
    assert options.skip_ingest is True
    assert options.skip_memory is True
    assert options.skip_risk is True

    # Verify metrics
    stats = llm_stats["cross_theses"]
    assert stats.calls == 1
    assert stats.errors == 0
    assert stats.avg_latency_ms >= 0.0


@pytest.mark.asyncio
async def test_llm_cross_theses_insufficient_context():
    """Insufficient context flag is preserved."""
    reset_stats()

    response_json = json.dumps({
        "overlaps": [],
        "contradictions": [],
        "gaps": [],
        "insufficient_context": True,
    })

    orchestrator = MockOrchestrator(response_json)
    theses = [make_test_thesis("T1", "Thesis 1")]

    result = await llm_cross_theses(theses, orchestrator)

    assert result.insufficient_context is True
    assert result.overlaps == []


@pytest.mark.asyncio
async def test_llm_cross_theses_invalid_json_raises():
    """Completely invalid JSON raises LLMOutputError."""
    reset_stats()

    response_json = "Not JSON at all"

    orchestrator = MockOrchestrator(response_json)
    theses = [make_test_thesis("T1", "Thesis 1")]

    with pytest.raises(LLMOutputError):
        await llm_cross_theses(theses, orchestrator)

    # Verify metrics recorded error
    stats = llm_stats["cross_theses"]
    assert stats.calls == 1
    assert stats.errors == 1


@pytest.mark.asyncio
async def test_llm_cross_theses_prompt_contains_thesis_data():
    """Verify prompt wiring: thesis IDs and titles appear in constructed prompt."""
    reset_stats()

    response_json = json.dumps({
        "overlaps": [],
        "contradictions": [],
        "gaps": [],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    theses = [
        make_test_thesis("T1", "Inflation Thesis"),
        make_test_thesis("T2", "Growth Slowdown"),
    ]

    await llm_cross_theses(theses, orchestrator)

    # Get the prompt that was passed to orchestrator
    assert len(orchestrator.calls) == 1
    prompt, _ = orchestrator.calls[0]

    # Verify sentinel inputs from theses appear in prompt
    assert "T1" in prompt
    assert "T2" in prompt
    assert "Inflation Thesis" in prompt
    assert "Growth Slowdown" in prompt

