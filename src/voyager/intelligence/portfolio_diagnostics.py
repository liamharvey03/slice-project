import json

from voyager.intelligence.context.context_builder import ContextBuilder
from voyager.intelligence.context.data_access import DataAccess


async def run_portfolio_diagnostics(
    data_access: DataAccess,
    orchestrator,
    include_memory: bool = False,
    include_risk: bool = True,
    extra_instructions: str | None = None,
):
    """
    Phase 7-style portfolio diagnostics engine:

    - Uses stubbed empty current_portfolio, factor_exposures, stress_tests,
      and recent_performance.
    - Optionally includes a risk snapshot from DataAccess.
    - Builds 'portfolio_diagnostics_context' via ContextBuilder.
    - Serializes it as JSON after 'context:\\n'.
    - Embeds extra_instructions as a JSON field when provided.
    """
    risk = data_access.get_risk_snapshot()
    cb = ContextBuilder(data_access)

    current_portfolio: dict = {}
    risk_profile = risk.dict() if risk else {}
    factor_exposures: dict = {}
    stress_tests: list = []
    recent_performance: dict = {}

    ctx = cb.build_portfolio_diagnostics_context(
        current_portfolio=current_portfolio,
        risk_profile=risk_profile,
        factor_exposures=factor_exposures,
        stress_tests=stress_tests,
        recent_performance=recent_performance,
    )

    if extra_instructions is not None:
        ctx["extra_instructions"] = extra_instructions

    user_text = "context:\n" + json.dumps(ctx)

    return await orchestrator.run_analyst(
        user_text=user_text,
        include_memory=include_memory,
        include_risk=include_risk,
    )
