import asyncio

from src.slice.session.orchestrator import SessionOrchestrator
from src.slice.session.models import SessionOptions


class DummyLLM:
    model_name = "dummy-llm"

    async def chat(self, messages):
        # very simple fake response
        return {
            "content": "ok",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }


def test_orchestrator_basic(monkeypatch):
    # Patch ingestion pipeline to avoid touching the real DB
    class DummyIngest:
        def ingest_observation_with_embedding(self, text, thesis_ref, sentiment, categories):
            class R:
                observation_id = 123
            return R()

    monkeypatch.setattr(
        "src.slice.session.orchestrator.IngestionPipeline",
        lambda: DummyIngest(),
    )

    # Patch memory wrapper
    monkeypatch.setattr(
        "src.slice.session.orchestrator.get_memory_context_for_text",
        lambda text, k: {"items": []},
    )

    # Patch risk to return None (no snapshot)
    monkeypatch.setattr(
        "src.slice.session.orchestrator.get_snapshot",
        lambda thesis_id=None, portfolio_id=None: None,
    )

    # Patch logger to be a no-op (even if our stub changed later)
    monkeypatch.setattr(
        "src.slice.session.orchestrator.log_session_event",
        lambda *args, **kwargs: None,
    )

    orch = SessionOrchestrator(llm_client=DummyLLM())
    opts = SessionOptions()

    # Run the coroutine
    resp = asyncio.run(orch.run_session("hello", opts))

    assert resp.observation_id == 123
    assert resp.llm_response == "ok"
    assert resp.memory_context == {"items": []}
    assert resp.risk_snapshot is None
    assert resp.total_tokens == 15