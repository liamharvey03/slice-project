"""
GoldRealYieldsStrategy

Purpose:
  Long gold when real yields are below their own trend, using Phase 2 data.

Data inputs:
  - Price: gold proxy (default GLD) loaded from market_data via price feeds.
  - Econ: real-yield proxy (default FRED DGS10) loaded from econ_data via load_econ_series.

Signal:
  - Compute rolling mean of the real-yield series over a configurable window.
  - If real_yield < rolling_mean on the bar date, target_long weight is applied; otherwise flat.

Parameters (params dict):
  - symbols: list[str] | None — tickers passed from Cerebro; must include price_symbol.
  - price_symbol: str — price feed symbol to trade from market_data.
  - real_yield_series_id: str — econ_data series id to use as real-yield proxy (e.g., DGS10).
  - real_yield_ma_window: int — rolling window length for the real-yield moving average.
  - target_long: float — portfolio weight when long the price_symbol.
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional

import pandas as pd

from slice.quant_engine.strategies.strategy_base import StrategyBase
from slice.quant_engine.data import load_econ_series


class GoldRealYieldsStrategy(StrategyBase):
    """
    Prototype: long gold when real yields are below their own trend.

    Approximation:
      - Uses a single econ series as a proxy for real yields
        (default: DGS10, but you can change real_yield_series_id later).
    - Compute rolling mean of that series.
    - If real_yield < real_yield_MA → long GLD up to target_long.
    """

    params = dict(
        symbols=None,                 # list of tickers provided by Cerebro; must include price_symbol
        price_symbol="GLD",           # ETF proxy for gold, resolved against market_data
        real_yield_series_id="DGS10", # econ_data series id used as real-yield proxy
        real_yield_ma_window=60,      # rolling window length for real yield moving average
        target_long=0.25,             # target portfolio weight when long
    )

    def __init__(self) -> None:
        # Let StrategyBase initialize its machinery (symbol_to_data, etc.)
        super().__init__()

        self._price_symbol: str = self.p.price_symbol
        self._target_long: float = float(self.p.target_long)
        self._ma_window: int = int(self.p.real_yield_ma_window)

        # Backtrader stores params under self.p, not as plain attributes.
        symbols_param: List[str] = list(self.p.symbols or [])

        # Sanity: require that the price_symbol is in the data feeds
        if self._price_symbol not in symbols_param:
            self.log(
                f"[GoldRealYields] price_symbol '{self._price_symbol}' "
                f"not in p.symbols={symbols_param}; staying flat."
            )
            self._enabled = False
            self._real_yield_series = None
            self._real_yield_ma = None
            return

        ry_id = self.p.real_yield_series_id
        ry_df = load_econ_series(ry_id)

        if ry_df.empty:
            self.log(
                f"[GoldRealYields] Missing econ data for real_yield_series_id='{ry_id}'. "
                "Strategy will remain flat."
            )
            self._enabled = False
            self._real_yield_series = None
            self._real_yield_ma = None
            return

        if not {"date", "value"}.issubset(ry_df.columns):
            self.log(
                f"[GoldRealYields] econ_df for '{ry_id}' has unexpected columns "
                f"{list(ry_df.columns)}; staying flat."
            )
            self._enabled = False
            self._real_yield_series = None
            self._real_yield_ma = None
            return

        ry_df = ry_df.copy()

        if not pd.api.types.is_datetime64_any_dtype(ry_df["date"]):
            ry_df["date"] = pd.to_datetime(ry_df["date"])

        ry_df = ry_df.sort_values("date")
        ry_df.set_index(ry_df["date"].dt.date, inplace=True)

        series = ry_df["value"].astype(float)
        ma = series.rolling(self._ma_window).mean()

        if series.empty:
            self.log(
                f"[GoldRealYields] No usable data in series '{ry_id}'; staying flat."
            )
            self._enabled = False
            self._real_yield_series = None
            self._real_yield_ma = None
            return

        self._enabled = True
        self._real_yield_series = series
        self._real_yield_ma = ma

        self.log(
            f"[GoldRealYields] Initialized with real_yield_series_id='{ry_id}', "
            f"{len(series)} points, MA window={self._ma_window}."
        )

    def compute_target_weights(self) -> Dict[str, float]:
        """
        Core decision rule:
          - Flat in all symbols except price_symbol.
          - If real_yield < real_yield_MA on this date → long gold to target_long.
        """
        symbols_param: List[str] = list(self.p.symbols or [])
        weights: Dict[str, float] = {s: 0.0 for s in symbols_param}

        if not getattr(self, "_enabled", False):
            return weights

        if self._real_yield_series is None or self._real_yield_ma is None:
            return weights

        price_symbol = self._price_symbol
        price_data = self.symbol_to_data.get(price_symbol)
        if price_data is None:
            return weights

        # Backtrader data datetime is a float-like; .date(0) returns a datetime.date
        current_date: datetime.date = price_data.datetime.date(0)

        try:
            ry = float(self._real_yield_series.loc[current_date])
            ma = float(self._real_yield_ma.loc[current_date])
        except KeyError:
            # No econ datapoint for this calendar date → stay flat
            return weights

        if pd.isna(ma):
            # MA not yet defined (early in sample) → stay flat
            return weights

        # Simple signal: real yields below their own MA → long gold
        if ry < ma:
            weights[price_symbol] = self._target_long

        return weights
