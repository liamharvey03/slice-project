"""
E3: In-memory metrics for LLM tool calls.

Tracks calls, errors, and latency per tool.
All metrics are in-memory only (no persistence).
"""
from pydantic import BaseModel


class LLMToolStats(BaseModel):
    """
    Statistics for a single LLM tool.

    Fields:
        calls: int - Total number of calls (success + failure)
        errors: int - Number of calls that failed (parse/validation errors)
        total_latency_ms: int - Sum of all latencies in milliseconds
    """

    calls: int = 0
    errors: int = 0
    total_latency_ms: int = 0

    @property
    def avg_latency_ms(self) -> float:
        """
        Average latency per call in milliseconds.

        Returns 0.0 if no calls have been made.
        """
        if self.calls == 0:
            return 0.0
        return self.total_latency_ms / self.calls


# Global stats dictionary - one entry per tool
llm_stats: dict[str, LLMToolStats] = {
    "thesis_review": LLMToolStats(),
    "cross_theses": LLMToolStats(),
    "intuition_qa": LLMToolStats(),
    "daily_summary": LLMToolStats(),
}


def record_llm_call(tool: str, latency_ms: int, success: bool) -> None:
    """
    Record a single LLM tool call.

    Args:
        tool: Tool name (must be one of the registered tools)
        latency_ms: Call latency in milliseconds
        success: True if call succeeded, False if it failed

    Raises:
        KeyError: If tool name is not registered
    """
    if tool not in llm_stats:
        raise KeyError(f"Unknown tool: {tool}. Registered tools: {list(llm_stats.keys())}")

    stats = llm_stats[tool]
    stats.calls += 1
    stats.total_latency_ms += latency_ms
    if not success:
        stats.errors += 1


def reset_stats() -> None:
    """
    Reset all tool statistics to zero.

    Useful for test isolation. Not thread-safe.
    """
    for stats in llm_stats.values():
        stats.calls = 0
        stats.errors = 0
        stats.total_latency_ms = 0

