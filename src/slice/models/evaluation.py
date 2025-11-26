from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel


class EquityPoint(BaseModel):
    date: datetime
    value: float


class ScenarioImpact(BaseModel):
    name: str
    pnl_abs: float  # absolute P&L in portfolio value units
    pnl_pct: float  # P&L as a percentage (e.g. -10.0 = -10.0%)


class ThesisEvaluationResult(BaseModel):
    performance: Dict[str, float]
    timeseries: List[EquityPoint]
    risk_metrics: Dict[str, float]
    scenarios: List[ScenarioImpact]