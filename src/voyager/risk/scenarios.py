from __future__ import annotations

from typing import List, Dict

from pydantic import BaseModel

from .schemas import (
    PortfolioReturnSeries,
    FactorModel,
    ScenarioShock,
    ScenarioResult,
)


from typing import Optional

class ScenarioConfig(BaseModel):
    """
    Input configuration for a scenario.
    """
    name: str
    description: Optional[str] = None
    shocks: List[ScenarioShock]

def _beta_lookup(factor_model: FactorModel) -> Dict[str, float]:
    """
    Build a mapping: factor_name -> beta from the FactorModel.
    """
    betas: Dict[str, float] = {}
    for exp in factor_model.exposures:
        betas[exp.factor_name] = exp.beta
    return betas


def run_scenarios(
    portfolio: PortfolioReturnSeries,
    factor_model: FactorModel,
    scenarios: List[ScenarioConfig],
) -> List[ScenarioResult]:
    """
    Estimate portfolio P&L impact for each scenario using a simple
    linear beta-based model:

        ΔP ≈ Σ_i beta_i * shock_i

    where:
      - beta_i comes from FactorModel
      - shock_i comes from ScenarioConfig.shocks

    Returns a list of ScenarioResult objects.
    """
    # Portfolio is included for future extension; currently unused.
    _ = portfolio  # avoid unused variable warning

    betas = _beta_lookup(factor_model)
    results: List[ScenarioResult] = []

    for cfg in scenarios:
        factor_contribs: Dict[str, float] = {}
        total_pnl_pct = 0.0

        for shock in cfg.shocks:
            b = betas.get(shock.factor_name, 0.0)
            contrib = b * shock.shock
            factor_contribs[shock.factor_name] = contrib
            total_pnl_pct += contrib

        result = ScenarioResult(
            name=cfg.name,
            description=cfg.description,
            shocks=cfg.shocks,
            estimated_portfolio_pnl_pct=total_pnl_pct,
            factor_contributions=factor_contribs,
        )
        results.append(result)

    return results