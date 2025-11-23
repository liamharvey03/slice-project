import logging
from typing import Optional

logger = logging.getLogger("slice.session")


def log_session_event(
    observation_id: int,
    llm_model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    latency_ms: Optional[int],
    memory_used: bool,
    risk_used: bool,
) -> None:
    """
    Phase 5 session logging.

    Requirements:
      - Must NEVER raise (even if logging backend is misconfigured).
      - Should emit a structured log line that can later be wired into
        whatever logging / DB sink we choose.
    """
    try:
        logger.info(
            "session_event",
            extra={
                "observation_id": observation_id,
                "llm_model": llm_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "memory_used": memory_used,
                "risk_used": risk_used,
            },
        )
    except Exception:
        # Hard guarantee: logging cannot interfere with the main flow.
        return None