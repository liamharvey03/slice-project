import sys
from pathlib import Path

# add src/ to sys.path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from slice.quant_engine.interface.run_backtest import run_backtest


def main():
    out = run_backtest(
        "BUY_AND_HOLD_FIRST",
        params={"tickers": ["SPY"]}
    )
    print("OK, keys:", out.keys())


if __name__ == "__main__":
    main()