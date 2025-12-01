"""
E5: Execution models for paper trading.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class TradeLeg(BaseModel):
    """A single leg of a trade plan."""
    asset: str
    direction: Literal["LONG"]  # E5 v1: long-only
    size_pct: float = Field(ge=0, le=100)  # percent of total notional (0-100)


class TradePlan(BaseModel):
    """A concrete plan for executing a thesis."""
    thesis_id: str
    total_notional: float = Field(gt=0)  # dollars to deploy into this thesis
    legs: List[TradeLeg]  # weights that sum <= 100


class ThesisPnL(BaseModel):
    """P&L metrics for a thesis."""
    thesis_id: str
    invested_notional: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: Optional[float] = None  # None if invested_notional == 0


class SizingConstraints(BaseModel):
    """
    Configuration for how much capital/risk a thesis is allowed to take.
    
    E5 v1 uses simple, static defaults; later phases can make this dynamic
    and risk-aware without changing the TradePlan DTO.
    """
    max_gross_leverage: float = 2.0  # fraction of equity
    max_position_weight: float = 0.15  # fraction of total_notional
    max_risk_per_thesis: float = 0.02  # fraction of total_notional

