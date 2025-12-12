import json

from voyager.intelligence.context.context_builder import ContextBuilder
from voyager.intelligence.context.data_access import DataAccess


async def run_long_horizon_analysis(
    thesis_id: int,
    horizon_months: int,
    data_access: DataAccess,
    orchestrator,
    include_memory: bool = True,
    include_risk: bool = True,
    extra_instructions: str | None = None,
):
    """
    Phase 7-style long-horizon engine (with optional extra_instructions).

    Contract points (enforced by tests):
    - Calls data_access.get_thesis(thesis_id) exactly once.
    - Calls data_access.get_risk_snapshot() exactly once.
    - Calls orchestrator.run_analyst(...) exactly once with:
        include_memory=True (default)
        include_risk=True   (default, important for tests)
    - Serializes a JSON object with kind="long_horizon_context" after the
      'context:\\n' prefix in user_text.
    - extra_instructions, if provided, must be embedded as a JSON field
      (not appended as separate plaintext after the JSON).
    """
    thesis = data_access.get_thesis(thesis_id)
    if thesis is None:
        return {"error": "thesis_not_found"}

    risk = data_access.get_risk_snapshot()
    cb = ContextBuilder(data_access)

    # Minimal macro_view, as in Phase 7: just risk_snapshot
    macro_view = {
        "risk_snapshot": risk.dict() if risk else None,
    }

    ctx = cb.build_long_horizon_context(
        primary_thesis=thesis.dict(),
        supporting_theses=[],
        macro_view=macro_view,
        scenarios=[],
        horizon_months=horizon_months,
    )

    if extra_instructions is not None:
        ctx["extra_instructions"] = extra_instructions

    user_text = "context:\n" + json.dumps(ctx)

    return await orchestrator.run_analyst(
        user_text=user_text,
        include_memory=include_memory,
        include_risk=include_risk,
    )
