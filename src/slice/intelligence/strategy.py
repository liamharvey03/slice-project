import json
from typing import Optional

from slice.intelligence.context.context_builder import ContextBuilder
from slice.intelligence.context.data_access import DataAccess
from slice.intelligence.orchestrator_client import OrchestratorClient
from slice.session.models import SessionResponse


async def run_strategy_recommendation(
    *,
    data_access: DataAccess,
    orchestrator: OrchestratorClient,
    include_memory: bool = True,
    include_risk: bool = True,
    extra_instructions: Optional[str] = None,
) -> SessionResponse:
    active_theses = data_access.get_all_theses()
    risk_profile = data_access.get_risk_snapshot()
    current_portfolio = {}  # stub; real portfolio wiring comes in Phase 8

    builder = ContextBuilder(data_access=data_access)
    context = builder.build_strategy_context(
        active_theses=active_theses,
        current_portfolio=current_portfolio,
        risk_profile=risk_profile,
    )

    context_json = json.dumps(context, default=str)

    text_parts = [
        "Phase 7 – Strategy Recommendation.",
        "",
        "You are a macro/portfolio strategy engine.",
        "Given the current theses, macro view, and portfolio context,",
        "produce high-level strategy recommendations:",
        "- desired tilts;",
        "- risk-on / risk-off posture;",
        "- key trades or themes.",
    ]

    if extra_instructions:
        text_parts.append("")
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
