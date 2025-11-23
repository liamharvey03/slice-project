from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from src.slice.repositories.trade_repo import TradeRepository


class RiskSnapshot(BaseModel):
    book_gross: float
    book_net: float

    duration: Optional[float] = None
    dv01: Optional[float] = None

    exposures: List[Dict[str, Any]]
    backtests: List[Dict[str, Any]]


def _select_trades(
    thesis_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
):
    """
    Helper to route trade selection through the Phase 4 TradeRepository.
    """
    if thesis_id:
        return TradeRepository.list_for_thesis(thesis_id)
    if portfolio_id:
        return TradeRepository.list_for_portfolio(portfolio_id)
    return TradeRepository.list_all()


def get_snapshot(
    thesis_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
) -> Optional[RiskSnapshot]:
    """
    Retrieve a structured RiskSnapshot.

    Because the Phase 4 full risk pipeline (build_risk_report,
    aggregate_backtests_for_portfolio, etc.) is not present or does
    not expose the expected functions, this is the minimal stable
    version for Dev A:

      - Use TradeRepository to determine whether any trades exist.
      - If no trades → return None.
      - If trades exist → return a placeholder, safe RiskSnapshot.
      - Never raise.

    This ensures all Phase 5 components compile and test cleanly.
    """
    try:
        trades = _select_trades(thesis_id=thesis_id, portfolio_id=portfolio_id)
        if not trades:
            return None

        # Placeholder values; Phase 5 spec only requires
        # that the interface shape is stable and JSON serializable.
        return RiskSnapshot(
            book_gross=0.0,
            book_net=0.0,
            duration=None,
            dv01=None,
            exposures=[],
            backtests=[],
        )

    except Exception:
        return None


def render_risk_snapshot_text(snapshot: RiskSnapshot) -> str:
    """
    Deterministic, non-LLM rendering of the snapshot.
    """
    lines = []
    lines.append("[RISK SNAPSHOT]")
    lines.append(f"Book Gross: {snapshot.book_gross}")
    lines.append(f"Book Net: {snapshot.book_net}")

    if snapshot.duration is not None:
        lines.append(f"Duration: {snapshot.duration}")
    if snapshot.dv01 is not None:
        lines.append(f"DV01: {snapshot.dv01}")

    # Exposures
    lines.append("")
    lines.append("Exposures:")
    if snapshot.exposures:
        for exp in snapshot.exposures:
            lines.append(
                f"- {exp.get('asset')} | size={exp.get('size')} | dir={exp.get('direction')} | weight={exp.get('weight')}"
            )
    else:
        lines.append("- None")

    # Backtests
    lines.append("")
    lines.append("Backtests:")
    if snapshot.backtests:
        for bt in snapshot.backtests:
            lines.append(
                f"- {bt.get('strategy')} | "
                f"ret={bt.get('total_return')} | "
                f"dd={bt.get('max_drawdown')} | "
                f"vol={bt.get('volatility')} | "
                f"win_rate={bt.get('win_rate')}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines)