from typing import List, Dict, Any, Optional

from pydantic import BaseModel


class RiskSnapshot(BaseModel):
    """
    High-level, LLM-facing risk representation for Phase 5.

    Concrete population logic lives in get_snapshot; this model is stable
    and must stay in sync with docs/phase5/phase5_interfaces.md.
    """

    # Top-level book metrics
    book_gross: float
    book_net: float

    duration: Optional[float] = None
    dv01: Optional[float] = None

    # Per-asset or per-trade exposures (structure kept flexible on purpose)
    exposures: List[Dict[str, Any]]

    # Related backtests or diagnostics
    backtests: List[Dict[str, Any]]


def get_snapshot(
    thesis_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
) -> Optional[RiskSnapshot]:
    """
    Retrieve a structured, quantitative RiskSnapshot.

    Rules (per Phase 5 spec):
      - If thesis_id is provided -> snapshot scoped to trades linked to that thesis.
      - If portfolio_id is provided -> snapshot scoped to that portfolio.
      - If neither is provided -> snapshot for the top-level book.

      - Must use existing Phase 4 repositories / risk reports.
      - Must return None (not raise) if:
          * there is no data
          * the risk system is disabled
          * an internal error occurs.

    This is a stub; implementation will be added in a later step.
    """
    raise NotImplementedError("risk.get_snapshot not implemented yet")


def render_risk_snapshot_text(snapshot: RiskSnapshot) -> str:
    """
    Deterministic, non-LLM rendering of the RiskSnapshot.

    Must produce a stable, fixed-order summary including:
      - Book gross/net
      - Duration/DV01 (if present)
      - Exposures
      - Backtest summaries

    This is a stub; implementation will be added in a later step.
    """
    raise NotImplementedError("render_risk_snapshot_text not implemented yet")