import pandas as pd

from src.slice.risk.schemas import RiskRails
from src.slice.risk.rails import compute_risk_rails


def main() -> None:
    # Fake weights for 3 assets
    weights = {
        "ASSET_A": 0.5,
        "ASSET_B": 0.3,
        "ASSET_C": 0.2,
    }

    # Build 60 days of random-ish returns but with A and B highly correlated
    dates = pd.date_range("2025-01-01", periods=60, freq="D")

    base = pd.Series(0.001, index=dates)  # 0.1% per day
    noise_a = pd.Series(0.0005, index=dates)
    noise_b = pd.Series(0.0006, index=dates)
    noise_c = pd.Series(-0.0002, index=dates)

    asset_returns = pd.DataFrame(
        {
            "ASSET_A": base + noise_a,
            "ASSET_B": base + noise_b,   # similar pattern to A
            "ASSET_C": noise_c,          # different behavior
        },
        index=dates,
    )

    # Portfolio returns = weighted sum of asset returns
    portfolio_returns = (asset_returns * pd.Series(weights)).sum(axis=1)

    # Dummy macro data
    macro = pd.DataFrame(
        {
            "yc_10y_2y": [-50],   # inverted curve
            "cpi_yoy": [5.5],     # high inflation
            "vix": [30],          # elevated vol
        },
        index=[dates[-1]],
    )

    rails: RiskRails = compute_risk_rails(
        weights=weights,
        asset_returns=asset_returns,
        portfolio_returns=portfolio_returns,
        macro=macro,
        concentration_threshold=0.2,
        corr_threshold=0.8,
        var_horizon_days=21,
    )

    print(rails.model_dump_json(indent=2))


if __name__ == "__main__":
    main()