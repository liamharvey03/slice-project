from typing import Any

from .models import SessionOptions, SessionResponse


class SessionOrchestrator:
    """
    Phase 5 orchestrator.

    Wires together:
      - observation ingestion
      - memory wrapper (Dev B)
      - risk snapshot (Dev A)
      - prompt builder
      - LLM client
      - logging
    """

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client

    async def run_session(self, text: str, options: SessionOptions) -> SessionResponse:
        """
        Full flow is specified in docs/phase5/phase5_interfaces.md.

        This stub exists to:
          - lock public signature
          - provide a stable import target for Dev B tests/docs
        """
        raise NotImplementedError("SessionOrchestrator.run_session not implemented yet")