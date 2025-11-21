import pandas as pd
from datetime import date

from src.slice.risk.schemas import TimeSeriesPoint, StrategyReturnSeries, BacktestResult
from src.slice.risk.aggregator import aggregate_from_backtest


def main() -> None:
    dates = pd.date_range("2025-01-01", periods=5, freq="D")

    strat_a = StrategyReturnSeries(
        strategy_id="A",
        frequency="D",
        returns=[TimeSeriesPoint(date=d.date(), value=0.01) for d in dates],
    )
    strat_b = StrategyReturnSeries(
        strategy_id="B",
        frequency="D",
        returns=[TimeSeriesPoint(date=d.date(), value=0.02) for d in dates],
    )

    backtest = BacktestResult(
        backtest_id="test_backtest",
        frequency="D",
        strategies=[strat_a, strat_b],
    )

    weights = {"A": 0.6, "B": 0.4}

    portfolio = aggregate_from_backtest(
        backtest=backtest,
        weights=weights,
        portfolio_id="agg_test",
    )

    print(portfolio.model_dump_json(indent=2))


if __name__ == "__main__":
    main()