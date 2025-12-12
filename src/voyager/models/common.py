from enum import Enum
from pydantic import BaseModel, Field, validator
from typing import List, Optional


class ThesisStatus(str, Enum):
    WATCHLIST = "WATCHLIST"    # Initial state
    VALIDATED = "VALIDATED"    # After Screen 1 logic validation
    CRITIQUED = "CRITIQUED"    # After Screen 2 critique
    BACKTESTED = "BACKTESTED"  # After Screen 3 backtest
    ACTIVE = "ACTIVE"          # After activation/sizing
    CLOSED = "CLOSED"          # Thesis closed


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