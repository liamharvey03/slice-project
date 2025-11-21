#!/usr/bin/env python
"""
Phase 3 demo script.

Runs a backtest via Dev A, aggregates via Dev B, and prints a summary RiskReport.
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict

# Allow running from repo root: PYTHONPATH=src python scripts/run_phase3_demo.py ...
if "PYTHONPATH" not in os.environ:
    # best effort; user should still set PYTHONPATH=src explicitly in docs
    pass

from slice.engine.analytics_pipeline import run_backtest_with_risk
from slice.risk.schemas import RiskReport


def main() -> None:
    parser = argparse.ArgumentParser(description="Slice Phase 3 demo runner")
    parser.add_argument(
        "--strategy-id",
        type=str,
        default="BUY_AND_HOLD_FIRST",
        help="Strategy ID (e.g. BUY_AND_HOLD_FIRST, GOLD_REAL_YIELDS)",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        required=True,
        help="One or more tickers to include in the backtest (space-separated).",
    )
    args = parser.parse_args()

    params: Dict[str, Any] = {
        "tickers": args.tickers,
        # Optional:
        # "start": "2015-01-01",
        # "end": "2020-01-01",
    }

    print(f"Running Phase 3 demo for strategy_id={args.strategy_id}, tickers={args.tickers}...")

    report: RiskReport = run_backtest_with_risk(
        strategy_id=args.strategy_id,
        params=params,
    )

    # -------------------------------
    # Print Risk Metrics
    # -------------------------------
    rm = report.risk_metrics
    print("\n=== Risk Metrics ===")
    print(f"Total return:     {rm.total_return:.4f}" if rm.total_return is not None else "Total return: n/a")
    print(f"CAGR:             {rm.cagr:.4f}" if rm.cagr is not None else "CAGR: n/a")
    print(f"Ann. vol:         {rm.annualized_vol:.4f}" if rm.annualized_vol is not None else "Ann. vol: n/a")
    print(f"Sharpe:           {rm.sharpe:.4f}" if rm.sharpe is not None else "Sharpe: n/a")
    print(f"Max drawdown:     {rm.max_drawdown:.4f}" if rm.max_drawdown is not None else "Max drawdown: n/a")

    print("\n=== Risk Rails ===")
    print(report.risk_rails)

    # -------------------------------
    # Scenarios (schema-safe)
    # -------------------------------
    print("\n=== Scenarios ===")

    scenario_list = None
    if hasattr(report, "scenario_results"):
        scenario_list = getattr(report, "scenario_results")
    elif hasattr(report, "scenarios"):
        scenario_list = getattr(report, "scenarios")

    if scenario_list:
        for scen in scenario_list:
            name = getattr(scen, "name", "unnamed")
            pnl = getattr(scen, "portfolio_pnl_pct", None)
            if pnl is not None:
                print(f"- {name}: estimated P&L {pnl:.4f}")
            else:
                print(f"- {name}: (no P&L field)")
    else:
        print("No scenarios configured or scenario field not defined on RiskReport.")


if __name__ == "__main__":
    main()