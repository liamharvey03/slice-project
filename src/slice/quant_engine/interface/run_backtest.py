# src/slice/quant_engine/interface/run_backtest.py

from __future__ import annotations
from datetime import datetime

import json
from typing import Any, Dict, List, Optional, Type

import backtrader as bt
import pandas as pd

from slice.quant_engine.core.cerebro import run_cerebro
from slice.quant_engine.data.loader import load_price_data
from slice.quant_engine.strategies.gold_real_yields import GoldRealYieldsStrategy
from slice.quant_engine.strategies.usd_divergence import USDDivergenceStrategy
from slice.quant_engine.strategies.curve_steepener import CurveSteepenerStrategy
from slice.quant_engine.strategies.strategy_base import StrategyBase
from slice.risk.schemas import TimeSeriesPoint, StrategyReturnSeries, BacktestResult

# ---------- 1. Registry + placeholder strategy ----------

class BuyAndHoldFirstSymbol(StrategyBase):
    """
    Placeholder strategy for testing:
    - 100% long the first configured symbol at all times.
    """

    def compute_target_weights(self) -> Dict[str, float]:
        symbols = self.p.symbols
        if not symbols:
            raise RuntimeError("BuyAndHoldFirstSymbol: no symbols configured")
        first = symbols[0]
        return {first: 1.0}


_STRATEGY_REGISTRY: Dict[str, Type[StrategyBase]] = {
    "BUY_AND_HOLD_FIRST": BuyAndHoldFirstSymbol,
    "GOLD_REAL_YIELDS": GoldRealYieldsStrategy,
    "USD_DIVERGENCE": USDDivergenceStrategy,
    "CURVE_STEEPNER": CurveSteepenerStrategy,
}


def _resolve_strategy(strategy_id: str) -> Type[StrategyBase]:
    """
    Map strategy_id → StrategyBase subclass.
    """
    try:
        return _STRATEGY_REGISTRY[strategy_id]
    except KeyError as exc:
        raise ValueError(
            f"Unknown strategy_id '{strategy_id}'. "
            f"Registered strategies: {sorted(_STRATEGY_REGISTRY.keys())}"
        ) from exc


# ---------- 2. Stub for run_backtest (we'll fill this next) ----------

def run_backtest(strategy_id: str, params: Optional[Dict[str, Any]] = None) -> BacktestResult:
    """
    Phase 3 backtest interface.

    Parameters
    ----------
    strategy_id : str
        Identifier for the strategy, resolved via _STRATEGY_REGISTRY.
    params : dict
        Expected keys:
          - "tickers": List[str] (required)
          - "start":  str/date-like, optional
          - "end":    str/date-like, optional
          - "cash": float, optional (default 100_000.0)
          - "commission": float, optional (default 0.0)
          - additional keys are preserved in the output but ignored by this layer

    Returns
    -------
    BacktestResultJSON : dict
        {
          "strategy_id": str,
          "params": dict,
          "tickers": List[str],
          "period": {"start": str | None, "end": str | None},
          "metrics": {
              "total_return": float | None,
              "sharpe": float | None,
              "max_drawdown": float | None,
              "max_drawdown_len": int | None,
          },
          "returns": [
              {"date": "YYYY-MM-DD", "return": float},
              ...
          ],
          "orders": [
              {
                  "datetime": str,
                  "symbol": str,
                  "size": float,
                  "price": float,
                  "value": float,
                  "commission": float,
                  "order_ref": int,
                  "direction": "buy" | "sell",
                  "status": "completed" | "partial",
              },
              ...
          ],
          "trades": [
              {
                  "symbol": str,
                  "dt_open": str,
                  "dt_close": str,
                  "size": float,
                  "price_open": float,
                  "price_close": float,
                  "pnl": float,
                  "pnl_commission": float,
              },
              ...
          ],
        }
    """
    params = params or {}

    # --- required param: tickers ---
    tickers = params.get("tickers")
    if not tickers or not isinstance(tickers, (list, tuple)):
        raise ValueError("params['tickers'] must be a non-empty list of ticker strings.")

    # --- optional params ---
    start = params.get("start")
    end = params.get("end")
    cash = float(params.get("cash", 100_000.0))
    commission = float(params.get("commission", 0.0))

    # --- resolve strategy ---
    strategy_cls = _resolve_strategy(strategy_id)

    # --- load price data ---
    price_data: Dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        df = load_price_data(ticker, start=start, end=end)
        if df.empty:
            raise ValueError(f"No price data found for ticker '{ticker}'.")
        price_data[ticker] = df

    # --- run backtest ---
    strat, analyzers = run_cerebro(
        strategy_cls=strategy_cls,
        price_data=price_data,
        cash=cash,
        commission=commission,
    )

    # ===================== Returns series =====================
    returns_analysis = analyzers["returns"].get_analysis()  # OrderedDict-like
    returns_series: List[Dict[str, Any]] = []

    for key, value in returns_analysis.items():
        # key is usually datetime; fall back if not
        if hasattr(key, "isoformat"):
            date_str = key.isoformat()
        else:
            # Analyzer keys can be numeric bt dates; handle that
            try:
                date_str = bt.num2date(key).isoformat()
            except Exception:
                date_str = str(key)

        returns_series.append({"date": date_str, "return": float(value)})

    returns_points: List[TimeSeriesPoint] = [
        TimeSeriesPoint(
            date=datetime.fromisoformat(entry["date"]).date(),
            value=float(entry["return"]),
        )
        for entry in returns_series
    ]

    strategy_series = StrategyReturnSeries(
        strategy_id=strategy_id,
        frequency="D",
        returns=returns_points,
    )

    if returns_points:
        start_date = returns_points[0].date
        end_date = returns_points[-1].date
        backtest_id = f"{strategy_id}_{start_date}_{end_date}"
    else:
        backtest_id = f"{strategy_id}_EMPTY"

    backtest = BacktestResult(
        backtest_id=backtest_id,
        frequency="D",
        strategies=[strategy_series],
    )

    # ===================== Metrics =====================
    sharpe_raw = analyzers["sharpe"].get_analysis().get("sharperatio", None)

    dd_analysis = analyzers["drawdown"].get_analysis()
    try:
        max_dd = float(dd_analysis.max.drawdown)
        max_dd_len = int(dd_analysis.max.len)
    except Exception:
        max_dd = None
        max_dd_len = None

    # total return from daily returns
    try:
        series = pd.Series([x["return"] for x in returns_series], dtype=float)
        total_return = float((1.0 + series).prod() - 1.0)
    except Exception:
        total_return = None

    metrics = {
        "total_return": total_return,
        "sharpe": float(sharpe_raw) if sharpe_raw is not None else None,
        "max_drawdown": max_dd,
        "max_drawdown_len": max_dd_len,
    }

    # ===================== Orders & trades =====================
    orders: List[Dict[str, Any]] = []
    for o in getattr(strat, "order_log", []):
        rec = dict(o)
        dt = rec.get("datetime")
        if dt is not None and hasattr(dt, "isoformat"):
            rec["datetime"] = dt.isoformat()
        orders.append(rec)

    trades: List[Dict[str, Any]] = []
    for tr in getattr(strat, "trade_log", []):
        rec = dict(tr)
        for field in ("dt_open", "dt_close"):
            dt = rec.get(field)
            if dt is not None and hasattr(dt, "isoformat"):
                rec[field] = dt.isoformat()
        trades.append(rec)

    # ===================== Period summary =====================
    if returns_series:
        period_start = returns_series[0]["date"]
        period_end = returns_series[-1]["date"]
    else:
        period_start = None
        period_end = None

    result: Dict[str, Any] = {
        "strategy_id": strategy_id,
        "params": params,
        "tickers": list(tickers),
        "period": {"start": period_start, "end": period_end},
        "metrics": metrics,
        "returns": returns_series,
        "orders": orders,
        "trades": trades,
    }

    return backtest
