from __future__ import annotations

from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

from .schemas import (
    ConcentrationFlag,
    CorrelationClusterFlag,
    RegimeWarning,
    RiskRails,
)


def compute_concentration_flags(
    weights: Dict[str, float],
    threshold: float = 0.2,
) -> List[ConcentrationFlag]:
    """
    Flag any asset whose absolute weight exceeds the given threshold.
    """
    flags: List[ConcentrationFlag] = []

    for asset, w in weights.items():
        if abs(w) > threshold:
            flags.append(
                ConcentrationFlag(
                    asset=asset,
                    weight=float(w),
                    threshold=threshold,
                )
            )

    return flags


def _find_corr_clusters(
    corr: pd.DataFrame,
    corr_threshold: float,
) -> List[List[str]]:
    """
    Build clusters of assets where |corr| >= corr_threshold using
    a simple graph connected-components approach.
    """
    assets = list(corr.columns)
    adjacency: Dict[str, Set[str]] = {a: set() for a in assets}

    for i, a in enumerate(assets):
        for j in range(i + 1, len(assets)):
            b = assets[j]
            c = corr.loc[a, b]
            if abs(c) >= corr_threshold:
                adjacency[a].add(b)
                adjacency[b].add(a)

    visited: Set[str] = set()
    clusters: List[List[str]] = []

    for a in assets:
        if a in visited:
            continue
        # BFS / DFS
        stack = [a]
        cluster: Set[str] = set()
        while stack:
            x = stack.pop()
            if x in visited:
                continue
            visited.add(x)
            cluster.add(x)
            for y in adjacency[x]:
                if y not in visited:
                    stack.append(y)
        if len(cluster) >= 2:
            clusters.append(sorted(cluster))

    return clusters


def compute_correlation_cluster_flags(
    returns: pd.DataFrame,
    corr_threshold: float = 0.8,
) -> List[CorrelationClusterFlag]:
    """
    Detect clusters of highly correlated assets (|corr| >= threshold).

    Instead of flagging just pairs, we group connected assets into clusters.
    """
    flags: List[CorrelationClusterFlag] = []

    if returns is None or returns.empty:
        return flags

    corr = returns.corr()
    clusters = _find_corr_clusters(corr, corr_threshold=corr_threshold)

    for cluster in clusters:
        comment = (
            f"Cluster of {len(cluster)} assets with |corr|>={corr_threshold:.2f} "
            f"based on historical returns."
        )
        flags.append(
            CorrelationClusterFlag(
                cluster_assets=cluster,
                comment=comment,
            )
        )

    return flags


def compute_var(
    portfolio_returns: pd.Series,
    horizon_days: int = 21,
    alpha_95: float = 0.05,
    alpha_99: float = 0.01,
) -> tuple[Optional[float], Optional[float]]:
    """
    Historical VaR estimate:

    - Use daily returns
    - Build *actual* horizon returns by rolling compounding:
        R_h = Π (1 + r_t) - 1 over each window of size horizon_days
    - Take empirical quantiles of this horizon return distribution.
    """
    if portfolio_returns is None or portfolio_returns.empty:
        return None, None

    daily = portfolio_returns.dropna().astype(float)
    if daily.empty:
        return None, None

    # Rolling horizon returns
    rolling_prod = (1.0 + daily).rolling(horizon_days).apply(
        lambda x: float(np.prod(x) - 1.0),
        raw=False,
    )
    horizon_returns = rolling_prod.dropna()
    if horizon_returns.empty:
        return None, None

    var_95 = float(horizon_returns.quantile(alpha_95))
    var_99 = float(horizon_returns.quantile(alpha_99))

    return var_95, var_99


def compute_regime_warnings(
    macro: Optional[pd.DataFrame] = None,
) -> List[RegimeWarning]:
    """
    Lightweight regime warning logic using optional macro features:
      - 'yc_10y_2y' (bp)
      - 'cpi_yoy' (%)
      - 'vix' (level)
    """
    warnings: List[RegimeWarning] = []

    if macro is None or macro.empty:
        return warnings

    latest = macro.sort_index().iloc[-1]

    if "yc_10y_2y" in latest.index:
        yc = float(latest["yc_10y_2y"])
        if yc < 0:
            warnings.append(
                RegimeWarning(
                    regime_name="Yield Curve Inversion",
                    reason=f"10Y-2Y spread inverted ({yc:.1f} bp).",
                )
            )

    if "cpi_yoy" in latest.index:
        cpi = float(latest["cpi_yoy"])
        if cpi > 4.0:
            warnings.append(
                RegimeWarning(
                    regime_name="High Inflation",
                    reason=f"CPI YoY elevated ({cpi:.1f}%).",
                )
            )

    if "vix" in latest.index:
        vix = float(latest["vix"])
        if vix > 25.0:
            warnings.append(
                RegimeWarning(
                    regime_name="High Equity Volatility",
                    reason=f"VIX elevated ({vix:.1f}).",
                )
            )

    return warnings


def compute_risk_rails(
    weights: Dict[str, float],
    asset_returns: pd.DataFrame,
    portfolio_returns: pd.Series,
    macro: Optional[pd.DataFrame] = None,
    concentration_threshold: float = 0.2,
    corr_threshold: float = 0.8,
    var_horizon_days: int = 21,
) -> RiskRails:
    """
    Build a RiskRails object from:

      - position weights
      - asset-level returns (DataFrame)
      - portfolio-level returns (Series)
      - optional macro data
    """
    concentration_flags = compute_concentration_flags(
        weights=weights,
        threshold=concentration_threshold,
    )

    correlation_cluster_flags = compute_correlation_cluster_flags(
        returns=asset_returns,
        corr_threshold=corr_threshold,
    )

    var_95, var_99 = compute_var(
        portfolio_returns=portfolio_returns,
        horizon_days=var_horizon_days,
    )

    regime_warnings = compute_regime_warnings(macro)

    return RiskRails(
        concentration_flags=concentration_flags,
        correlation_cluster_flags=correlation_cluster_flags,
        var_1m_95=var_95,
        var_1m_99=var_99,
        regime_warnings=regime_warnings,
    )