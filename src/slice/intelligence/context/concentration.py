from __future__ import annotations

from typing import Any, Dict, List


def compute_concentration(portfolio_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute concentration metrics for a given portfolio snapshot.

    Input: output of build_portfolio_snapshot(...)
      {
          "positions": [
              {"symbol": ..., "weight": float, ...},
              ...
          ],
          "totals": {...}
      }

    Output:
      {
          "largest_weight": float,
          "top3_sum": float,
          "flags": {
              "single_name_over_20": bool,
              "top3_over_50": bool,
          }
      }
    """
    positions: List[Dict[str, Any]] = portfolio_snapshot.get("positions", [])
    if not positions:
        return {
            "largest_weight": 0.0,
            "top3_sum": 0.0,
            "flags": {
                "single_name_over_20": False,
                "top3_over_50": False,
            },
        }

    weights = sorted([p.get("weight", 0.0) for p in positions], reverse=True)

    largest = weights[0]
    top3 = sum(weights[:3]) if len(weights) >= 3 else sum(weights)

    flags = {
        "single_name_over_20": largest > 0.20,
        "top3_over_50": top3 > 0.50,
    }

    return {
        "largest_weight": largest,
        "top3_sum": top3,
        "flags": flags,
    }
