from __future__ import annotations

from math import sqrt
from typing import Iterable

import pandas as pd

from .schemas import PortfolioReturnSeries, RiskMetrics


TRADING_DAYS_PER_YEAR = 252


def _series_from_portfolio(portfolio: PortfolioReturnSeries) -> pd.Series:
    """
    Convert a PortfolioReturnSeries into a pandas Series of returns
    indexed by date.
    """
    data = {p.date: p.value for p in portfolio.returns}
    s = pd.Series(data).sort_index()
    return s


def _compute_cumulative_return(returns: pd.Series) -> float:
    """
    Compute cumulative return: (Π (1 + r_t)) - 1
    """
    if returns.empty:
        return 0.0
    return float((1.0 + returns).prod() - 1.0)


def _compute_cagr(returns: pd.Series, freq: str) -> float | None:
    """
    Compute CAGR given a return series and a frequency label ("D", "W", "M").
    If the effective period is too short (< 30 days), return None.
    """
    if returns.empty:
        return None

    start_date = returns.index[0]
    end_date = returns.index[-1]
    num_days = (end_date - start_date).days
    if num_days < 30:
        return None

    cum_return = (1.0 + returns).prod() - 1.0
    years = num_days / 365.25
    if years <= 0:
        return None

    cagr = (1.0 + cum_return) ** (1.0 / years) - 1.0
    return float(cagr)


def _compute_annualized_vol(returns: pd.Series, freq: str) -> float:
    """
    Annualized volatility based on the frequency.
    """
    if returns.empty:
        return 0.0

    std_dev = float(returns.std(ddof=1))

    if freq == "D":
        factor = sqrt(TRADING_DAYS_PER_YEAR)
    elif freq == "W":
        factor = sqrt(52.0)
    elif freq == "M":
        factor = sqrt(12.0)
    else:
        factor = sqrt(TRADING_DAYS_PER_YEAR)

    return std_dev * factor


def _compute_sharpe(
    returns: pd.Series,
    freq: str,
    risk_free_rate_annual: float = 0.0,
) -> float | None:
    """
    Compute annualized Sharpe ratio given a return series and an annual risk-free rate.
    """
    if returns.empty:
        return None

    if freq == "D":
        rf_period = (1.0 + risk_free_rate_annual) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    elif freq == "W":
        rf_period = (1.0 + risk_free_rate_annual) ** (1.0 / 52.0) - 1.0
    elif freq == "M":
        rf_period = (1.0 + risk_free_rate_annual) ** (1.0 / 12.0) - 1.0
    else:
        rf_period = (1.0 + risk_free_rate_annual) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0

    excess = returns - rf_period
    mean_excess = float(excess.mean())
    vol = float(excess.std(ddof=1))
    if vol == 0.0:
        return None

    if freq == "D":
        factor = sqrt(TRADING_DAYS_PER_YEAR)
    elif freq == "W":
        factor = sqrt(52.0)
    elif freq == "M":
        factor = sqrt(12.0)
    else:
        factor = sqrt(TRADING_DAYS_PER_YEAR)

    sharpe = (mean_excess / vol) * factor
    return float(sharpe)


def _compute_max_drawdown(returns: pd.Series) -> float:
    """
    Compute max drawdown from a series of returns.
    """
    if returns.empty:
        return 0.0

    equity = (1.0 + returns).cumprod()
    rolling_max = equity.cummax()
    drawdowns = (equity / rolling_max) - 1.0
    return float(drawdowns.min())


def _compute_rolling_stats(
    returns: pd.Series,
    freq: str,
    windows: Iterable[int] = (21, 63, 252),
):
    rolling_vol = {}
    rolling_sharpe = {}

    for w in windows:
        if len(returns) < w:
            continue

        window = returns[-w:]
        vol_w = _compute_annualized_vol(window, freq)
        sharpe_w = _compute_sharpe(window, freq)

        label = f"{w}D"
        rolling_vol[label] = vol_w
        if sharpe_w is not None:
            rolling_sharpe[label] = sharpe_w

    return rolling_vol, rolling_sharpe


def compute_risk_metrics(
    portfolio: PortfolioReturnSeries,
    risk_free_rate_annual: float = 0.0,
) -> RiskMetrics:

    freq = portfolio.frequency or "D"
    returns = _series_from_portfolio(portfolio)

    total_return = _compute_cumulative_return(returns)
    cagr = _compute_cagr(returns, freq)
    annualized_vol = _compute_annualized_vol(returns, freq)
    sharpe = _compute_sharpe(returns, freq, risk_free_rate_annual)
    max_drawdown = _compute_max_drawdown(returns)
    rolling_vol, rolling_sharpe = _compute_rolling_stats(returns, freq)

    return RiskMetrics(
        frequency=freq,
        total_return=total_return,
        cagr=cagr,
        annualized_vol=annualized_vol,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        rolling_vol=rolling_vol,
        rolling_sharpe=rolling_sharpe,
    )