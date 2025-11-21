#!/usr/bin/env python3
"""
Quick validation that the Backtrader feed wiring works end-to-end.
"""

from __future__ import annotations

import sys
from pathlib import Path

import backtrader as bt

# Ensure src/ is importable
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

from slice.quant_engine.data.loader import load_price_data
from slice.quant_engine.data.feed import SlicePandasData


def main() -> int:
    cerebro = bt.Cerebro()

    df = load_price_data("SPY")
    data = SlicePandasData(dataname=df)
    cerebro.adddata(data)

    class TestStrat(bt.Strategy):
        def next(self):
            if not self.position:
                self.buy()

    cerebro.addstrategy(TestStrat)
    cerebro.run()

    print("Loaded rows:", len(df))
    print(df.head())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
