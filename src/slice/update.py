from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import requests
from fredapi import Fred
from sqlalchemy import text

from .config import load_settings
from .db import get_engine, get_last_market_date, get_last_macro_date


# ----------------------------
# TwelveData incremental fetch
# ----------------------------
def fetch_twelvedata_incremental(symbol: str, api_key: str, start_date: date) -> Optional[pd.DataFrame]:
    """
    Fetch daily data for `symbol` from TwelveData starting at `start_date`.

    Returns a DataFrame with columns:
      ticker, date, open, high, low, close, volume
    or None on error / no data.
    """
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 5000,
        "apikey": api_key,
        "start_date": start_date.isoformat(),
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        js = r.json()

        if "values" not in js:
            print(f"[TD] No values for {symbol}: {js}")
            return None

        df = pd.DataFrame(js["values"])
        if df.empty:
            return None

        df["date"] = pd.to_datetime(df["datetime"]).dt.date
        df = df.rename(
            columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )

        # Coerce numeric
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["ticker"] = symbol

        return df[["ticker", "date", "open", "high", "low", "close", "volume"]]

    except Exception as e:
        print(f"[TD] Error fetching {symbol}: {e}")
        return None


# ----------------------------
# Incremental market updater
# ----------------------------
def update_daily_prices() -> None:
    """
    Incrementally update market_data for the core ETF universe.

    Logic:
      - For each symbol, find MAX(date) in market_data.
      - Fetch from TwelveData starting at that date.
      - Drop rows <= last_date.
      - Insert remaining rows with ON CONFLICT DO NOTHING.
    """
    settings = load_settings()
    if not settings.twelvedata_api_key:
        print("[ERROR] TWELVEDATA_API_KEY is not set.")
        return

    engine = get_engine()

    symbols = [
        "SPY",
        "QQQ",
        "SGOV",
        "IEF",
        "TLT",
        "TBF",
        "RINF",
        "GLD",
        "XLE",
        # FX / more ETFs can be added later
    ]

    for symbol in symbols:
        print(f"[Update Prices] {symbol}")
        last_date = get_last_market_date(engine, symbol)

        if last_date is None:
            print("  No existing data in DB; run backfill first. Skipping.")
            continue

        df = fetch_twelvedata_incremental(symbol, settings.twelvedata_api_key, last_date)
        if df is None or df.empty:
            print("  No data returned from TwelveData.")
            continue

        # Keep strictly newer dates only
        df = df[df["date"] > last_date]
        if df.empty:
            print("  No new rows (DB already up to date).")
            continue

        rows = df.to_dict(orient="records")

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO market_data
                        (ticker, date, open, high, low, close, volume)
                    VALUES
                        (:ticker, :date, :open, :high, :low, :close, :volume)
                    ON CONFLICT (ticker, date) DO NOTHING
                    """
                ),
                rows,
            )

        print(f"  Inserted {len(rows)} new row(s).")


# ----------------------------
# Incremental macro updater
# ----------------------------
def update_macro_data() -> None:
    """
    Incrementally update econ_data for the core FRED universe.

    Logic:
      - For each series_id, find MAX(date) in econ_data.
      - Fetch full series via FRED.
      - Filter to rows > last_date.
      - Insert with ON CONFLICT DO NOTHING.
    """
    settings = load_settings()
    if not settings.fred_api_key:
        print("[ERROR] FRED_API_KEY is not set.")
        return

    engine = get_engine()
    fred = Fred(api_key=settings.fred_api_key)

    series_map = {
        "CPIAUCSL": "CPI",
        "PCEPILFE": "Core PCE",
        "UNRATE": "Unemployment",
        "GDP": "GDP",
        "FEDFUNDS": "Fed Funds",
    }

    for series_id, label in series_map.items():
        print(f"[Update Macro] {series_id} ({label})")
        last_date = get_last_macro_date(engine, series_id)

        if last_date is None:
            print("  No existing data in DB; run backfill first. Skipping.")
            continue

        try:
            series = fred.get_series(series_id)
        except Exception as e:
            print(f"  FRED error for {series_id}: {e}")
            continue

        if series is None or series.empty:
            print("  FRED returned empty series.")
            continue

        df = series.to_frame(name="value")
        df.index = df.index.date  # index is datetime64; convert to date
        df = df.reset_index().rename(columns={"index": "date"})

        # Keep strictly newer dates only
        df = df[df["date"] > last_date]
        if df.empty:
            print("  No new rows (DB already up to date).")
            continue

        rows = [
            {
                "series_id": series_id,
                "date": row["date"],
                "value": float(row["value"]),
            }
            for _, row in df.iterrows()
        ]

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO econ_data (series_id, date, value)
                    VALUES (:series_id, :date, :value)
                    ON CONFLICT (series_id, date) DO NOTHING
                    """
                ),
                rows,
            )

        print(f"  Inserted {len(rows)} new row(s).")
