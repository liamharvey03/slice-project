from enum import Enum
from pydantic import BaseModel, Field, validator
from typing import List, Optional


class ThesisStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    WATCHLIST = "WATCHLIST"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeType(str, Enum):
    SIMULATED = "SIMULATED"
    REAL = "REAL"


class Sentiment(str, Enum):
    VERY_BULLISH = "VERY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    VERY_BEARISH = "VERY_BEARISH"
    ANXIOUS = "ANXIOUS"
    CONFIDENT = "CONFIDENT"