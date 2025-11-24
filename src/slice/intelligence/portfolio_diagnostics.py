import json
from typing import Optional

from slice.intelligence.context.context_builder import ContextBuilder
from slice.intelligence.context.data_access import DataAccess
from slice.intelligence.orchestrator_client import OrchestratorClient
from slice.session.models import SessionResponse


async def run_portfolio_diagnostics(
    *,
    data_access: DataAccess,
    orchestrator: OrchestratorClient,
    include_memory: bool = False,
    include_risk: bool = True,
    extra_instructions: Optional[str] = None,
) -> SessionResponse:
    risk_profile = data_access.get_risk_snapshot()
    current_portfolio = {}  # stub; real holdings wiring deferred to Phase 8

    builder = ContextBuilder(data_access=data_access)
    context = builder.build_portfolio_diagnostics_context(
        current_portfolio=current_portfolio,
        risk_profile=risk_profile,
    )

    context_json = json.dumps(context, default=str)

    text_parts = [
        "Phase 7 – Portfolio Diagnostics.",
        "",
        "You are analyzing the portfolio's risk and exposure profile.",
        "Use the context JSON to:",
        "- summarize key risk concentrations;",
        "- highlight drawdown or tail risks;",
        "- identify diversification or correlation issues.",
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
