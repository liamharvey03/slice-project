"""
E3: Diagnostics API endpoint for LLM tool metrics.
"""
from fastapi import APIRouter

from slice.llm.metrics import llm_stats

router = APIRouter()


@router.get("/api/v1/diagnostics/llm")
def get_llm_diagnostics() -> dict:
    """
    Return LLM tool metrics.

    Returns a stable shape with all four tool keys present,
    even if counts are zero.

    Returns:
        {
            "llm_tool_metrics": {
                "thesis_review": {
                    "calls": int,
                    "errors": int,
                    "avg_latency_ms": float
                },
                "cross_theses": {...},
                "intuition_qa": {...},
                "daily_summary": {...}
            }
        }
    """
    return {
        "llm_tool_metrics": {
            name: {
                "calls": stats.calls,
                "errors": stats.errors,
                "avg_latency_ms": stats.avg_latency_ms,
            }
            for name, stats in llm_stats.items()
        }
    }

