#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Optional: load .env if available
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from slice.update import update_daily_prices, update_macro_data


def main() -> int:
    print("\n=== Slice Incremental Update ===\n")

    update_daily_prices()
    print("\n--- Market update complete ---\n")

    update_macro_data()
    print("\n--- Macro update complete ---\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
