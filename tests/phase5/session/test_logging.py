from src.slice.session.logging import log_session_event


def test_log_session_event_does_not_raise(monkeypatch):
    # Force the logger to raise internally to verify we still don't propagate.
    def broken_info(*args, **kwargs):
        raise RuntimeError("logging failure")

    monkeypatch.setattr(
        "src.slice.session.logging.logger.info",
        broken_info,
    )

    # Should not raise, even if logger.info explodes
    log_session_event(
        observation_id=123,
        llm_model="dummy-llm",
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=42,
        memory_used=True,
        risk_used=False,
    )


def test_log_session_event_happy_path():
    # Just call it and ensure no exception
    log_session_event(
        observation_id=1,
        llm_model="dummy-llm",
        prompt_tokens=None,
        completion_tokens=None,
        latency_ms=None,
        memory_used=False,
        risk_used=False,
    )