from __future__ import annotations

from typing import Any, Dict, Optional

from slice.quant_engine.interface.run_backtest import run_backtest
from slice.risk.aggregator import aggregate_from_backtest
from slice.risk.report import build_risk_report
from slice.risk.schemas import BacktestResult, PortfolioReturnSeries, RiskReport

def run_backtest_with_risk(
    strategy_id: str,
    params: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
    portfolio_id: Optional[str] = None,
    factor_data=None,
    scenarios=None,
    macro=None,
) -> RiskReport:
    """
    Phase 3 orchestration entrypoint.

    1. Calls Dev A's run_backtest(...) → BacktestResult
    2. Aggregates into a PortfolioReturnSeries via aggregate_from_backtest(...)
    3. Builds a RiskReport via build_risk_report(...)
    """
    params = params or {}

    # Default: single-strategy portfolio, full weight on this strategy
    if weights is None:
        weights = {strategy_id: 1.0}

    # Default portfolio_id if not provided
    if portfolio_id is None:
        portfolio_id = f"PORT_{strategy_id}"

    # 1) Dev A – backtest
    backtest: BacktestResult = run_backtest(strategy_id=strategy_id, params=params)

    # 2) Dev B – aggregate to portfolio series
    portfolio: PortfolioReturnSeries = aggregate_from_backtest(
        backtest=backtest,
        weights=weights,
        portfolio_id=portfolio_id,
    )

    # 3) Dev B – build risk report
    report: RiskReport = build_risk_report(
        portfolio=portfolio,
        asset_returns=None,   # can be wired later if needed
        weights=weights,
        factor_data=factor_data,
        scenarios=scenarios,
        macro=macro,
    )

    return report