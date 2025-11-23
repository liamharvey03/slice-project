def log_session_event(
    observation_id: int,
    llm_model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    latency_ms: int | None,
    memory_used: bool,
    risk_used: bool,
) -> None:
    """
    Phase 5 session logging.

    Stub implementation so SessionOrchestrator can import this safely.
    Real logging can later write to DB or file, but must never raise.
    """
    # No-op for now
    return None