from __future__ import annotations

from datetime import date
from typing import List, Dict, Optional, Any

from pydantic import BaseModel, Field


# ---------- Time series primitives ----------

class TimeSeriesPoint(BaseModel):
    date: date
    value: float


class PortfolioReturnSeries(BaseModel):
    portfolio_id: str
    frequency: str  # "D", "W", "M", etc.
    returns: List[TimeSeriesPoint] = Field(default_factory=list)


# ---------- Risk metrics ----------

class RiskMetrics(BaseModel):
    frequency: str
    total_return: float
    cagr: Optional[float] = None
    annualized_vol: float
    sharpe: Optional[float] = None
    max_drawdown: float
    rolling_vol: Dict[str, float] = Field(default_factory=dict)
    rolling_sharpe: Dict[str, float] = Field(default_factory=dict)


# ---------- Factor model ----------

class FactorExposure(BaseModel):
    factor_name: str
    beta: float
    t_stat: float
    p_value: float


class FactorModel(BaseModel):
    frequency: str
    r_squared: float
    exposures: List[FactorExposure] = Field(default_factory=list)


# ---------- Scenarios ----------

class ScenarioShock(BaseModel):
    factor_name: str
    shock: float  # shock in absolute return terms (e.g. +0.01 = +1%)


class ScenarioResult(BaseModel):
    name: str
    description: Optional[str] = None
    shocks: List[ScenarioShock] = Field(default_factory=list)
    estimated_portfolio_pnl_pct: float
    factor_contributions: Dict[str, float] = Field(default_factory=dict)


# ---------- Risk rails ----------

class ConcentrationFlag(BaseModel):
    asset: str
    weight: float
    threshold: float


class CorrelationClusterFlag(BaseModel):
    cluster_assets: List[str] = Field(default_factory=list)
    comment: Optional[str] = None


class RegimeWarning(BaseModel):
    regime_name: str
    reason: str


class RiskRails(BaseModel):
    concentration_flags: List[ConcentrationFlag] = Field(default_factory=list)
    correlation_cluster_flags: List[CorrelationClusterFlag] = Field(default_factory=list)
    var_1m_95: Optional[float] = None
    var_1m_99: Optional[float] = None
    regime_warnings: List[RegimeWarning] = Field(default_factory=list)


# ---------- Backtest adapter models (Dev A → Dev B) ----------

class StrategyReturnSeries(BaseModel):
    """
    One strategy/asset return series from Dev A backtest output.
    """
    strategy_id: str
    frequency: str  # "D", "W", "M"
    returns: List[TimeSeriesPoint] = Field(default_factory=list)


class BacktestResult(BaseModel):
    """
    Minimal BacktestResultJSON for Dev B.

    All Dev B work should start from this shape: a set of
    component return series that will be aggregated into
    a PortfolioReturnSeries using a weights dict.
    """
    backtest_id: str
    frequency: str
    strategies: List[StrategyReturnSeries] = Field(default_factory=list)


# ---------- Top-level risk report ----------

class RiskReport(BaseModel):
    as_of: date
    portfolio: PortfolioReturnSeries
    risk_metrics: RiskMetrics
    risk_rails: RiskRails
    factor_model: Optional[FactorModel] = None
    scenarios: List[ScenarioResult] = Field(default_factory=list)
    # new: correlation matrix for assets/strategies
    correlation_matrix: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)