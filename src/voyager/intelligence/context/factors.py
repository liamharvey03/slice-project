from __future__ import annotations

from typing import Any, Dict, Iterable


# Static placeholder factor table.
# Later: replace with DB-backed or quant-engine derived betas.
STATIC_FACTOR_TABLE = {
    "AAPL": {"beta_real_yield": -0.1, "beta_dxy": -0.05, "beta_growth": 0.25},
    "MSFT": {"beta_real_yield": -0.05, "beta_dxy": -0.02, "beta_growth": 0.20},
    "TLT":  {"beta_real_yield": -1.50, "beta_dxy":  0.00, "beta_growth": -0.30},
}


def map_position_factors(positions: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Map each position symbol to factor betas.

    If a symbol is missing from the static table, assign 0 betas.
    """
    mapping: Dict[str, Dict[str, float]] = {}

    for pos in positions:
        sym = pos["symbol"]
        mapping[sym] = STATIC_FACTOR_TABLE.get(sym, {
            "beta_real_yield": 0.0,
            "beta_dxy": 0.0,
            "beta_growth": 0.0,
        })

    return mapping


def aggregate_factors(mapped: Dict[str, Dict[str, float]], positions: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """
    Aggregate factor loadings weighted by position weights.

    mapped: output of map_position_factors(...)
    positions: portfolio positions with computed "weight"
    """
    agg = {"beta_real_yield": 0.0, "beta_dxy": 0.0, "beta_growth": 0.0}

    for pos in positions:
        sym = pos["symbol"]
        w = pos.get("weight", 0.0)
        betas = mapped.get(sym, {})

        agg["beta_real_yield"] += betas.get("beta_real_yield", 0.0) * w
        agg["beta_dxy"] += betas.get("beta_dxy", 0.0) * w
        agg["beta_growth"] += betas.get("beta_growth", 0.0) * w

    return agg


def compute_factor_exposures(portfolio_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    End-to-end factor exposure calculation.
    Returns:
      {
          "position_factors": {symbol: {...}, ...},
          "aggregate": {...}
      }
    """
    positions = portfolio_snapshot.get("positions", [])
    pos_mapping = map_position_factors(positions)
    agg = aggregate_factors(pos_mapping, positions)

    return {
        "position_factors": pos_mapping,
        "aggregate": agg,
    }
