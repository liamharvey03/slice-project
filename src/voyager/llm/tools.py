"""
E3: LLM tool implementations and shared helpers.

This module contains:
- extract_json: Helper to salvage JSON from LLM responses
- LLMOutputError: Custom exception for parse failures
- OrchestratorProtocol: Type protocol for orchestrator dependency
- Four tool functions: llm_review_thesis, llm_cross_theses, llm_query_intuition, llm_daily_summary
"""
import time
from typing import Protocol, List

from voyager.session.models import SessionOptions, SessionResponse, SessionMode
from voyager.models.thesis import Thesis
from voyager.models.evaluation import ThesisEvaluationResult
from voyager.models.observation import Observation
from voyager.models.llm_outputs import (
    ThesisReview,
    CrossThesisReport,
    IntuitionAnswer,
    DailySummary,
)
from voyager.models.llm_inputs import DailyContext
from voyager.llm.prompts import (
    build_thesis_review_prompt,
    build_cross_theses_prompt,
    build_intuition_prompt,
    build_daily_summary_prompt,
)
from voyager.llm.metrics import record_llm_call


class LLMOutputError(Exception):
    """Raised when LLM output cannot be parsed as valid JSON."""

    pass


class OrchestratorProtocol(Protocol):
    """
    Protocol for orchestrator dependency injection.

    E3 tools depend on this interface rather than concrete SessionOrchestrator,
    making testing and mocking easier.
    """

    async def run_session(
        self, text: str, options: SessionOptions
    ) -> SessionResponse:
        """
        Run a session with the given text and options.

        Returns:
            SessionResponse with llm_response containing the raw LLM output
        """
        ...


def extract_json(raw: str) -> str:
    """
    Extract JSON from LLM response, salvaging when wrapped in text.

    Strategy: Find first '{' to last '}' and return that substring.
    This handles cases where the LLM adds commentary before/after the JSON.

    Args:
        raw: Raw LLM response string

    Returns:
        JSON string (substring from first '{' to last '}')

    Raises:
        LLMOutputError: If no '{' or '}' found, or if they're in wrong order
    """
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")

    if first_brace == -1 or last_brace == -1:
        raise LLMOutputError(
            f"No JSON object found in response. First '{{' at {first_brace}, last '}}' at {last_brace}"
        )

    if first_brace > last_brace:
        raise LLMOutputError(
            f"Malformed JSON: first '{{' at {first_brace} comes after last '}}' at {last_brace}"
        )

    return raw[first_brace : last_brace + 1]


async def llm_review_thesis(
    thesis: Thesis,
    evaluation: ThesisEvaluationResult,
    orchestrator: OrchestratorProtocol,
) -> ThesisReview:
    """
    LLM review of a thesis against its evaluation.

    Pure function: no DB, no side effects beyond LLM call.

    Args:
        thesis: Thesis to review
        evaluation: E2 evaluation results
        orchestrator: Orchestrator to use for LLM call

    Returns:
        ThesisReview DTO

    Raises:
        LLMOutputError: If LLM output cannot be parsed as valid JSON
    """
    start = time.monotonic()
    success = False

    try:
        prompt = build_thesis_review_prompt(thesis, evaluation)

        # E3-safe options: explicitly disable all side effects
        options = SessionOptions(
            mode=SessionMode.ANALYST,
            use_memory=False,
            use_risk=False,
            skip_ingest=True,
            skip_memory=True,
            skip_risk=True,
        )

        resp = await orchestrator.run_session(prompt, options)
        raw = resp.llm_response

        # Try parsing directly first
        try:
            result = ThesisReview.parse_raw(raw)
        except Exception:
            # Salvage JSON if wrapped in text
            json_str = extract_json(raw)
            result = ThesisReview.parse_raw(json_str)

        success = True
        return result

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        record_llm_call("thesis_review", latency_ms, success)


async def llm_cross_theses(
    theses: List[Thesis],
    orchestrator: OrchestratorProtocol,
) -> CrossThesisReport:
    """
    LLM analysis of relationships between multiple theses.

    Pure function: no DB, no side effects beyond LLM call.

    Args:
        theses: List of theses to analyze
        orchestrator: Orchestrator to use for LLM call

    Returns:
        CrossThesisReport DTO

    Raises:
        LLMOutputError: If LLM output cannot be parsed as valid JSON
    """
    start = time.monotonic()
    success = False

    try:
        prompt = build_cross_theses_prompt(theses)

        # E3-safe options: explicitly disable all side effects
        options = SessionOptions(
            mode=SessionMode.ANALYST,
            use_memory=False,
            use_risk=False,
            skip_ingest=True,
            skip_memory=True,
            skip_risk=True,
        )

        resp = await orchestrator.run_session(prompt, options)
        raw = resp.llm_response

        # Try parsing directly first
        try:
            result = CrossThesisReport.parse_raw(raw)
        except Exception:
            # Salvage JSON if wrapped in text
            json_str = extract_json(raw)
            result = CrossThesisReport.parse_raw(json_str)

        success = True
        return result

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        record_llm_call("cross_theses", latency_ms, success)


async def llm_query_intuition(
    question: str,
    observations: List[Observation],
    orchestrator: OrchestratorProtocol,
) -> IntuitionAnswer:
    """
    LLM answer to an intuition query based on observations.

    Pure function: no DB, no side effects beyond LLM call.
    Validates that references are actual observation IDs.

    Args:
        question: User question
        observations: Observations to use as context
        orchestrator: Orchestrator to use for LLM call

    Returns:
        IntuitionAnswer DTO with validated references

    Raises:
        LLMOutputError: If LLM output cannot be parsed as valid JSON
    """
    start = time.monotonic()
    success = False

    try:
        prompt = build_intuition_prompt(question, observations)

        # E3-safe options: explicitly disable all side effects
        options = SessionOptions(
            mode=SessionMode.STANDARD,
            use_memory=False,
            use_risk=False,
            skip_ingest=True,
            skip_memory=True,
            skip_risk=True,
        )

        resp = await orchestrator.run_session(prompt, options)
        raw = resp.llm_response

        # Try parsing directly first
        try:
            result = IntuitionAnswer.parse_raw(raw)
        except Exception:
            # Salvage JSON if wrapped in text
            json_str = extract_json(raw)
            result = IntuitionAnswer.parse_raw(json_str)

        # Reference validation: filter to only IDs present in observations
        allowed_ids = {obs.id for obs in observations}
        original_refs = result.references

        # Filter to only allowed IDs
        filtered = [r for r in original_refs if r in allowed_ids]

        # Dedupe while preserving order
        seen = set()
        filtered_unique = []
        for r in filtered:
            if r not in seen:
                seen.add(r)
                filtered_unique.append(r)

        # Only flip insufficient_context if we dropped any hallucinated IDs (not just duplicates)
        if len(filtered) < len(original_refs):
            result.insufficient_context = True

        result.references = filtered_unique

        success = True
        return result

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        record_llm_call("intuition_qa", latency_ms, success)


async def llm_daily_summary(
    context: DailyContext,
    orchestrator: OrchestratorProtocol,
) -> DailySummary:
    """
    LLM daily summary for portfolio manager.

    Pure function: no DB, no side effects beyond LLM call.
    Validates that thesis_references are actual thesis IDs.

    Args:
        context: Daily context snapshot
        orchestrator: Orchestrator to use for LLM call

    Returns:
        DailySummary DTO with validated thesis_references

    Raises:
        LLMOutputError: If LLM output cannot be parsed as valid JSON
    """
    start = time.monotonic()
    success = False

    try:
        prompt = build_daily_summary_prompt(context)

        # E3-safe options: explicitly disable all side effects
        options = SessionOptions(
            mode=SessionMode.CONCISE,
            use_memory=False,
            use_risk=False,
            skip_ingest=True,
            skip_memory=True,
            skip_risk=True,
        )

        resp = await orchestrator.run_session(prompt, options)
        raw = resp.llm_response

        # Try parsing directly first
        try:
            result = DailySummary.parse_raw(raw)
        except Exception:
            # Salvage JSON if wrapped in text
            json_str = extract_json(raw)
            result = DailySummary.parse_raw(json_str)

        # Reference validation: filter to only IDs present in active_theses
        allowed_ids = {thesis.id for thesis in context.active_theses}
        original_refs = result.thesis_references

        # Filter to only allowed IDs
        filtered = [r for r in original_refs if r in allowed_ids]

        # Dedupe while preserving order
        seen = set()
        filtered_unique = []
        for r in filtered:
            if r not in seen:
                seen.add(r)
                filtered_unique.append(r)

        # Only flip insufficient_context if we dropped any hallucinated IDs (not just duplicates)
        if len(filtered) < len(original_refs):
            result.insufficient_context = True

        result.thesis_references = filtered_unique

        success = True
        return result

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        record_llm_call("daily_summary", latency_ms, success)

