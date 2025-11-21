# src/slice/quant_engine/data/loader.py

import pandas as pd
from sqlalchemy import text

from slice.db import get_engine


def load_price_data(ticker: str, start=None, end=None) -> pd.DataFrame:
    """
    Deterministic loader for OHLCV data from Postgres.
    Output columns MUST match Backtrader expectations.

    Parameters
    ----------
    ticker : str
    start : datetime/date or None
    end   : datetime/date or None

    Returns
    -------
    pd.DataFrame indexed by datetime with columns:
    open, high, low, close, volume
    """
    engine = get_engine()

    sql = """
        SELECT date, open, high, low, close, volume
        FROM market_data
        WHERE ticker = :ticker
        ORDER BY date ASC
    """

    params = {"ticker": ticker}

    df = pd.read_sql(text(sql), engine, params=params)

    # Convert to datetime index
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)

    # Enforce Backtrader-friendly dtypes
    df = df.astype({
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "volume": float,
    })

    # Apply optional date filtering
    if start:
        df = df[df.index >= pd.to_datetime(start)]
    if end:
        df = df[df.index <= pd.to_datetime(end)]

    return df
