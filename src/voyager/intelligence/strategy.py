import json

from voyager.intelligence.context.context_builder import ContextBuilder
from voyager.intelligence.context.data_access import DataAccess


async def run_strategy_recommendation(
    data_access: DataAccess,
    orchestrator,
    include_memory: bool = True,
    include_risk: bool = True,
    extra_instructions: str | None = None,
):
    """
    Phase 7-style strategy engine:

    - Loads all theses and an optional risk snapshot via DataAccess.
    - Uses stubbed empty current_portfolio and macro_view/constraints.
    - Builds a 'strategy_context' object via ContextBuilder.
    - Serializes it as JSON after a 'context:\\n' prefix.
    - Embeds extra_instructions as a JSON field when provided.
    """
    theses = data_access.get_all_theses()
    risk = data_access.get_risk_snapshot()
    cb = ContextBuilder(data_access)

    active_theses = [t.dict() for t in theses]
    current_portfolio: dict = {}
    risk_profile = risk.dict() if risk else {}
    constraints: dict = {}
    macro_view: dict = {}

    ctx = cb.build_strategy_context(
        active_theses=active_theses,
        current_portfolio=current_portfolio,
        risk_profile=risk_profile,
        constraints=constraints,
        macro_view=macro_view,
    )

    if extra_instructions is not None:
        ctx["extra_instructions"] = extra_instructions

    user_text = "context:\n" + json.dumps(ctx)

    return await orchestrator.run_analyst(
        user_text=user_text,
        include_memory=include_memory,
        include_risk=include_risk,
    )
