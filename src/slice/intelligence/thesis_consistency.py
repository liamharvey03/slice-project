import json
from typing import Any, Optional

from slice.session.models import SessionResponse


class ThesisConsistencyChecker:
    """
    Phase 6: Cross-thesis consistency review.

    Responsibilities:
      - Use a provided context_builder (duck-typed, e.g., ContextBuilder) to fetch
        a unified multi-thesis context.
      - Build a single ANALYST-mode request string.
      - Invoke the orchestrator (duck-typed, e.g., OrchestratorClient) and
        return the SessionResponse unchanged.
    """

    def __init__(
        self,
        context_builder: Any,
        orchestrator: Any,
    ) -> None:
        # context_builder must provide build_multi_thesis_context()
        self._context_builder = context_builder
        # orchestrator must provide run_analyst(user_text, include_memory=..., include_risk=...)
        self._orchestrator = orchestrator

    async def analyze(
        self,
        *,
        include_memory: bool = True,
        include_risk: bool = False,  # default off; cross-thesis risk is not central
        extra_instructions: Optional[str] = None,
    ) -> SessionResponse:
        """
        Perform a cross-thesis coherence analysis.
        """

        context = self._context_builder.build_multi_thesis_context()
        context_json = json.dumps(context, default=str)

        text_parts = [
            "Phase 6 – Cross-Thesis Consistency Review",
            "",
            "You are Slice's global consistency checker.",
            "",
            "You are given a JSON payload named 'context' holding ALL current theses.",
            "",
            "Task:",
            "1) Identify contradictions across theses (timing, causal assumptions, macro drivers).",
            "2) Identify overlaps that should be merged or clarified.",
            "3) Identify missing links: places where theses depend on unstated assumptions.",
            "4) Flag any theses that are logically impossible to hold simultaneously.",
            "",
            "Produce clear, structured reasoning.",
        ]

        if extra_instructions:
            text_parts.append("")
            text_parts.append("Additional user instructions:")
            text_parts.append(extra_instructions)

        text_parts.append("")
        text_parts.append("context:")
        text_parts.append(context_json)

        user_text = "\n".join(text_parts)

        resp: SessionResponse = await self._orchestrator.run_analyst(
            user_text,
            include_memory=include_memory,
            include_risk=include_risk,
        )
        return resp