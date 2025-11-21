#!/usr/bin/env python3
"""
Phase 2 – Historical Backfill Script

Fetches full history for:
  - ETFs & FX from TwelveData (fallback to yfinance)
  - Macro series from FRED (fredapi)
and writes into Postgres market_data and econ_data tables.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import yfinance as yf
from fredapi import Fred
import requests

from sqlalchemy import text

# Ensure src/ is on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    # If python-dotenv isn't installed, env vars must be set in the shell
    pass

from slice.db import get_engine
from slice.config import load_settings


# ------------------------------------------------------------
# Config – assets and macro series
# ------------------------------------------------------------
ETF_SYMBOLS = [
    "SPY", "QQQ",
    "SGOV", "IEF", "TLT", "TBF",
    "RINF",
    "GLD", "XLE",
    "UUP",
]

FX_SYMBOLS = [
    "EUR/USD",
]

FRED_SERIES = {
    "CPIAUCSL": "CPI",
    "PCEPILFE": "CorePCE",
    "UNRATE": "Unemployment",
    "GDP": "GDP",
    "FEDFUNDS": "FedFunds",
}


# ------------------------------------------------------------
# TwelveData Fetcher
# ------------------------------------------------------------
def fetch_twelvedata_daily(symbol: str, api_key: str) -> pd.DataFrame | None:
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 5000,
        "apikey": api_key,
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        js = r.json()
        if "values" not in js:
            print(f"[TD] No values for {symbol}: {js}")
            return None

        df = pd.DataFrame(js["values"])
        if df.empty:
            print(f"[TD] Empty values for {symbol}")
            return None

        # Normalize datetime → date
        df["date"] = pd.to_datetime(df["datetime"]).dt.date

        # Some instruments (FX) may not have volume
        if "volume" not in df.columns:
            df["volume"] = None

        # Coerce numeric columns where present
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["ticker"] = symbol
        return df[["ticker", "date", "open", "high", "low", "close", "volume"]]

    except Exception as e:
        print(f"[TD] Error fetching {symbol}: {e}")
        return None


# ------------------------------------------------------------
# yfinance Fallback
# ------------------------------------------------------------
def fetch_yf_daily(symbol: str) -> pd.DataFrame | None:
    try:
        yf_symbol = symbol.replace("/", "")
        data = yf.download(yf_symbol, period="max", interval="1d", progress=False)
        if data.empty:
            return None

        df = data.reset_index()
        df["date"] = df["Date"].dt.date
        df["ticker"] = symbol

        return df[["ticker", "date", "Open", "High", "Low", "Close", "Volume"]].rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            }
        )
    except Exception as e:
        print(f"[YF] Error fetching {symbol}: {e}")
        return None


# ------------------------------------------------------------
# FRED Fetcher
# ------------------------------------------------------------
def fetch_fred_series(series_id: str, fred_key: str) -> pd.DataFrame:
    fred = Fred(api_key=fred_key)
    series = fred.get_series(series_id)
    df = series.to_frame("value")
    df.index = df.index.astype("datetime64[ns]").date
    df = df.reset_index().rename(columns={"index": "date"})
    df["series_id"] = series_id
    return df[["series_id", "date", "value"]]


# ------------------------------------------------------------
# Insert helpers
# ------------------------------------------------------------
def insert_market_data(df: pd.DataFrame):
    if df is None or df.empty:
        return

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO market_data (ticker, date, open, high, low, close, volume)
                VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
                ON CONFLICT (ticker, date) DO NOTHING
            """),
            df.to_dict(orient="records")
        )


def insert_econ_data(df: pd.DataFrame):
    if df is None or df.empty:
        return

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO econ_data (series_id, date, value)
                VALUES (:series_id, :date, :value)
                ON CONFLICT (series_id, date) DO NOTHING
            """),
            df.to_dict(orient="records")
        )


# ------------------------------------------------------------
# Main backfill routine
# ------------------------------------------------------------
def main():
    settings = load_settings()
    print("=== Slice Phase 2 Backfill ===")

    # ---- Market Data (ETFs + FX) ----
    for symbol in ETF_SYMBOLS + FX_SYMBOLS:
        print(f"\n[Market] Fetching history for {symbol} ...")

        df = None
        if settings.twelvedata_api_key:
            df = fetch_twelvedata_daily(symbol, settings.twelvedata_api_key)

        if df is None:
            print(f"[Fallback] Trying yfinance for {symbol} ...")
            df = fetch_yf_daily(symbol)

        if df is None or df.empty:
            print(f"[WARN] No data for {symbol}; skipping.")
            continue

        print(f"[OK] {symbol}: {len(df)} rows")
        insert_market_data(df)

    # ---- Macro Data (FRED) ----
    print("\n=== FRED Macro Series ===")
    for series_id in FRED_SERIES:
        print(f"[Macro] {series_id} ...")
        df = fetch_fred_series(series_id, settings.fred_api_key)
        print(f"[OK] {series_id}: {len(df)} rows")
        insert_econ_data(df)

    print("\n=== Backfill complete ===")


if __name__ == "__main__":
    main()