# src/slice/quant_engine/core/cerebro.py

from __future__ import annotations

from typing import Dict, Type, List, Tuple

import backtrader as bt
import pandas as pd

from slice.quant_engine.data.feed import SlicePandasData
from slice.quant_engine.strategies.strategy_base import StrategyBase


def build_cerebro(
    strategy_cls: Type[StrategyBase],
    price_data: Dict[str, pd.DataFrame],
    cash: float = 100_000.0,
    commission: float = 0.0,
) -> bt.Cerebro:
    """
    Construct a Backtrader Cerebro engine with:
      - given StrategyBase subclass
      - dict of {symbol: price_dataframe}
      - basic broker configuration
      - standard analyzers (returns, sharpe, drawdown)

    Parameters
    ----------
    strategy_cls : subclass of StrategyBase
    price_data   : mapping of symbol -> pandas DataFrame (OHLCV, datetime index)
    cash         : initial cash
    commission   : per-trade commission fraction (0.001 = 10 bps)

    Returns
    -------
    bt.Cerebro
    """
    c = bt.Cerebro()

    # Broker setup
    c.broker.setcash(cash)
    c.broker.setcommission(commission=commission)

    # Add data feeds
    symbols: List[str] = []
    for symbol, df in price_data.items():
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"price_data[{symbol}] is not a DataFrame")

        # deterministic index order
        df = df.sort_index()

        data_feed = SlicePandasData(dataname=df)
        c.adddata(data_feed, name=symbol)
        symbols.append(symbol)

    # Add strategy
    c.addstrategy(strategy_cls, symbols=symbols)

    # Standard analyzers for Dev A contract
    c.addanalyzer(
        bt.analyzers.TimeReturn,
        _name="returns",
        timeframe=bt.TimeFrame.Days,
    )
    c.addanalyzer(
        bt.analyzers.SharpeRatio,
        _name="sharpe",
        timeframe=bt.TimeFrame.Days,
        riskfreerate=0.0,
    )
    c.addanalyzer(
        bt.analyzers.DrawDown,
        _name="drawdown",
    )

    return c


def run_cerebro(
    strategy_cls: Type[StrategyBase],
    price_data: Dict[str, pd.DataFrame],
    cash: float = 100_000.0,
    commission: float = 0.0,
) -> Tuple[StrategyBase, Dict[str, bt.Analyzer]]:
    """
    Convenience wrapper:
      - builds Cerebro
      - runs it
      - returns (strategy_instance, analyzers)

    This will later be called by the run_backtest() interface layer.
    """
    cerebro = build_cerebro(
        strategy_cls=strategy_cls,
        price_data=price_data,
        cash=cash,
        commission=commission,
    )

    results = cerebro.run()
    if not results:
        raise RuntimeError("Cerebro.run() returned no strategies")

    # We only support a single strategy instance
    strat: StrategyBase = results[0]

    analyzers: Dict[str, bt.Analyzer] = {
        "returns": strat.analyzers.returns,
        "sharpe": strat.analyzers.sharpe,
        "drawdown": strat.analyzers.drawdown,
    }

    return strat, analyzers