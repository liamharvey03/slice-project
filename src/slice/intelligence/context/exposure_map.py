from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .factors import compute_factor_exposures


def _normalize_thesis(thesis: Any) -> Dict[str, Any]:
    """
    Normalize a thesis object to a dict with at least:
      - id
      - title (optional, default 'thesis-{id}')
    Supports either:
      - dict-like objects
      - objects with .id / .title attributes
    """
    # dict-like
    if isinstance(thesis, Mapping):
        tid = thesis.get("id")
        title = thesis.get("title") or f"thesis-{tid}"
        return {"id": tid, "title": title}

    # object with attrs
    tid = getattr(thesis, "id", None)
    title = getattr(thesis, "title", None) or f"thesis-{tid}"
    return {"id": tid, "title": title}


def build_exposure_map(
    theses: Iterable[Any],
    portfolio_snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a cross-thesis exposure map.

    Inputs:
      - theses: iterable of thesis objects (dict-like or with .id/.title)
      - portfolio_snapshot: output of build_portfolio_snapshot(...)

    Assumptions:
      - portfolio positions may contain "thesis_id" pointing to a thesis id.
      - factor betas are derived via compute_factor_exposures(...) for each symbol.

    Output:
      {
          "theses": [
              {
                  "id": thesis_id,
                  "title": str,
                  "weight": float,  # sum of position weights tagged to this thesis
                  "factor_exposures": {
                      "beta_real_yield": float,
                      "beta_dxy": float,
                      "beta_growth": float,
                  },
                  "positions": [symbol, ...],
              },
              ...
          ],
          "unassigned": {
              "weight": float,
              "positions": [symbol, ...],
          },
      }
    """
    normalized_theses: List[Dict[str, Any]] = [_normalize_thesis(t) for t in theses]
    thesis_index: Dict[Any, Dict[str, Any]] = {
        t["id"]: {**t, "weight": 0.0, "positions": [], "factor_exposures": {
            "beta_real_yield": 0.0,
            "beta_dxy": 0.0,
            "beta_growth": 0.0,
        }}
        for t in normalized_theses
    }

    positions: List[Dict[str, Any]] = portfolio_snapshot.get("positions", [])
    factor_data = compute_factor_exposures(portfolio_snapshot)
    position_factors: Dict[str, Dict[str, float]] = factor_data.get("position_factors", {})

    unassigned_weight = 0.0
    unassigned_positions: List[str] = []

    for pos in positions:
        sym = pos["symbol"]
        w = float(pos.get("weight", 0.0))
        thesis_id = pos.get("thesis_id")

        betas = position_factors.get(sym, {
            "beta_real_yield": 0.0,
            "beta_dxy": 0.0,
            "beta_growth": 0.0,
        })

        if thesis_id in thesis_index:
            entry = thesis_index[thesis_id]
            entry["weight"] += w
            entry["positions"].append(sym)
            # accumulate factor exposures weighted by position weight
            entry["factor_exposures"]["beta_real_yield"] += betas.get("beta_real_yield", 0.0) * w
            entry["factor_exposures"]["beta_dxy"] += betas.get("beta_dxy", 0.0) * w
            entry["factor_exposures"]["beta_growth"] += betas.get("beta_growth", 0.0) * w
        else:
            unassigned_weight += w
            unassigned_positions.append(sym)

    return {
        "theses": list(thesis_index.values()),
        "unassigned": {
            "weight": unassigned_weight,
            "positions": unassigned_positions,
        },
    }
