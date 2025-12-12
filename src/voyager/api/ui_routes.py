from typing import Any, Dict

from fastapi import APIRouter

from voyager.intelligence.context.data_access import DataAccess
from voyager.intelligence.context.context_builder import ContextBuilder


router = APIRouter()


def get_data_access() -> DataAccess:
    """
    Get DataAccess instance using centrally wired dependency.
    
    Uses the shared DataAccess instance that includes E4 repositories,
    ensuring consistency across all routes.
    """
    # Use centrally wired DataAccess with E4 repos
    return DataAccess.depends()


@router.get("/health")
def health() -> Dict[str, str]:
    """
    Minimal UI health check for Phase 8.
    Does not touch DB, DataAccess, or orchestrator.
    """
    return {"status": "ok"}


@router.get("/portfolio")
def get_portfolio_view() -> Dict[str, Any]:
    """
    Deterministic portfolio view for the UI.

    - Uses DataAccess.get_current_portfolio()
    - Uses DataAccess.get_portfolio_depth() for concentration/factors/thesis map
    """
    da = get_data_access()
    portfolio = da.get_current_portfolio()
    theses = da.get_all_theses()
    depth = da.get_portfolio_depth(theses)

    return {
        "portfolio": portfolio,
        "depth": depth,
    }


@router.get("/strategy-context")
def get_strategy_context() -> Dict[str, Any]:
    """
    Phase 8 strategy context, built via ContextBuilder helper.
    No LLM calls here; this is pure data surface for UI.
    """
    da = get_data_access()
    cb = ContextBuilder(da)
    ctx = cb.build_strategy_context_from_data()
    return ctx


@router.get("/diagnostics-context")
def get_portfolio_diagnostics_context() -> Dict[str, Any]:
    """
    Phase 8 portfolio diagnostics context, built via ContextBuilder helper.
    Exposes risk profile + factor and thesis exposures for UI use.
    """
    da = get_data_access()
    cb = ContextBuilder(da)
    ctx = cb.build_portfolio_diagnostics_context_from_data()
    return ctx


@router.get("/narrative-context")
def get_narrative_context() -> Dict[str, Any]:
    """
    Phase 8 narrative coherence context, built via ContextBuilder helper.

    This surfaces:
      - theses[]
      - macro_view { risk_snapshot, macro_snapshot, regimes }
      - portfolio_snapshot
      - quant_summaries (currently stubbed)
    """
    da = get_data_access()
    cb = ContextBuilder(da)
    ctx = cb.build_narrative_coherence_context_from_data(window_label=None)
    return ctx
