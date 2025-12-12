"""
E3: Tests for LLM metrics infrastructure.

Verifies:
- Calls and latency update on both success and failure
- errors increments only on success=False
- avg_latency_ms computed correctly
"""
import pytest

from voyager.llm.metrics import (
    LLMToolStats,
    llm_stats,
    record_llm_call,
    reset_stats,
)


def test_llm_tool_stats_initial_state():
    """Fresh stats start at zero."""
    stats = LLMToolStats()
    assert stats.calls == 0
    assert stats.errors == 0
    assert stats.total_latency_ms == 0
    assert stats.avg_latency_ms == 0.0


def test_llm_tool_stats_avg_latency():
    """avg_latency_ms computed correctly."""
    stats = LLMToolStats(calls=2, total_latency_ms=1000)
    assert stats.avg_latency_ms == 500.0

    # Zero calls returns 0.0
    stats_zero = LLMToolStats()
    assert stats_zero.avg_latency_ms == 0.0


def test_record_llm_call_success():
    """Successful calls increment calls and latency, not errors."""
    reset_stats()
    tool = "thesis_review"

    record_llm_call(tool, latency_ms=100, success=True)

    stats = llm_stats[tool]
    assert stats.calls == 1
    assert stats.errors == 0
    assert stats.total_latency_ms == 100
    assert stats.avg_latency_ms == 100.0


def test_record_llm_call_failure():
    """Failed calls increment calls, latency, AND errors."""
    reset_stats()
    tool = "thesis_review"

    record_llm_call(tool, latency_ms=200, success=False)

    stats = llm_stats[tool]
    assert stats.calls == 1
    assert stats.errors == 1
    assert stats.total_latency_ms == 200
    assert stats.avg_latency_ms == 200.0


def test_record_llm_call_multiple():
    """Multiple calls accumulate correctly."""
    reset_stats()
    tool = "cross_theses"

    record_llm_call(tool, latency_ms=100, success=True)
    record_llm_call(tool, latency_ms=500, success=True)
    record_llm_call(tool, latency_ms=300, success=False)

    stats = llm_stats[tool]
    assert stats.calls == 3
    assert stats.errors == 1
    assert stats.total_latency_ms == 900
    assert stats.avg_latency_ms == 300.0


def test_record_llm_call_unknown_tool():
    """Unknown tool raises KeyError."""
    with pytest.raises(KeyError, match="Unknown tool"):
        record_llm_call("unknown_tool", latency_ms=100, success=True)


def test_reset_stats():
    """reset_stats zeros all tool stats."""
    tool = "intuition_qa"
    record_llm_call(tool, latency_ms=100, success=True)
    record_llm_call(tool, latency_ms=200, success=False)

    assert llm_stats[tool].calls == 2
    assert llm_stats[tool].errors == 1

    reset_stats()

    assert llm_stats[tool].calls == 0
    assert llm_stats[tool].errors == 0
    assert llm_stats[tool].total_latency_ms == 0


def test_all_tools_pre_registered():
    """All four tools are pre-registered in llm_stats."""
    expected_tools = {"thesis_review", "cross_theses", "intuition_qa", "daily_summary"}
    assert set(llm_stats.keys()) == expected_tools

    for tool in expected_tools:
        assert isinstance(llm_stats[tool], LLMToolStats)

