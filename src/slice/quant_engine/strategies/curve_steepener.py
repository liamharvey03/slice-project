"""
CurveSteepenerStrategy

Purpose:
  Express a curve steepener view when long-end yields rise relative to short-end.

Data inputs:
  - Price: steepener proxy (default TBF) from market_data.
  - Econ: 2Y and 10Y yields (default FRED DGS2, DGS10) from econ_data via load_econ_series.

Signal:
  - Compute slope = y10 - y2.
  - Compute rolling mean of slope over slope_ma_window.
  - If slope > slope_MA on the bar date, target_long weight is applied to price_symbol; otherwise flat.

Parameters (params dict):
  - symbols: list[str] | None — tickers supplied by Cerebro; must include price_symbol.
  - price_symbol: str — steepener proxy to trade from market_data.
  - y2_series_id: str — econ_data series id for 2Y yield (e.g., DGS2).
  - y10_series_id: str — econ_data series id for 10Y yield (e.g., DGS10).
  - slope_ma_window: int — rolling window length for slope moving average.
  - target_long: float — portfolio weight when long the steepener proxy.
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional

import pandas as pd

from slice.quant_engine.strategies.strategy_base import StrategyBase
from slice.quant_engine.data import load_econ_series


class CurveSteepenerStrategy(StrategyBase):
    """
    Prototype: Long curve steepener proxy when the curve begins to steepen.

    Approximation:
      - Use 2Y and 10Y yields from econ_data.
      - slope = y10 - y2
      - slope_ma = rolling mean of slope
      - When slope > slope_ma (steepening vs trend): long steepener proxy.

    Notes:
      - Default econ series IDs assume FRED DGS2 and DGS10; adjust if your
        Phase 2 backfill uses different IDs.
      - If data missing or no overlap, strategy is disabled and remains flat.
    """

    params = dict(
        symbols=None,              # list of tickers provided by Cerebro; must include price_symbol
        price_symbol="TBF",        # steepener proxy price symbol resolved via market_data
        y2_series_id="DGS2",       # econ_data series id for 2Y yield
        y10_series_id="DGS10",     # econ_data series id for 10Y yield
        slope_ma_window=60,        # rolling window length for slope moving average
        target_long=0.25,          # target portfolio weight when long steepener proxy
    )

    def __init__(self) -> None:
        super().__init__()

        self._price_symbol: str = self.p.price_symbol
        self._target_long: float = float(self.p.target_long)
        self._ma_window: int = int(self.p.slope_ma_window)

        if self.p.symbols is None or self._price_symbol not in self.p.symbols:
            self.log(
                f"[CurveSteepener] price_symbol '{self._price_symbol}' "
                f"not in feeds {self.p.symbols}; staying flat."
            )
            self._enabled = False
            self._slope = None
            self._slope_ma = None
            return

        y2_id = self.p.y2_series_id
        y10_id = self.p.y10_series_id

        y2_df = load_econ_series(y2_id)
        y10_df = load_econ_series(y10_id)

        if y2_df.empty or y10_df.empty:
            self.log(
                f"[CurveSteepener] Missing econ data for y2_id='{y2_id}' "
                f"or y10_id='{y10_id}'. Strategy will remain flat."
            )
            self._enabled = False
            self._slope = None
            self._slope_ma = None
            return

        for label, df in (("2Y", y2_df), ("10Y", y10_df)):
            if not {"date", "value"}.issubset(df.columns):
                self.log(
                    f"[CurveSteepener] {label} econ_df has unexpected columns "
                    f"{list(df.columns)}; staying flat."
                )
                self._enabled = False
                self._slope = None
                self._slope_ma = None
                return

        y2_df = y2_df.copy()
        y10_df = y10_df.copy()

        if not pd.api.types.is_datetime64_any_dtype(y2_df["date"]):
            y2_df["date"] = pd.to_datetime(y2_df["date"])
        if not pd.api.types.is_datetime64_any_dtype(y10_df["date"]):
            y10_df["date"] = pd.to_datetime(y10_df["date"])

        y2_df = y2_df.sort_values("date")
        y10_df = y10_df.sort_values("date")

        y2_df.set_index(y2_df["date"].dt.date, inplace=True)
        y10_df.set_index(y10_df["date"].dt.date, inplace=True)

        joined = pd.DataFrame({
            "y2": y2_df["value"].astype(float),
            "y10": y10_df["value"].astype(float),
        }).dropna()

        if joined.empty:
            self.log("[CurveSteepener] No overlapping dates between 2Y and 10Y series; staying flat.")
            self._enabled = False
            self._slope = None
            self._slope_ma = None
            return

        slope = joined["y10"] - joined["y2"]
        slope_ma = slope.rolling(self._ma_window).mean()

        self._enabled = True
        self._slope = slope
        self._slope_ma = slope_ma

        self.log(
            f"[CurveSteepener] Initialized with y2_id='{y2_id}', y10_id='{y10_id}', "
            f"{len(slope)} overlapping points, MA window={self._ma_window}."
        )

    def compute_target_weights(self) -> Dict[str, float]:
        symbols = self.p.symbols or []
        weights: Dict[str, float] = {s: 0.0 for s in symbols}

        if not getattr(self, "_enabled", False):
            return weights

        if self._slope is None or self._slope_ma is None:
            return weights

        price_symbol = self._price_symbol
        price_data = self.symbol_to_data.get(price_symbol)
        if price_data is None:
            return weights

        current_date: datetime.date = price_data.datetime.date(0)

        try:
            sl = float(self._slope.loc[current_date])
            ma = float(self._slope_ma.loc[current_date])
        except KeyError:
            return weights

        if pd.isna(ma):
            return weights

        # Signal: slope above its MA → steepening → long steepener proxy
        if sl > ma:
            weights[price_symbol] = self._target_long

        return weights
