from __future__ import annotations
from typing import Optional
import pandas as pd

from sqlalchemy import text
from slice.db import get_engine


def load_econ_series(
    series_id: str,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """
    Load econ_data for a given series_id, returning:
        date | value
    """

    engine = get_engine()

    query = """
        SELECT date, value
        FROM econ_data
        WHERE series_id = :series_id
        ORDER BY date ASC;
    """

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"series_id": series_id})

    if df.empty:
        return df

    # Ensure expected columns and types
    df["date"] = pd.to_datetime(df["date"])
    df = df[["date", "value"]]   # <-- IMPORTANT: enforce column order

    if start is not None:
        df = df[df["date"] >= pd.to_datetime(start)]
    if end is not None:
        df = df[df["date"] <= pd.to_datetime(end)]

    return df