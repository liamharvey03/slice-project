from __future__ import annotations

from typing import List, Dict, Optional

import pandas as pd

from .schemas import (
    PortfolioReturnSeries,
    RiskReport,
)

from .scenarios import ScenarioConfig, run_scenarios
from .metrics import compute_risk_metrics
from .factor import run_factor_regression
from .rails import compute_risk_rails


def build_risk_report(
    *,
    portfolio: PortfolioReturnSeries,
    asset_returns: Optional[pd.DataFrame] = None,
    weights: Optional[Dict[str, float]] = None,
    factor_data: Optional[pd.DataFrame] = None,
    scenarios: Optional[List[ScenarioConfig]] = None,
    macro: Optional[pd.DataFrame] = None,
) -> RiskReport:
    """
    Master Dev B entrypoint.

    Combines:
      - metrics
      - factor model
      - scenario results
      - risk rails
      - correlation matrix
    into one unified RiskReport Pydantic object.
    """

    # ----- 1. Metrics -----
    risk_metrics = compute_risk_metrics(portfolio)

    # ----- 2. Factor model -----
    if factor_data is not None and not factor_data.empty:
        factor_model = run_factor_regression(
            portfolio=portfolio,
            factor_data=factor_data,
            frequency=portfolio.frequency,
        )
    else:
        from .schemas import FactorModel
        factor_model = FactorModel(
            frequency=portfolio.frequency,
            r_squared=0.0,
            exposures=[],
        )

    # ----- 3. Scenarios -----
    scenario_results = []
    if scenarios:
        scenario_results = run_scenarios(
            portfolio=portfolio,
            factor_model=factor_model,
            scenarios=scenarios,
        )

    # ----- 4. Risk Rails -----
    from .schemas import RiskRails

    if (
        asset_returns is None or asset_returns.empty
        or weights is None or len(weights) == 0
    ):
        rails = RiskRails(
            concentration_flags=[],
            correlation_cluster_flags=[],
            var_1m_95=None,
            var_1m_99=None,
            regime_warnings=[],
        )
        corr_matrix: Dict[str, Dict[str, float]] = {}
    else:
        # Portfolio returns for VaR / rails
        portfolio_returns = (asset_returns * pd.Series(weights)).sum(axis=1)

        rails = compute_risk_rails(
            weights=weights,
            asset_returns=asset_returns,
            portfolio_returns=portfolio_returns,
            macro=macro,
        )

        # Full correlation matrix for consumer
        corr_df = asset_returns.corr()
        corr_matrix = {
            row: {col: float(val) for col, val in corr_df.loc[row].items()}
            for row in corr_df.index
        }

    # ----- 5. Assemble final report -----
    return RiskReport(
        as_of=pd.Timestamp.today().date(),
        portfolio=portfolio,
        risk_metrics=risk_metrics,
        risk_rails=rails,
        factor_model=factor_model,
        scenarios=scenario_results,
        correlation_matrix=corr_matrix,
        metadata={},
    )