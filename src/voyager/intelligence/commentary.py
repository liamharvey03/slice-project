import json
from typing import Any, Optional

from voyager.session.models import SessionResponse


class CommentaryEngine:
    """
    Phase 6: Daily / Weekly commentary generator.

    Responsibilities:
      - Use a provided context_builder (duck-typed, typically ContextBuilder)
        to assemble a deterministic context dict.
      - Construct a clear instruction string for the LLM.
      - Call the orchestrator (duck-typed, typically OrchestratorClient)
        in CONCISE mode to keep outputs short and readable.
    """

    def __init__(self, context_builder: Any, orchestrator: Any) -> None:
        # context_builder must provide: build_daily_context()
        self._context_builder = context_builder
        # orchestrator must provide: run_concise(user_text, include_memory=..., include_risk=...)
        self._orchestrator = orchestrator

    async def generate_daily(
        self,
        *,
        include_memory: bool = False,
        include_risk: bool = True,
        extra_instructions: Optional[str] = None,
    ) -> SessionResponse:
        """
        Generate a daily commentary note based on recent observations + risk snapshot.
        """

        context = self._context_builder.build_daily_context()
        context_json = json.dumps(context, default=str)

        parts = [
            "Phase 6 – Daily Commentary",
            "",
            "You are Voyager's internal daily commentary writer.",
            "",
            "You are given a JSON payload named 'context' that contains:",
            "- recent observations (notes, trades, or market thoughts)",
            "- a risk snapshot if available",
            "",
            "Task:",
            "1) Produce a concise daily note that summarizes what changed, what matters,",
            "   and how the current positioning / risk should be interpreted.",
            "2) Avoid making new trades; focus on interpretation and narrative.",
            "3) Keep it short and readable (1–3 short paragraphs).",
        ]

        if extra_instructions:
            parts.append("")
            parts.append("Additional instructions from the user:")
            parts.append(extra_instructions)

        parts.append("")
        parts.append("context:")
        parts.append(context_json)

        user_text = "\n".join(parts)

        resp: SessionResponse = await self._orchestrator.run_concise(
            user_text,
            include_memory=include_memory,
            include_risk=include_risk,
        )
        return resp

    async def generate_weekly(
        self,
        *,
        week_label: Optional[str] = None,
        include_memory: bool = False,
        include_risk: bool = True,
        extra_instructions: Optional[str] = None,
    ) -> SessionResponse:
        """
        Generate a weekly commentary note.

        For now, this reuses the same daily context (recent observations + risk)
        and relies on the instructions + optional week_label to communicate scope.
        """

        context = self._context_builder.build_daily_context()
        context_json = json.dumps(context, default=str)

        parts = [
            "Phase 6 – Weekly Commentary",
            "",
            "You are Voyager's internal weekly commentary writer.",
        ]

        if week_label:
            parts.append("")
            parts.append(f"Week label: {week_label}")

        parts.extend(
            [
                "",
                "You are given a JSON payload named 'context' that contains:",
                "- recent observations (notes, trades, or market thoughts)",
                "- a risk snapshot if available",
                "",
                "Task:",
                "1) Produce a concise weekly wrap that highlights the main themes,",
                "   key risks, and any major changes from earlier in the period.",
                "2) Connect observations into a coherent story.",
                "3) Keep it compact (2–4 short paragraphs).",
            ]
        )

        if extra_instructions:
            parts.append("")
            parts.append("Additional instructions from the user:")
            parts.append(extra_instructions)

        parts.append("")
        parts.append("context:")
        parts.append(context_json)

        user_text = "\n".join(parts)

        resp: SessionResponse = await self._orchestrator.run_concise(
            user_text,
            include_memory=include_memory,
            include_risk=include_risk,
        )
        return resp