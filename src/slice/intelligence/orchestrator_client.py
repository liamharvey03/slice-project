from typing import Protocol
from slice.session.models import SessionOptions, SessionMode, SessionResponse
from slice.session.orchestrator import SessionOrchestrator


class LLMClientProtocol(Protocol):
    """
    Minimal protocol for the LLM client used by SessionOrchestrator.
    The orchestrator expects .chat(messages=[...]) -> dict.
    """

    async def chat(self, messages: list[dict]) -> dict:
        ...


class OrchestratorClient:
    """
    Phase-6 wrapper around the Phase-5 async SessionOrchestrator.

    This class provides a clean, stable interface for all Phase-6 intelligence
    modules to invoke the Phase-5 session pipeline:

        ingest → memory → risk → prompt → LLM → logging → response

    WITHOUT:
      - modifying SessionOptions,
      - touching prompt logic,
      - altering orchestrator behavior,
      - creating architectural drift.

    Phase-6 code MUST call this wrapper instead of SessionOrchestrator directly.
    """

    def __init__(self, llm_client: LLMClientProtocol) -> None:
        # Phase 5 orchestrator is created with injected LLM client
        self._orchestrator = SessionOrchestrator(llm_client=llm_client)

    async def run_session(
        self,
        *,
        user_text: str,
        mode: SessionMode,
        include_memory: bool = True,
        include_risk: bool = False,
    ) -> SessionResponse:
        """
        Core Phase-6 entrypoint.

        user_text is passed directly into the orchestrator’s ingest path.
        SessionOptions controls memory/risk behavior ONLY.
        """

        options = SessionOptions(
            mode=mode,
            use_memory=include_memory,
            use_risk=include_risk,
        )

        # Run the FULL async Phase-5 flow
        response: SessionResponse = await self._orchestrator.run_session(
            text=user_text,
            options=options,
        )
        return response

    async def run_standard(
        self,
        user_text: str,
        *,
        include_memory: bool = True,
        include_risk: bool = False,
    ) -> SessionResponse:
        return await self.run_session(
            user_text=user_text,
            mode=SessionMode.STANDARD,
            include_memory=include_memory,
            include_risk=include_risk,
        )

    async def run_analyst(
        self,
        user_text: str,
        *,
        include_memory: bool = True,
        include_risk: bool = True,
    ) -> SessionResponse:
        return await self.run_session(
            user_text=user_text,
            mode=SessionMode.ANALYST,
            include_memory=include_memory,
            include_risk=include_risk,
        )

    async def run_concise(
        self,
        user_text: str,
        *,
        include_memory: bool = True,
        include_risk: bool = True,
    ) -> SessionResponse:
        return await self.run_session(
            user_text=user_text,
            mode=SessionMode.CONCISE,
            include_memory=include_memory,
            include_risk=include_risk,
        )