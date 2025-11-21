import pandas as pd
from datetime import date

from src.slice.risk.schemas import (
    PortfolioReturnSeries,
    TimeSeriesPoint,
    ScenarioShock,
)
from src.slice.risk.scenarios import ScenarioConfig
from src.slice.risk.report import build_risk_report


def main() -> None:
    # --- Create 60-day portfolio of +1% per day ---
    dates = pd.date_range("2025-01-01", periods=60, freq="D")

    portfolio_returns = [
        TimeSeriesPoint(date=d.date(), value=0.01)
        for d in dates
    ]

    portfolio = PortfolioReturnSeries(
        portfolio_id="test_portfolio",
        frequency="D",
        returns=portfolio_returns,
    )

    # --- Asset returns (3 assets) ---
    base = pd.Series(0.001, index=dates)
    asset_returns = pd.DataFrame(
        {
            "ASSET_A": base + 0.0005,
            "ASSET_B": base + 0.0004,
            "ASSET_C": base - 0.0001,
        },
        index=dates,
    )

    weights = {
        "ASSET_A": 0.5,
        "ASSET_B": 0.3,
        "ASSET_C": 0.2,
    }

    # --- Factor data ---
    factor_data = pd.DataFrame(
        {"FACTOR1": 0.005},
        index=dates,
    )

    # --- One Scenario ---
    scenario = ScenarioConfig(
        name="Factor1 up 1%",
        description="Shock FACTOR1 by +1%",
        shocks=[ScenarioShock(factor_name="FACTOR1", shock=0.01)],
    )

    # --- Macro ---
    macro = pd.DataFrame(
        {
            "yc_10y_2y": [-40],
            "cpi_yoy": [5.2],
            "vix": [28],
        },
        index=[dates[-1]],
    )

    report = build_risk_report(
        portfolio=portfolio,
        asset_returns=asset_returns,
        weights=weights,
        factor_data=factor_data,
        scenarios=[scenario],
        macro=macro,
    )

    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()