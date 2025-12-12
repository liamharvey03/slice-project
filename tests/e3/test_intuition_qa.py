"""
E3: Contract tests for llm_query_intuition tool.

Tests:
- Happy path DTO parsing
- Reference validation (filters hallucinated IDs)
- Insufficient context behavior
- Metrics recording
"""
import asyncio
import json
import pytest

from voyager.llm.tools import llm_query_intuition
from voyager.models.observation import Observation
from voyager.models.llm_outputs import IntuitionAnswer
from voyager.models.common import Sentiment
from voyager.llm.metrics import llm_stats, reset_stats
from datetime import datetime


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


def make_observation(id: str, text: str) -> Observation:
    """Create a minimal test observation."""
    return Observation(
        id=id,
        timestamp=datetime.now(),
        text=text,
        thesis_ref=[],
        sentiment=Sentiment.NEUTRAL,
        categories=[],
        actionable="NO",
    )


@pytest.mark.asyncio
async def test_llm_query_intuition_happy_path():
    """Happy path: valid JSON returns IntuitionAnswer with valid references."""
    reset_stats()

    response_json = json.dumps({
        "answer": "Growth is slowing based on the observations.",
        "references": ["obs1", "obs2"],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    observations = [
        make_observation("obs1", "GDP growth declined"),
        make_observation("obs2", "Unemployment rising"),
    ]

    result = await llm_query_intuition("What is the economic outlook?", observations, orchestrator)

    assert isinstance(result, IntuitionAnswer)
    assert "slowing" in result.answer.lower()
    assert result.references == ["obs1", "obs2"]
    assert result.insufficient_context is False

    # Verify metrics
    stats = llm_stats["intuition_qa"]
    assert stats.calls == 1
    assert stats.errors == 0


@pytest.mark.asyncio
async def test_llm_query_intuition_reference_validation_filters_hallucinated():
    """Hallucinated observation IDs are filtered and insufficient_context set."""
    reset_stats()

    response_json = json.dumps({
        "answer": "Growth is slowing.",
        "references": ["obs2", "obs999"],  # obs999 doesn't exist
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    observations = [
        make_observation("obs1", "GDP growth declined"),
        make_observation("obs2", "Unemployment rising"),
    ]

    result = await llm_query_intuition("What is the economic outlook?", observations, orchestrator)

    # obs999 should be filtered out
    assert result.references == ["obs2"]
    # insufficient_context should be True because we dropped a reference
    assert result.insufficient_context is True


@pytest.mark.asyncio
async def test_llm_query_intuition_reference_deduplication():
    """Duplicate references are deduplicated while preserving order."""
    reset_stats()

    response_json = json.dumps({
        "answer": "Test answer",
        "references": ["obs1", "obs2", "obs1"],  # obs1 appears twice
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    observations = [
        make_observation("obs1", "Observation 1"),
        make_observation("obs2", "Observation 2"),
    ]

    result = await llm_query_intuition("Test question", observations, orchestrator)

    # Should dedupe while preserving order
    assert result.references == ["obs1", "obs2"]
    assert result.insufficient_context is False  # No hallucination, just dupes


@pytest.mark.asyncio
async def test_llm_query_intuition_insufficient_context_empty_observations():
    """Empty observations should result in insufficient_context=True."""
    reset_stats()

    response_json = json.dumps({
        "answer": "",
        "references": [],
        "insufficient_context": True,
    })

    orchestrator = MockOrchestrator(response_json)
    observations = []

    result = await llm_query_intuition("What happened?", observations, orchestrator)

    assert result.insufficient_context is True
    assert result.answer == ""
    assert result.references == []


@pytest.mark.asyncio
async def test_llm_query_intuition_all_references_hallucinated():
    """If all references are hallucinated, references becomes empty and insufficient_context=True."""
    reset_stats()

    response_json = json.dumps({
        "answer": "Some answer",
        "references": ["obs999", "obs888"],  # Neither exists
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    observations = [
        make_observation("obs1", "Real observation"),
    ]

    result = await llm_query_intuition("Test", observations, orchestrator)

    assert result.references == []
    assert result.insufficient_context is True


@pytest.mark.asyncio
async def test_llm_query_intuition_prompt_contains_question_and_observations():
    """Verify prompt wiring: question and observation IDs/text appear in constructed prompt."""
    reset_stats()

    response_json = json.dumps({
        "answer": "test",
        "references": [],
        "insufficient_context": False,
    })

    orchestrator = MockOrchestrator(response_json)
    observations = [
        make_observation("obs_test_123", "GDP growth rate declined"),
        make_observation("obs_test_456", "Unemployment at historic lows"),
    ]
    question = "What is the economic outlook for Q4?"

    await llm_query_intuition(question, observations, orchestrator)

    # Get the prompt that was passed to orchestrator
    assert len(orchestrator.calls) == 1
    prompt, _ = orchestrator.calls[0]

    # Verify sentinel inputs appear in prompt
    assert question in prompt
    assert "obs_test_123" in prompt
    assert "obs_test_456" in prompt
    assert "GDP growth rate declined" in prompt
    assert "Unemployment at historic lows" in prompt

