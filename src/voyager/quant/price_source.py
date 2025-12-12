from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd


class PriceSource(Protocol):
    """
    Abstract interface for retrieving historical and current prices.

    E2 only needs a simple daily-close price interface. Concrete implementations
    can wrap DB loaders, APIs, or cached data, but E2 code will only depend on
    this protocol.
    """

    def get_history(self, asset: str, start: date, end: date) -> pd.Series:
        """
        Return daily prices for `asset` between `start` and `end`.

        Expected:
            - Index: datetime or date, monotonic ascending
            - Values: float closing prices
        """
        ...

    def get_current_price(self, asset: str) -> float:
        """
        Return the latest available price for `asset`.
        """
        ...