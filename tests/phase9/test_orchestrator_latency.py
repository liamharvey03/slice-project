"""
Phase 9: basic performance/latency contract check.

We don't try to run a real LLM session here (that depends on injected clients).
Instead, we pin the structural contract that the session response exposes a
`latency_ms` field, so callers can evaluate performance.
"""

from voyager.session.orchestrator import SessionResponse


def test_session_response_has_latency_ms_field():
    # Support both Pydantic-style models and dataclasses.
    fields = getattr(SessionResponse, "__fields__", None)
    if fields is not None:
        # Pydantic model
        assert "latency_ms" in fields
    else:
        # Dataclass or plain class with annotations
        annotations = getattr(SessionResponse, "__annotations__", {})
        assert "latency_ms" in annotations
