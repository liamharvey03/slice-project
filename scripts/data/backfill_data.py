#!/usr/bin/env python3
"""
Phase 2 – Historical Backfill Script

Fetches full history for:
  - ETFs & FX from TwelveData
  - Macro series from FRED (fredapi)
and writes into Postgres market_data and econ_data tables.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import time
from fredapi import Fred
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

from voyager.db import get_engine
from voyager.config import load_settings


# ------------------------------------------------------------
# Session Management (connection pooling + retry)
# ------------------------------------------------------------

def create_session() -> requests.Session:
    """Create session with retry logic and connection pooling"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,  # Wait 2s, 4s, 8s between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10
    )
    
    session.mount("https://", adapter)
    return session


# Module-level session singleton
_session: requests.Session | None = None


def get_session() -> requests.Session:
    """Get or create the shared session"""
    global _session
    if _session is None:
        _session = create_session()
    return _session


# ------------------------------------------------------------
# Config – assets and macro series (V3 Complete List)
# ------------------------------------------------------------

# Equity ETFs
EQUITY_ETFS = [
    "SPY",   # S&P 500
    "QQQ",   # Nasdaq 100
    "IWM",   # Russell 2000 (small caps)
    "EFA",   # MSCI EAFE (developed ex-US)
    "EEM",   # MSCI Emerging Markets
]

# Rates/Bond ETFs
RATES_ETFS = [
    "SGOV",  # 0-3 Month T-Bills
    "IEF",   # 7-10 Year Treasury
    "TLT",   # 20+ Year Treasury
    "TBF",   # Short 20+ Year Treasury
    "TIP",   # TIPS (inflation protected)
    "RINF",  # Inflation expectations
]

# Commodity ETFs
COMMODITY_ETFS = [
    "GLD",   # Gold
    "SLV",   # Silver
    "USO",   # Oil (WTI)
    "DBC",   # Broad Commodities Index
    "XLE",   # Energy sector
]

# FX ETFs
FX_ETFS = [
    "UUP",   # US Dollar Index Bullish
    "FXE",   # Euro
    "FXY",   # Japanese Yen
]

# Volatility ETFs (VIXY instead of VIX - TwelveData supports this ETF)
VOL_ETFS = [
    "VIXY",  # ProShares VIX Short-Term Futures ETF
]

# Combine all ETFs
ALL_ETFS = EQUITY_ETFS + RATES_ETFS + COMMODITY_ETFS + FX_ETFS + VOL_ETFS

# Spot FX pairs
FX_PAIRS = [
    "EUR/USD",
]

# FRED Macro Series - expanded for V3
FRED_SERIES = [
    # Inflation
    "CPIAUCSL",   # CPI All Urban Consumers
    "PCEPILFE",   # Core PCE Price Index
    
    # Labor
    "UNRATE",     # Unemployment Rate
    
    # Growth
    "GDP",        # Gross Domestic Product
    
    # Rates - Nominal
    "FEDFUNDS",   # Federal Funds Effective Rate
    "DGS2",       # 2-Year Treasury Constant Maturity
    "DGS10",      # 10-Year Treasury Constant Maturity
    
    # Rates - Real & Breakeven (NEW - required for V3)
    "DFII10",     # 10-Year Treasury Inflation-Indexed (Real Yield)
    "T10YIE",     # 10-Year Breakeven Inflation Rate
]


# ------------------------------------------------------------
# TwelveData Fetcher
# ------------------------------------------------------------
def fetch_twelvedata_daily(symbol: str, api_key: str) -> pd.DataFrame | None:
    """
    Fetch daily OHLCV from TwelveData API with retry logic.
    
    Features:
    - 30 second timeout (5000 rows is a lot of data)
    - 3 retry attempts with exponential backoff
    - Session reuse for connection pooling
    - Rate limit detection and backoff
    """
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 5000,
        "apikey": api_key,
    }

    session = get_session()
    
    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=30)
            js = r.json()
            
            # Rate limit hit - back off and retry
            if js.get("code") == 429:
                wait = (attempt + 1) * 5
                print(f"[TD] Rate limited, waiting {wait}s...", end=" ", flush=True)
                time.sleep(wait)
                continue
            
            # API error response
            if "values" not in js:
                msg = js.get("message", str(js)[:80])
                print(f"[TD] API error: {msg}")
                return None

            df = pd.DataFrame(js["values"])
            if df.empty:
                print(f"[TD] Empty response for {symbol}")
                return None

            # Parse response
            df["date"] = pd.to_datetime(df["datetime"]).dt.date
            
            if "volume" not in df.columns:
                df["volume"] = None

            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df["ticker"] = symbol
            return df[["ticker", "date", "open", "high", "low", "close", "volume"]]

        except requests.exceptions.Timeout:
            wait = (attempt + 1) * 3
            print(f"[TD] Timeout on {symbol}, retry {attempt + 1}/3 in {wait}s...", end=" ", flush=True)
            time.sleep(wait)
            
        except requests.exceptions.ConnectionError:
            wait = (attempt + 1) * 3
            print(f"[TD] Connection error on {symbol}, retry {attempt + 1}/3 in {wait}s...", end=" ", flush=True)
            time.sleep(wait)
            
        except Exception as e:
            print(f"[TD] Error fetching {symbol}: {e}")
            return None
    
    print(f"[TD] Failed after 3 attempts for {symbol}")
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
    print("=== Voyager V3 Data Backfill ===")

    # ---- Market Data (ETFs) ----
    for symbol in ALL_ETFS:
        print(f"\n[Market] Fetching {symbol} ...")
        
        if not settings.twelvedata_api_key:
            print(f"[ERROR] TwelveData API key not configured. Set TWELVEDATA_API_KEY in .env")
            continue
        
        df = fetch_twelvedata_daily(symbol, settings.twelvedata_api_key)
        
        if df is None or df.empty:
            print(f"[WARN] No data for {symbol}; skipping.")
            continue
        
        print(f"[OK] {symbol}: {len(df)} rows")
        insert_market_data(df)
        
        # Polite delay to avoid rate limiting
        time.sleep(1.5)

    # ---- FX Pairs ----
    for symbol in FX_PAIRS:
        print(f"\n[FX] Fetching {symbol} ...")
        
        if not settings.twelvedata_api_key:
            print(f"[ERROR] TwelveData API key not configured. Set TWELVEDATA_API_KEY in .env")
            continue
        
        df = fetch_twelvedata_daily(symbol, settings.twelvedata_api_key)
        
        if df is None or df.empty:
            print(f"[WARN] No data for {symbol}; skipping.")
            continue
        
        print(f"[OK] {symbol}: {len(df)} rows")
        insert_market_data(df)
        
        # Polite delay to avoid rate limiting
        time.sleep(1.5)

    # ---- FRED Macro Series ----
    print("\n=== FRED Macro Series ===")
    for series_id in FRED_SERIES:
        print(f"[Macro] {series_id} ...")
        try:
            df = fetch_fred_series(series_id, settings.fred_api_key)
            print(f"[OK] {series_id}: {len(df)} rows")
            insert_econ_data(df)
        except Exception as e:
            print(f"[WARN] Error fetching {series_id}: {e}")

    print("\n=== Backfill complete ===")


if __name__ == "__main__":
    main()