from datetime import date
import pandas as pd

from src.slice.risk.schemas import (
    TimeSeriesPoint,
    PortfolioReturnSeries,
    ScenarioShock,
)
from src.slice.risk.factor import run_factor_regression
from src.slice.risk.scenarios import ScenarioConfig, run_scenarios


def main() -> None:
    # 60 days of data
    dates = pd.date_range("2025-01-01", periods=60, freq="D")

    # Factor: 0.5% per day
    factor_returns = pd.Series(0.005, index=dates, name="FACTOR1")
    factor_df = factor_returns.to_frame()

    # Portfolio: 1% per day
    portfolio_returns = [
        TimeSeriesPoint(date=d.date(), value=0.01)
        for d in dates
    ]

    portfolio = PortfolioReturnSeries(
        portfolio_id="test_portfolio",
        frequency="D",
        returns=portfolio_returns,
    )

    # Run factor regression
    factor_model = run_factor_regression(portfolio, factor_df, frequency="D")

    # Scenario: +1% shock
    scenario = ScenarioConfig(
        name="Factor1 up 1%",
        description="Shock FACTOR1 by +1%",
        shocks=[
            ScenarioShock(factor_name="FACTOR1", shock=0.01),
        ],
    )

    # Run scenario engine
    results = run_scenarios(
        portfolio=portfolio,
        factor_model=factor_model,
        scenarios=[scenario],
    )

    for r in results:
        print(r.model_dump_json(indent=2))


if __name__ == "__main__":
    main()