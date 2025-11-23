# src/slice/config.py

import os
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()


@dataclass
class DatabaseConfig:
    url: str


@dataclass
class Settings:
    db: DatabaseConfig
    twelvedata_api_key: str
    fred_api_key: str


def load_settings() -> Settings:
    """
    Phase 2: only care about DB + data provider keys.

    Required:
      - SLICE_DB_URL

    Optional (but needed later for data fetch):
      - TWELVEDATA_API_KEY
      - FRED_API_KEY
    """
    db_url = os.getenv("SLICE_DB_URL")
    if not db_url:
        raise RuntimeError("Environment variable SLICE_DB_URL is not set")

    td_key = os.getenv("TWELVEDATA_API_KEY", "")
    fred_key = os.getenv("FRED_API_KEY", "")

    return Settings(
        db=DatabaseConfig(url=db_url),
        twelvedata_api_key=td_key,
        fred_api_key=fred_key,
    )