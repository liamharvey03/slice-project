import json
from typing import Any, Dict, List, Optional

from slice.intelligence.context.context_builder import ContextBuilder
from slice.intelligence.context.data_access import DataAccess
from slice.intelligence.orchestrator_client import OrchestratorClient
from slice.session.models import SessionResponse


async def run_narrative_coherence(
    *,
    data_access: DataAccess,
    orchestrator: OrchestratorClient,
    window_label: Optional[str] = None,
    include_memory: bool = True,
    include_risk: bool = True,
    extra_instructions: Optional[str] = None,
) -> SessionResponse:
    theses = data_access.get_all_theses()
    risk_snapshot = data_access.get_risk_snapshot()

    theses_payload: List[Dict[str, Any]] = [t.dict() for t in theses]
    macro_view: Dict[str, Any] = {
        "risk_snapshot": risk_snapshot.dict() if risk_snapshot else None,
    }
    portfolio_snapshot: Dict[str, Any] = {}

    builder = ContextBuilder(data_access=data_access)
    context = builder.build_narrative_coherence_context(
        theses=theses_payload,
        macro_view=macro_view,
        portfolio_snapshot=portfolio_snapshot,
    )

    context_json = json.dumps(context, default=str)

    text_parts = [
        "Phase 7 – Narrative coherence.",
        "",
        "You are a macro narrative engine for the portfolio.",
        "Given the current theses, macro view, and portfolio snapshot:",
        "- Produce a coherent narrative tying these elements together.",
        "- Call out tensions, contradictions, and missing pieces.",
        "- Explain how the portfolio is positioned vs the macro backdrop.",
    ]

    if window_label:
        text_parts.append(f"Window label: {window_label}")

    if extra_instructions:
        text_parts.append("Additional user instructions:")
        text_parts.append(extra_instructions)

    text_parts.extend(
        [
            "",
            "context:",
            context_json,
        ]
    )

    user_text = "\n".join(text_parts)

    response: SessionResponse = await orchestrator.run_analyst(
        user_text,
        include_memory=include_memory,
        include_risk=include_risk,
    )
    return response
