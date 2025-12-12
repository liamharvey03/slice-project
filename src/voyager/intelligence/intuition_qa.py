import json
from typing import Any, Optional

from voyager.session.models import SessionResponse


class IntuitionQAEngine:
    """
    Phase 6: Intuition RAG-style Q&A.

    Responsibilities:
      - Take a user question.
      - Use a provided memory_service to recall relevant past observations.
      - Use a provided context_builder (e.g., ContextBuilder) to assemble a
        deterministic context dict.
      - Call an orchestrator (e.g., OrchestratorClient) in STANDARD mode.
    """

    def __init__(
        self,
        memory_service: Any,
        context_builder: Any,
        orchestrator: Any,
    ) -> None:
        # memory_service must implement: recall(question: str, k: int) -> list[dict]
        self._memory_service = memory_service
        # context_builder must implement: build_intuition_context(question, recalled_obs) -> dict
        self._context_builder = context_builder
        # orchestrator must implement: run_standard(user_text, include_memory=..., include_risk=...) -> SessionResponse
        self._orchestrator = orchestrator

    async def answer(
        self,
        question: str,
        *,
        k: int = 5,
        include_memory: bool = False,
        include_risk: bool = False,
        extra_instructions: Optional[str] = None,
    ) -> SessionResponse:
        """
        Answer a question using recalled observations as context.

        `include_memory` defaults to False because we already inject retrieved
        observations explicitly; turning it on allows Phase 5 memory to add more.
        """

        # 1) Recall from memory layer (Phase 4)
        recalled = self._memory_service.recall(question, k=k)

        # 2) Build deterministic context
        context = self._context_builder.build_intuition_context(
            question=question,
            recalled_obs=recalled,
        )
        context_json = json.dumps(context, default=str)

        # 3) Build user_text for the orchestrator
        parts = [
            "Phase 6 – Intuition Q&A",
            "",
            "You are Voyager's internal intuition explainer.",
            "",
            "You are given a JSON payload named 'context' that contains:",
            "- the user's current question",
            "- a list of recalled observations from prior sessions",
            "",
            "Task:",
            "1) Answer the question using only the information contained in the recalled observations,",
            "   plus obvious implications that follow directly from them.",
            "2) Explain your reasoning clearly and succinctly.",
            "3) If the context is insufficient to answer, say so explicitly.",
        ]

        if extra_instructions:
            parts.append("")
            parts.append("Additional instructions from the user:")
            parts.append(extra_instructions)

        parts.append("")
        parts.append("context:")
        parts.append(context_json)

        user_text = "\n".join(parts)

        # 4) Call orchestrator in STANDARD mode
        resp: SessionResponse = await self._orchestrator.run_standard(
            user_text,
            include_memory=include_memory,
            include_risk=include_risk,
        )
        return resp