"""
Phase 7 smoke test script.

Usage:
    python scripts/run_phase7_smoke.py

Assumes the FastAPI app is running locally at http://localhost:8000
and that /api/v1/intel/* routes are mounted.
"""

import json
import sys
from typing import Any, Dict

import requests


BASE_URL = "http://localhost:8000/api/v1/intel"


def _post(path: str, payload: Dict[str, Any]) -> None:
    url = f"{BASE_URL}{path}"
    print(f"\nPOST {url}")
    try:
        resp = requests.post(url, json=payload, timeout=10)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return

    print(f"  status: {resp.status_code}")
    try:
        data = resp.json()
        print("  json:", json.dumps(data, indent=2)[:500])
    except Exception:
        print("  body:", resp.text[:500])


def main() -> None:
    print("Phase 7 smoke: horizon/strategy/diagnostics/narrative\n")

    _post(
        "/horizon",
        {
            "thesis_id": 1,
            "horizon_months": 12,
        },
    )

    _post(
        "/strategy",
        {
            "extra_instructions": "Keep a balanced book.",
        },
    )

    _post(
        "/diagnostics",
        {
            "extra_instructions": "Highlight major risk concentrations.",
        },
    )

    _post(
        "/narrative",
        {
            "window_label": "weekly",
            "extra_instructions": "Focus on macro narrative.",
        },
    )


if __name__ == "__main__":
    sys.exit(main())
