from __future__ import annotations
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from .common import ThesisStatus, Direction


class ThesisExpressionLeg(BaseModel):
    asset: str
    direction: Direction
    size_pct: Optional[float] = Field(None, ge=0, le=100)

    @validator("asset")
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

    @validator("drivers", "disconfirmers", "expression", each_item=False)
    def non_empty_lists(cls, v, field):
        if len(v) == 0:
            raise ValueError(f"{field.name} cannot be empty")
        return v

    @validator("monitor_indices", each_item=True)
    def monitor_index_format(cls, v):
        if not v.strip():
            raise ValueError("monitor_indices contains empty string")
        return v