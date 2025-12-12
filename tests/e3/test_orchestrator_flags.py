"""
E3: Tests for SessionOrchestrator skip_* flags.

Verifies that skip_ingest, skip_memory, and skip_risk flags are honored
and that they override use_memory/use_risk when set.
"""
import asyncio
from unittest.mock import Mock, call

import pytest

from voyager.session.orchestrator import SessionOrchestrator
from voyager.session.models import SessionOptions, SessionMode


class DummyLLM:
    model_name = "dummy-llm"

    async def chat(self, messages):
        return {
            "content": "test response",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }


@pytest.fixture
def mock_ingest(monkeypatch):
    """Mock ingestion pipeline that tracks calls."""
    mock_ingest_instance = Mock()
    mock_ingest_instance.ingest_observation_with_embedding.return_value = Mock(
        observation_id=123
    )

    monkeypatch.setattr(
        "voyager.session.orchestrator.IngestionPipeline",
        lambda: mock_ingest_instance,
    )
    return mock_ingest_instance


@pytest.fixture
def mock_memory(monkeypatch):
    """Mock memory retrieval that tracks calls."""
    mock_func = Mock(return_value={"items": []})

    monkeypatch.setattr(
        "voyager.session.orchestrator.get_memory_context_for_text",
        mock_func,
    )
    return mock_func


@pytest.fixture
def mock_risk(monkeypatch):
    """Mock risk snapshot that tracks calls."""
    mock_func = Mock(return_value=None)

    monkeypatch.setattr(
        "voyager.session.orchestrator.get_snapshot",
        mock_func,
    )
    return mock_func


@pytest.fixture
def mock_logger(monkeypatch):
    """Mock logger to avoid side effects."""
    monkeypatch.setattr(
        "voyager.session.orchestrator.log_session_event",
        lambda *args, **kwargs: None,
    )


def test_skip_ingest_flag_prevents_ingestion(mock_ingest, mock_memory, mock_risk, mock_logger):
    """skip_ingest=True should never call ingest_observation_with_embedding."""
    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions(skip_ingest=True)

    resp = asyncio.run(orch.run_session("test text", opts))

    # Ingest should never be called
    mock_ingest.ingest_observation_with_embedding.assert_not_called()
    # observation_id should be None
    assert resp.observation_id is None


def test_skip_ingest_false_calls_ingest(mock_ingest, mock_memory, mock_risk, mock_logger):
    """skip_ingest=False (default) should call ingest normally."""
    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions(skip_ingest=False)

    resp = asyncio.run(orch.run_session("test text", opts))

    # Ingest should be called once
    mock_ingest.ingest_observation_with_embedding.assert_called_once()
    assert resp.observation_id == 123


def test_skip_memory_flag_bypasses_memory_even_if_use_memory_true(
    mock_ingest, mock_memory, mock_risk, mock_logger
):
    """skip_memory=True should bypass memory even when use_memory=True."""
    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions(use_memory=True, skip_memory=True)

    resp = asyncio.run(orch.run_session("test text", opts))

    # Memory should never be called
    mock_memory.assert_not_called()
    # memory_context should be None
    assert resp.memory_context is None


def test_skip_memory_false_with_use_memory_true_calls_memory(
    mock_ingest, mock_memory, mock_risk, mock_logger
):
    """skip_memory=False + use_memory=True should call memory."""
    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions(use_memory=True, skip_memory=False)

    resp = asyncio.run(orch.run_session("test text", opts))

    # Memory should be called
    mock_memory.assert_called_once()
    assert resp.memory_context == {"items": []}


def test_skip_risk_flag_bypasses_risk_even_if_use_risk_true(
    mock_ingest, mock_memory, mock_risk, mock_logger
):
    """skip_risk=True should bypass risk even when use_risk=True."""
    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions(use_risk=True, skip_risk=True)

    resp = asyncio.run(orch.run_session("test text", opts))

    # Risk should never be called
    mock_risk.assert_not_called()
    # risk_snapshot should be None
    assert resp.risk_snapshot is None


def test_skip_risk_false_with_use_risk_true_calls_risk(
    mock_ingest, mock_memory, mock_risk, mock_logger
):
    """skip_risk=False + use_risk=True should call risk."""
    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions(use_risk=True, skip_risk=False)

    resp = asyncio.run(orch.run_session("test text", opts))

    # Risk should be called
    mock_risk.assert_called_once()
    assert resp.risk_snapshot is None  # Our mock returns None


def test_all_skip_flags_together(mock_ingest, mock_memory, mock_risk, mock_logger):
    """All skip flags together should bypass all side effects."""
    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions(
        skip_ingest=True,
        skip_memory=True,
        skip_risk=True,
    )

    resp = asyncio.run(orch.run_session("test text", opts))

    # None of these should be called
    mock_ingest.ingest_observation_with_embedding.assert_not_called()
    mock_memory.assert_not_called()
    mock_risk.assert_not_called()

    # All should be None
    assert resp.observation_id is None
    assert resp.memory_context is None
    assert resp.risk_snapshot is None


def test_e3_mode_skip_overrides_use_flags(mock_ingest, mock_memory, mock_risk, mock_logger):
    """
    E3 mode test: skip flags override use_* flags.
    
    This matches the exact SessionOptions used by E3 tools:
    use_memory=False, use_risk=False, skip_ingest=True, skip_memory=True, skip_risk=True
    """
    orch = SessionOrchestrator(llm_client=DummyLLM())
    
    # E3-safe options as used by all LLM tools
    opts = SessionOptions(
        use_memory=False,
        use_risk=False,
        skip_ingest=True,
        skip_memory=True,
        skip_risk=True,
    )

    resp = asyncio.run(orch.run_session("test text", opts))

    # Verify call counts explicitly
    assert mock_ingest.ingest_observation_with_embedding.call_count == 0
    assert mock_memory.call_count == 0
    assert mock_risk.call_count == 0

    # All context should be None
    assert resp.observation_id is None
    assert resp.memory_context is None
    assert resp.risk_snapshot is None


def test_e3_mode_skip_overrides_even_when_use_true(mock_ingest, mock_memory, mock_risk, mock_logger):
    """
    Even with use_memory=True and use_risk=True, skip flags take precedence.
    """
    orch = SessionOrchestrator(llm_client=DummyLLM())
    
    opts = SessionOptions(
        use_memory=True,  # Would normally enable memory
        use_risk=True,    # Would normally enable risk
        skip_ingest=True,
        skip_memory=True,
        skip_risk=True,
    )

    resp = asyncio.run(orch.run_session("test text", opts))

    # Skip flags should override use_* flags
    assert mock_ingest.ingest_observation_with_embedding.call_count == 0
    assert mock_memory.call_count == 0
    assert mock_risk.call_count == 0

    # All context should be None
    assert resp.observation_id is None
    assert resp.memory_context is None
    assert resp.risk_snapshot is None

