#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

# Ensure src/ on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Optional .env loader
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from slice.config import load_settings
from slice.db import get_engine


MARKET_TICKERS = [
    "SPY",
    "QQQ",
    "SGOV",
    "IEF",
    "TLT",
    "TBF",
    "RINF",
    "GLD",
    "XLE",
    "UUP",
    "EUR/USD",
]

MACRO_SERIES = [
    "CPIAUCSL",
    "PCEPILFE",
    "UNRATE",
    "GDP",
    "FEDFUNDS",
]


def validate_market(engine) -> None:
    print("=== MARKET DATA VALIDATION ===\n")
    with engine.connect() as conn:
        for ticker in MARKET_TICKERS:
            print(f"[Ticker] {ticker}")
            df = pd.read_sql(
                text(
                    """
                    SELECT date, open, high, low, close, volume
                    FROM market_data
                    WHERE ticker = :ticker
                    ORDER BY date
                    """
                ),
                conn,
                params={"ticker": ticker},
                parse_dates=["date"],
            )

            if df.empty:
                print("  -> NO ROWS\n")
                continue

            # Basic stats
            n_rows = len(df)
            d_min = df["date"].min().date()
            d_max = df["date"].max().date()

            # Duplicate date check
            dup_dates = df["date"].duplicated().sum()

            # Null checks
            null_open = df["open"].isna().sum()
            null_close = df["close"].isna().sum()

            # Non-positive price checks
            nonpos_close = (df["close"] <= 0).sum()

            print(f"  rows: {n_rows}")
            print(f"  date range: {d_min} -> {d_max}")
            print(f"  duplicate dates: {dup_dates}")
            print(f"  null open: {null_open}, null close: {null_close}")
            print(f"  non-positive close: {nonpos_close}")

            # Very rough anomaly indicator: huge jumps
            df["ret_abs"] = (df["close"] / df["close"].shift(1) - 1.0).abs()
            big_moves = df["ret_abs"] > 0.2  # > 20% abs move day-to-day
            n_big = big_moves.sum()
            print(f"  >20% abs daily moves: {n_big}")
            if n_big > 0:
                worst = df.loc[big_moves, ["date", "close", "ret_abs"]].head(3)
                print("    sample big moves:")
                for _, row in worst.iterrows():
                    print(
                        f"      {row['date'].date()}: close={row['close']:.4f}, |ret|={row['ret_abs']:.2%}"
                    )

            print()


def validate_macro(engine) -> None:
    print("=== MACRO DATA VALIDATION ===\n")
    with engine.connect() as conn:
        for sid in MACRO_SERIES:
            print(f"[Series] {sid}")
            df = pd.read_sql(
                text(
                    """
                    SELECT date, value
                    FROM econ_data
                    WHERE series_id = :sid
                    ORDER BY date
                    """
                ),
                conn,
                params={"sid": sid},
                parse_dates=["date"],
            )

            if df.empty:
                print("  -> NO ROWS\n")
                continue

            n_rows = len(df)
            d_min = df["date"].min().date()
            d_max = df["date"].max().date()

            dup_dates = df["date"].duplicated().sum()
            null_val = df["value"].isna().sum()

            # Very crude anomaly check: extreme z-scores
            v = df["value"]
            mean = v.mean()
            std = v.std(ddof=1)
            if std > 0:
                z = (v - mean).abs() / std
                extreme = z > 5  # > 5 sigma
                n_extreme = extreme.sum()
            else:
                n_extreme = 0

            print(f"  rows: {n_rows}")
            print(f"  date range: {d_min} -> {d_max}")
            print(f"  duplicate dates: {dup_dates}")
            print(f"  null values: {null_val}")
            print(f"  extreme values (>5 sigma): {n_extreme}")
            if n_extreme > 0:
                worst = df.loc[extreme, ["date", "value"]].head(3)
                print("    sample extremes:")
                for _, row in worst.iterrows():
                    print(f"      {row['date'].date()}: value={row['value']}")

            print()


def main() -> int:
    settings = load_settings()
    engine = get_engine()

    validate_market(engine)
    validate_macro(engine)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
