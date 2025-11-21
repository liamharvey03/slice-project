"""
USDDivergenceStrategy

Purpose:
  Express a long-USD view when the US vs foreign short-rate differential is above trend.

Data inputs:
  - Price: USD proxy (default UUP) from market_data.
  - Econ: US short rate (default DGS2) and comparison rate (default DGS10 placeholder)
    from econ_data via load_econ_series.

Signal:
  - Compute spread = us_rate - eu_rate.
  - Compute rolling mean over spread_ma_window.
  - If spread > spread_MA on the bar date, target_long weight is applied to price_symbol; else flat.

Parameters (params dict):
  - symbols: list[str] | None — tickers supplied by Cerebro; must include price_symbol.
  - price_symbol: str — USD price proxy to trade from market_data.
  - us_rate_series_id: str — econ_data series id for US short rate (e.g., DGS2).
  - eu_rate_series_id: str — econ_data series id for comparator rate (placeholder needs real ID).
  - spread_ma_window: int — rolling window length for spread moving average.
  - target_long: float — portfolio weight when long the price_symbol.
"""
from __future__ import annotations

import datetime
from typing import Dict

import pandas as pd

from slice.quant_engine.strategies.strategy_base import StrategyBase
from slice.quant_engine.data import load_econ_series


class USDDivergenceStrategy(StrategyBase):
    """
    Prototype: Long USD when US vs "EU" rate differential is above its own MA.

    - Uses two econ series:
        * us_rate_series_id (default: DGS2, US 2Y yield)
        * eu_rate_series_id (default: DGS10, used here as a foreign anchor)

    - spread = us - eu
    - spread_ma = rolling mean(spread, spread_ma_window)
    - If spread > spread_ma: long price_symbol (default: UUP), else flat.

    This is deliberately simple and sandbox-y, just like GoldRealYieldsStrategy.
    """

    params = dict(
        symbols=None,                 # list of tickers provided by Cerebro; must include price_symbol
        price_symbol="UUP",           # USD price proxy resolved via market_data
        us_rate_series_id="DGS2",     # econ_data series id for US short rate
        eu_rate_series_id="DGS10",    # econ_data series id for comparator rate (placeholder; replace if needed)
        spread_ma_window=60,          # rolling window length for spread moving average
        target_long=0.25,             # target portfolio weight when long USD proxy
    )

    def __init__(self) -> None:
        super().__init__()

        self._price_symbol: str = self.p.price_symbol
        self._target_long: float = float(self.p.target_long)
        self._ma_window: int = int(self.p.spread_ma_window)

        # Sanity: make sure price_symbol is in the symbols list passed in
        if self.p.symbols is None or self._price_symbol not in self.p.symbols:
            self.log(
                f"[USDDivergence] price_symbol '{self._price_symbol}' "
                f"not in p.symbols={self.p.symbols}; staying flat."
            )
            self._enabled = False
            self._spread = None
            self._spread_ma = None
            return

        us_id = self.p.us_rate_series_id
        eu_id = self.p.eu_rate_series_id

        us_df = load_econ_series(us_id)
        eu_df = load_econ_series(eu_id)

        if us_df.empty or eu_df.empty:
            self.log(
                f"[USDDivergence] Missing econ data for us_id='{us_id}' "
                f"or eu_id='{eu_id}'. Strategy will remain flat."
            )
            self._enabled = False
            self._spread = None
            self._spread_ma = None
            return

        # Expect columns ['date', 'value'] from load_econ_series
        for label, df in (("US", us_df), ("EU", eu_df)):
            if not {"date", "value"}.issubset(df.columns):
                self.log(
                    f"[USDDivergence] {label} econ_df has unexpected columns "
                    f"{list(df.columns)}; staying flat."
                )
                self._enabled = False
                self._spread = None
                self._spread_ma = None
                return

        us_df = us_df.copy()
        eu_df = eu_df.copy()

        if not pd.api.types.is_datetime64_any_dtype(us_df["date"]):
            us_df["date"] = pd.to_datetime(us_df["date"])
        if not pd.api.types.is_datetime64_any_dtype(eu_df["date"]):
            eu_df["date"] = pd.to_datetime(eu_df["date"])

        us_df = us_df.sort_values("date")
        eu_df = eu_df.sort_values("date")

        # Index by date (date-only) to align with daily price series
        us_df.set_index(us_df["date"].dt.date, inplace=True)
        eu_df.set_index(eu_df["date"].dt.date, inplace=True)

        joined = pd.DataFrame(
            {
                "us": us_df["value"].astype(float),
                "eu": eu_df["value"].astype(float),
            }
        ).dropna()

        if joined.empty:
            self.log(
                "[USDDivergence] No overlapping dates between US and EU series; "
                "staying flat."
            )
            self._enabled = False
            self._spread = None
            self._spread_ma = None
            return

        spread = joined["us"] - joined["eu"]
        spread_ma = spread.rolling(self._ma_window).mean()

        self._enabled = True
        self._spread = spread
        self._spread_ma = spread_ma

        self.log(
            f"[USDDivergence] Initialized with us_id='{us_id}', eu_id='{eu_id}', "
            f"{len(spread)} overlapping points, MA window={self._ma_window}."
        )

    def compute_target_weights(self) -> Dict[str, float]:
        """
        Core hook for StrategyBase: compute per-symbol target weights at each bar.

        - Default flat across all symbols.
        - If signal is on and econ series aligned for the current date, allocate
          target_long to the price_symbol, 0 to others.
        """
        symbols = self.p.symbols or []
        weights: Dict[str, float] = {s: 0.0 for s in symbols}

        if not getattr(self, "_enabled", False):
            return weights

        if self._spread is None or self._spread_ma is None:
            return weights

        price_data = self.symbol_to_data.get(self._price_symbol)
        if price_data is None:
            return weights

        current_date: datetime.date = price_data.datetime.date(0)

        try:
            sp = float(self._spread.loc[current_date])
            ma = float(self._spread_ma.loc[current_date])
        except KeyError:
            # No econ data for this exact date → stay flat
            return weights

        if pd.isna(ma):
            return weights

        if sp > ma:
            weights[self._price_symbol] = self._target_long

        return weights
