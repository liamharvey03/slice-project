from typing import Any, Optional
import time

from src.slice.session.models import SessionOptions, SessionResponse
from src.slice.session.prompts import build_prompt
from src.slice.session.logging import log_session_event
from src.slice.memory.interface import get_memory_context_for_text
from src.slice.risk.interface import get_snapshot, render_risk_snapshot_text

from src.slice.ingest.pipeline import IngestionPipeline


class SessionOrchestrator:
    """
    Phase 5 orchestrator.

    Wires together:
      - Phase 4 observation ingestion
      - Dev B memory wrapper
      - Dev A risk snapshot
      - prompt builder
      - LLM client
      - non-raising logging
    """

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client
        self.ingest = IngestionPipeline()

    async def run_session(self, text: str, options: SessionOptions) -> SessionResponse:
        """
        Full flow per Phase 5 spec.
        """

        # ------------------------------------------------------------
        # 1. INGEST OBSERVATION
        # ------------------------------------------------------------
        try:
            ingest_result = self.ingest.ingest_observation_with_embedding(
                text=text,
                thesis_ref=None,   # Phase 5 UI doesn’t tie these yet
                sentiment=None,
                categories=None,
            )
            observation_id = ingest_result.observation_id
        except Exception:
            # If ingestion fails entirely, we cannot proceed.
            # This is the only place where failing hard is correct.
            raise RuntimeError("Observation ingestion failed")

        # ------------------------------------------------------------
        # 2. MEMORY (Dev B wrapper)
        # ------------------------------------------------------------
        if options.use_memory:
            memory_ctx = get_memory_context_for_text(
                text=text,
                k=options.max_memory_items,
            )
        else:
            memory_ctx = None

        # ------------------------------------------------------------
        # 3. RISK (Dev A)
        # ------------------------------------------------------------
        if options.use_risk:
            snapshot = get_snapshot(
                thesis_id=options.risk_for_thesis_id,
                portfolio_id=options.risk_for_portfolio_id,
            )
            risk_ctx = snapshot.dict() if snapshot else None
        else:
            risk_ctx = None

        # For prompt readability:
        if risk_ctx:
            risk_ctx["rendered"] = render_risk_snapshot_text(snapshot)

        # ------------------------------------------------------------
        # 4. PROMPT BUILDING
        # ------------------------------------------------------------
        messages = build_prompt(
            memory_ctx=memory_ctx,
            risk_ctx=risk_ctx,
            user_text=text,
            options=options,
        )

        # ------------------------------------------------------------
        # 5. LLM CALL
        # ------------------------------------------------------------
        start = time.time()
        llm_resp = await self.llm_client.chat(messages=messages)
        latency = int((time.time() - start) * 1000)

        llm_text = llm_resp.get("content", "")

        # Token accounting if provided
        usage = llm_resp.get("usage", {}) or {}

        # ------------------------------------------------------------
        # 6. LOGGING (non-blocking, never raises)
        # ------------------------------------------------------------
        try:
            log_session_event(
                observation_id=observation_id,
                llm_model=self.llm_client.model_name,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                latency_ms=latency,
                memory_used=options.use_memory,
                risk_used=options.use_risk,
            )
        except Exception:
            pass

        # ------------------------------------------------------------
        # 7. RETURN STRUCTURED RESPONSE
        # ------------------------------------------------------------
        return SessionResponse(
            observation_id=observation_id,
            llm_response=llm_text,
            memory_context=memory_ctx,
            risk_snapshot=risk_ctx,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=latency,
        )