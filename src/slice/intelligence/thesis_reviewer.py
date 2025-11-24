import json
from typing import Optional

from slice.intelligence.context.context_builder import ContextBuilder
from slice.intelligence.orchestrator_client import OrchestratorClient
from slice.session.models import SessionResponse


class ThesisReviewer:
    """
    Phase-6: higher-level thesis review module.

    Responsibilities:
      - Pull structured context for a single thesis via ContextBuilder.
      - Wrap that context into a single user_text instruction.
      - Invoke the Phase-5 session pipeline via OrchestratorClient (ANALYST mode).
      - Return the SessionResponse unchanged.
    """

    def __init__(
        self,
        context_builder: ContextBuilder,
        orchestrator: OrchestratorClient,
    ) -> None:
        self._context_builder = context_builder
        self._orchestrator = orchestrator

    async def review_thesis(
        self,
        thesis_id: int,
        *,
        include_memory: bool = True,
        include_risk: bool = True,
        extra_instructions: Optional[str] = None,
    ) -> SessionResponse:
        """
        Build context for the specified thesis and run an ANALYST-mode session.

        Raises:
            ValueError: if the thesis does not exist (ContextBuilder returns an error).
        """

        context = self._context_builder.build_thesis_context(thesis_id)
        if "error" in context:
            # Keep this simple and explicit for now; API layer can catch/translate.
            raise ValueError(f"Thesis {thesis_id} not found")

        context_json = json.dumps(context, default=str)

        # This string is what ultimately flows into Phase-5's prompt builder.
        # We keep it deterministic and self-describing so tests can assert on it.
        user_text_parts = [
            "Phase 6 – Thesis Review Request",
            "",
            "You are Slice's internal thesis reviewer.",
            "",
            "You are given a JSON payload named 'context' that contains:",
            "- the primary thesis definition",
            "- its linked observations",
            "- an optional risk snapshot",
            "",
            "Task:",
            "1) Assess whether the thesis is internally coherent and aligned with its observations.",
            "2) Identify any contradictions, missing links, or unclear assumptions.",
            "3) Suggest concrete improvements to the thesis framing and observation coverage.",
            "",
            "You are not executing trades; you are critiquing the intellectual structure.",
        ]

        if extra_instructions:
            user_text_parts.append("")
            user_text_parts.append("Additional instructions from the user:")
            user_text_parts.append(extra_instructions)

        user_text_parts.append("")
        user_text_parts.append("context:")
        user_text_parts.append(context_json)

        user_text = "\n".join(user_text_parts)

        response = await self._orchestrator.run_analyst(
            user_text,
            include_memory=include_memory,
            include_risk=include_risk,
        )
        return response