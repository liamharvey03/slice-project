from __future__ import annotations
from pydantic import BaseModel, Field, validator
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

    @validator("text")
    def text_not_empty(cls, v):
        if not v.strip():
            raise ValueError("text cannot be empty")
        return v

    @validator("categories", each_item=True)
    def categories_non_empty(cls, v):
        if not v.strip():
            raise ValueError("categories contains empty string")
        return v