from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .common import TradeType


class Trade(BaseModel):
    trade_id: str
    timestamp: datetime
    asset: str
    action: str  # BUY / SELL (we can convert to enum later)
    quantity: float
    price: float
    type: TradeType
    thesis_ref: Optional[str]
    notes: Optional[str] = None