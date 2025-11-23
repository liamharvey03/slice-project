from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from src.slice.repositories.trade_repo import TradeRepository
from src.slice.risk.report import build_risk_report
from src.slice.risk.aggregator import aggregate_backtests_for_portfolio
from src.slice.risk.schemas import BacktestResult, RiskReport


class RiskSnapshot(BaseModel):
    book_gross: float
    book_net: float

    duration: Optional[float] = None
    dv01: Optional[float] = None

    exposures: List[Dict[str, Any]]
    backtests: List[Dict[str, Any]]


def get_snapshot(
    thesis_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
) -> Optional[RiskSnapshot]:
    """
    Retrieve a structured, quantitative RiskSnapshot.

    Must:
      - Use TradeRepository for trade selection
      - Use Phase 4 risk data: RiskReport, BacktestResult
      - Return None on empty or invalid inputs
      - Never raise
    """
    try:
        # 1. Select trades
        if thesis_id:
            trades = TradeRepository.list_for_thesis(thesis_id)
        elif portfolio_id:
            trades = TradeRepository.list_for_portfolio(portfolio_id)
        else:
            trades = TradeRepository.list_all()

        if not trades:
            return None

        # 2. Compute base risk report (Phase 4)
        risk_report: RiskReport = build_risk_report(trades)
        if risk_report is None:
            return None

        # 3. Compute backtests (Phase 4)
        backtests: List[BacktestResult] = aggregate_backtests_for_portfolio(trades)

        # 4. Convert exposures into simple dicts for LLM
        exposures: List[Dict[str, Any]] = []
        for exp in risk_report.exposures:
            exposures.append({
                "asset": exp.asset,
                "size": exp.size,
                "direction": exp.direction,
                "weight": exp.weight,
            })

        # 5. Convert backtests into serializable dicts
        backtest_dicts: List[Dict[str, Any]] = []
        for bt in backtests:
            backtest_dicts.append({
                "strategy": bt.strategy,
                "total_return": bt.total_return,
                "max_drawdown": bt.max_drawdown,
                "volatility": bt.volatility,
                "win_rate": bt.win_rate,
            })

        return RiskSnapshot(
            book_gross=risk_report.book_gross,
            book_net=risk_report.book_net,
            duration=risk_report.duration,
            dv01=risk_report.dv01,
            exposures=exposures,
            backtests=backtest_dicts,
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
    lines.append("\nExposures:")
    if snapshot.exposures:
        for exp in snapshot.exposures:
            lines.append(
                f"- {exp['asset']} | size={exp['size']} | dir={exp['direction']} | weight={exp['weight']}"
            )
    else:
        lines.append("- None")

    # Backtests
    lines.append("\nBacktests:")
    if snapshot.backtests:
        for bt in snapshot.backtests:
            lines.append(
                f"- {bt['strategy']} | "
                f"ret={bt['total_return']} | "
                f"dd={bt['max_drawdown']} | "
                f"vol={bt['volatility']} | "
                f"win_rate={bt['win_rate']}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines)