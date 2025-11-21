from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .schemas import (
    TimeSeriesPoint,
    PortfolioReturnSeries,
    StrategyReturnSeries,
    BacktestResult,
)


def aggregate_portfolio(
    components: Dict[str, List[TimeSeriesPoint]],
    weights: Dict[str, float],
    portfolio_id: str,
    frequency: str,
) -> PortfolioReturnSeries:
    """
    Aggregate multiple component return series into a single portfolio
    return series using the given weights.

    components: mapping from component_id -> list of TimeSeriesPoint
    weights:   mapping from component_id -> weight (summing to ~1)
    """
    if not components:
        return PortfolioReturnSeries(
            portfolio_id=portfolio_id,
            frequency=frequency,
            returns=[],
        )

    frames = {
        name: pd.Series({p.date: p.value for p in series})
        for name, series in components.items()
        if name in weights
    }

    if not frames:
        return PortfolioReturnSeries(
            portfolio_id=portfolio_id,
            frequency=frequency,
            returns=[],
        )

    returns_df = pd.DataFrame(frames).sort_index().fillna(0.0)
    w = pd.Series(weights)
    # align weights with available columns
    w = w.reindex(returns_df.columns).fillna(0.0)

    weighted = (returns_df * w).sum(axis=1)
    points = [
        TimeSeriesPoint(date=idx, value=float(val))
        for idx, val in weighted.items()
    ]

    return PortfolioReturnSeries(
        portfolio_id=portfolio_id,
        frequency=frequency,
        returns=points,
    )


def aggregate_from_backtest(
    backtest: BacktestResult,
    weights: Dict[str, float],
    portfolio_id: str,
) -> PortfolioReturnSeries:
    """
    Adapter from Dev A BacktestResultJSON to Dev B PortfolioReturnSeries.

    backtest.strategies: list of StrategyReturnSeries
    weights: mapping from strategy_id -> portfolio weight
    """
    components: Dict[str, List[TimeSeriesPoint]] = {}
    for strat in backtest.strategies:
        if strat.strategy_id not in weights:
            continue
        components[strat.strategy_id] = strat.returns

    frequency = backtest.frequency
    return aggregate_portfolio(
        components=components,
        weights=weights,
        portfolio_id=portfolio_id,
        frequency=frequency,
    )