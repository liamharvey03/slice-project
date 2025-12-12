from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from .common import Sentiment


class Observation(BaseModel):
    id: str
    timestamp: datetime
    text: str
    thesis_ref: List[str]
    sentiment: Sentiment
    categories: List[str]
    actionable: str  # constrained later ("YES", "NO", "MONITORING")

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v):
        if not v.strip():
            raise ValueError("text cannot be empty")
        return v

    @field_validator("categories", mode="after")
    @classmethod
    def categories_non_empty(cls, v):
        # Manually iterate since each_item is removed
        for item in v:
            if not item.strip():
                raise ValueError("categories contains empty string")
        return v