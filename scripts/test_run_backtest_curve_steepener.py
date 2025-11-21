import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from slice.quant_engine.interface.run_backtest import run_backtest


def main():
    result = run_backtest(
        "CURVE_STEEPNER",
        params={
            "tickers": ["TBF"],   # must match price_symbol default
            "cash": 100_000.0,
            "commission": 0.0,
        },
    )

    print("Top-level keys:", sorted(result.keys()))
    print("Metrics:", json.dumps(result["metrics"], indent=2))
    print("Period:", result["period"])
    print("Num returns:", len(result["returns"]))
    print("Num orders:", len(result["orders"]))
    print("Num trades:", len(result["trades"]))


if __name__ == "__main__":
    main()