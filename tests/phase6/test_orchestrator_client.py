import pytest

from voyager.intelligence.orchestrator_client import OrchestratorClient
from voyager.session.models import SessionMode, SessionOptions


class DummyLLMClient:
    async def chat(self, messages):
        return {"content": "dummy", "usage": {}}


class DummySessionOrchestrator:
    """
    Matches the REAL orchestrator signature:

        async def run_session(self, text: str, options: SessionOptions)
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.last_text = None
        self.last_options = None

    async def run_session(self, text: str, options: SessionOptions):
        self.last_text = text
        self.last_options = options
        return {"ok": True, "mode": str(options.mode)}


@pytest.fixture(autouse=True)
def patch_session_orchestrator(monkeypatch):
    """
    Patch SessionOrchestrator inside the intelligence wrapper
    so we can inspect the SessionOptions created by OrchestratorClient.
    """
    import voyager.intelligence.orchestrator_client as oc_mod

    monkeypatch.setattr(oc_mod, "SessionOrchestrator", DummySessionOrchestrator)
    yield


@pytest.mark.asyncio
async def test_run_standard_sets_mode_and_flags_correctly():
    client = OrchestratorClient(llm_client=DummyLLMClient())

    resp = await client.run_standard("hello world", include_memory=True, include_risk=False)
    assert resp == {"ok": True, "mode": str(SessionMode.STANDARD)}

    orchestrator = client._orchestrator
    opts = orchestrator.last_options
    assert orchestrator.last_text == "hello world"
    assert opts.mode == SessionMode.STANDARD
    assert opts.use_memory is True
    assert opts.use_risk is False


@pytest.mark.asyncio
async def test_run_analyst_enables_risk_by_default():
    client = OrchestratorClient(llm_client=DummyLLMClient())

    await client.run_analyst("check this thesis")

    orchestrator = client._orchestrator
    opts = orchestrator.last_options
    assert orchestrator.last_text == "check this thesis"
    assert opts.mode == SessionMode.ANALYST
    assert opts.use_memory is True
    assert opts.use_risk is True


@pytest.mark.asyncio
async def test_run_concise_uses_concise_mode():
    client = OrchestratorClient(llm_client=DummyLLMClient())

    await client.run_concise("summarize")

    orchestrator = client._orchestrator
    opts = orchestrator.last_options
    assert orchestrator.last_text == "summarize"
    assert opts.mode == SessionMode.CONCISE