import json
from typing import Optional

from slice.intelligence.context.context_builder import ContextBuilder
from slice.intelligence.context.data_access import DataAccess
from slice.intelligence.orchestrator_client import OrchestratorClient
from slice.session.models import SessionResponse


async def run_long_horizon_analysis(
    thesis_id: int,
    horizon_months: int,
    *,
    data_access: DataAccess,
    orchestrator: OrchestratorClient,
    include_memory: bool = True,
    include_risk: bool = False,
    extra_instructions: Optional[str] = None,
) -> SessionResponse:
    thesis = data_access.get_thesis(thesis_id)
    if thesis is None:
        raise ValueError("thesis_not_found")

    macro_view = data_access.get_risk_snapshot()

    builder = ContextBuilder(data_access=data_access)
    context = builder.build_long_horizon_context(
        primary_thesis=thesis,
        macro_view=macro_view,
        horizon_months=horizon_months,
    )

    context_json = json.dumps(context, default=str)

    text_parts = [
        "Phase 7 – Long-Horizon Reasoning",
        "",
        "You are evaluating a thesis over a multi-month horizon.",
        f"Horizon (months): {horizon_months}",
        "",
        "Use the JSON payload under 'context' to reason about:",
        "- macro path and regimes;",
        "- thesis robustness over the horizon;",
        "- key risks and scenario paths.",
        "",
        "context:",
        context_json,
    ]

    if extra_instructions:
        text_parts.append("")
        text_parts.append("Additional user instructions:")
        text_parts.append(extra_instructions)

    user_text = "\n".join(text_parts)

    response: SessionResponse = await orchestrator.run_analyst(
        user_text,
        include_memory=include_memory,
        include_risk=include_risk,
    )
    return response
