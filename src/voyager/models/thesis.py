from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum
from .common import ThesisStatus, Direction


class ThesisExpressionLeg(BaseModel):
    asset: str
    direction: Direction
    size_pct: Optional[float] = Field(None, ge=0, le=100)

    @field_validator("asset")
    @classmethod
    def asset_not_empty(cls, v):
        if not v.strip():
            raise ValueError("asset cannot be empty")
        return v


class Thesis(BaseModel):
    id: str
    title: str
    hypothesis: str
    drivers: List[str]
    disconfirmers: List[str]
    expression: List[ThesisExpressionLeg]
    start_date: str
    review_date: Optional[str]
    status: ThesisStatus
    tags: List[str]
    monitor_indices: List[str]
    notes: Optional[str] = None
    risk_rails: Optional["RiskRails"] = None
    final_size: Optional[float] = None

    @field_validator("drivers", "disconfirmers", "expression")
    @classmethod
    def non_empty_lists(cls, v, info):
        if len(v) == 0:
            raise ValueError(f"{info.field_name} cannot be empty")
        return v

    @field_validator("monitor_indices", mode="after")
    @classmethod
    def monitor_index_format(cls, v):
        # Manually iterate since each_item is removed
        for item in v:
            if not item.strip():
                raise ValueError("monitor_indices contains empty string")
        return v


# ===========================================
# V3 Models
# ===========================================

class ThesisStatusV3(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    CRITIQUED = "CRITIQUED"
    BACKTESTED = "BACKTESTED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class RiskRails(BaseModel):
    max_dd_tolerance: float = Field(ge=0, le=1, description="e.g., 0.08 = 8%")
    position_cap: float = Field(ge=0, le=1, description="e.g., 0.10 = 10%")
    stop_loss: Optional[float] = Field(default=None, ge=0, le=1)
    time_horizon: Optional[str] = Field(default=None, description="ISO date string")


class ThesisSnapshot(BaseModel):
    id: str
    thesis_id: str
    snapshot_type: str  # "pre_critique" | "post_critique" | "activation"
    content: dict  # Full thesis state at snapshot time
    created_at: str  # ISO datetime


class LogicLink(BaseModel):
    claim: str  # "Fed hikes → real yields up"
    series_a: str  # "FEDFUNDS"
    series_b: str  # "DFII10"
    query_type: str  # "correlation" | "conditional_returns"
    result: float  # The computed value
    interpretation: str  # "supports" | "weak" | "contradicts"


class LogicValidation(BaseModel):
    id: str
    thesis_id: str
    links: List[LogicLink]
    created_at: str  # ISO datetime


# Resolve forward reference for Thesis.risk_rails
Thesis.model_rebuild()