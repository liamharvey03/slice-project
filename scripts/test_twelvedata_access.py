# scripts/test_twelvedata_access.py (sketch)

import random
import pandas as pd
import requests
from pathlib import Path
import sys

from slice.config import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "twelvedata"

def test_symbol(symbol: str, api_key: str) -> dict:
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 1000,
        "apikey": api_key,
    }
    r = requests.get(url, params=params, timeout=10)
    js = r.json()
    ok = ("values" in js)
    n = len(js.get("values", [])) if ok else 0
    return {"symbol": symbol, "ok": ok, "rows": n, "raw": js if not ok else None}

def main():
    settings = load_settings()
    api_key = settings.twelvedata_api_key
    if not api_key:
        print("TWELVEDATA_API_KEY not set")
        sys.exit(1)

    # Example: ETFs
    etf_df = pd.read_csv(DATA_DIR / "12data_etf.csv")
    candidates = etf_df["symbol"].dropna().unique().tolist()
    sample = random.sample(candidates, k=min(20, len(candidates)))

    results = []
    for symbol in sample:
        print(f"Testing {symbol} ...")
        res = test_symbol(symbol, api_key)
        results.append(res)

    ok_count = sum(1 for r in results if r["ok"])
    print(f"\nOK: {ok_count}/{len(results)}")

if __name__ == "__main__":
    main()