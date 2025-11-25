import json

from slice.intelligence.context.context_builder import ContextBuilder
from slice.intelligence.context.data_access import DataAccess


async def run_narrative_coherence(
    data_access: DataAccess,
    orchestrator,
    window_label: str | None = None,
    include_memory: bool = True,
    include_risk: bool = True,
    extra_instructions: str | None = None,
):
    """
    Phase 7-style narrative coherence engine:

    - Loads all theses and optional risk snapshot via DataAccess.
    - Uses stubbed portfolio_snapshot and empty recent_observations/quant_summaries.
    - Adds a commentary_window label if provided.
    - Builds 'narrative_coherence_context' via ContextBuilder.
    - Serializes it as JSON after 'context:\\n'.
    - Embeds extra_instructions as a JSON field when provided.
    """
    theses = data_access.get_all_theses()
    risk = data_access.get_risk_snapshot()
    cb = ContextBuilder(data_access)

    theses_dicts = [t.dict() for t in theses]
    macro_view = {
        "risk_snapshot": risk.dict() if risk else None,
    }
    portfolio_snapshot: dict = {}
    recent_observations: list = []
    quant_summaries: dict = {}
    commentary_window = {"label": window_label} if window_label else {}

    ctx = cb.build_narrative_coherence_context(
        theses=theses_dicts,
        macro_view=macro_view,
        portfolio_snapshot=portfolio_snapshot,
        recent_observations=recent_observations,
        quant_summaries=quant_summaries,
        commentary_window=commentary_window,
    )

    if extra_instructions is not None:
        ctx["extra_instructions"] = extra_instructions

    user_text = "context:\n" + json.dumps(ctx)

    return await orchestrator.run_analyst(
        user_text=user_text,
        include_memory=include_memory,
        include_risk=include_risk,
    )
