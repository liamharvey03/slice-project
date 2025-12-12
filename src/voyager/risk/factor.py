from __future__ import annotations

from typing import List

import pandas as pd
import statsmodels.api as sm

from .schemas import PortfolioReturnSeries, FactorExposure, FactorModel


def _series_from_portfolio(portfolio: PortfolioReturnSeries) -> pd.Series:
    """
    Convert a PortfolioReturnSeries into a pandas Series of returns
    indexed by date.
    """
    data = {p.date: p.value for p in portfolio.returns}
    s = pd.Series(data).sort_index()
    return s


def _align_portfolio_and_factors(
    portfolio: PortfolioReturnSeries,
    factor_data: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Align portfolio returns and factor data on a common date index.
    Only keep dates that exist in both.
    """
    port_series = _series_from_portfolio(portfolio)
    factor_data = factor_data.sort_index()

    joined = pd.concat(
        [port_series.rename("portfolio"), factor_data],
        axis=1,
        join="inner",
    ).dropna()

    y = joined["portfolio"]
    X = joined.drop(columns=["portfolio"])

    return y, X


def run_factor_regression(
    portfolio: PortfolioReturnSeries,
    factor_data: pd.DataFrame,
    frequency: str = "D",
) -> FactorModel:
    """
    Run a multi-factor OLS regression of portfolio returns on factor_data.
    """
    if factor_data is None or factor_data.empty:
        return FactorModel(
            frequency=frequency,
            r_squared=0.0,
            exposures=[],
        )

    y, X = _align_portfolio_and_factors(portfolio, factor_data)

    if X.empty or y.empty or len(X) < X.shape[1] + 2:
        # Not enough data
        return FactorModel(
            frequency=frequency,
            r_squared=0.0,
            exposures=[],
        )

    X_with_const = sm.add_constant(X)
    model = sm.OLS(y, X_with_const).fit()

    exposures: List[FactorExposure] = []
    for factor_name in X.columns:
        beta = float(model.params.get(factor_name, 0.0))
        t_stat = float(model.tvalues.get(factor_name, 0.0))
        p_value = float(model.pvalues.get(factor_name, 1.0))

        exposures.append(
            FactorExposure(
                factor_name=factor_name,
                beta=beta,
                t_stat=t_stat,
                p_value=p_value,
            )
        )

    r_squared = float(model.rsquared)

    return FactorModel(
        frequency=frequency,
        r_squared=r_squared,
        exposures=exposures,
    )