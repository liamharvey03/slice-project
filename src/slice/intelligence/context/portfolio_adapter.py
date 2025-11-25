from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Tuple


class PortfolioAdapterError(Exception):
    """Domain error for portfolio adapter issues."""
    pass


def _validate_positions(positions: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """Validate raw positions have the minimal required fields.

    Required keys per position:
      - symbol: str
      - quantity: float/int
      - price: float/int (current mark)

    Optional keys:
      - thesis_id: int/str
      - pnl: float
    """
    validated: List[Mapping[str, Any]] = []
    for idx, pos in enumerate(positions):
        if "symbol" not in pos:
            raise PortfolioAdapterError(f"Position {idx} missing 'symbol'")
        if "quantity" not in pos:
            raise PortfolioAdapterError(f"Position {idx} missing 'quantity'")
        if "price" not in pos:
            raise PortfolioAdapterError(f"Position {idx} missing 'price'")

        # basic type-ish checks (lenient, just to avoid obvious garbage)
        symbol = pos["symbol"]
        if not isinstance(symbol, str) or not symbol:
            raise PortfolioAdapterError(f"Position {idx} has invalid symbol={symbol!r}")

        # numeric-ish checks
        try:
            float(pos["quantity"])
            float(pos["price"])
        except (TypeError, ValueError):
            raise PortfolioAdapterError(
                f"Position {idx} has non-numeric quantity/price: "
                f"quantity={pos['quantity']!r}, price={pos['price']!r}"
            )

        validated.append(pos)
    return validated


def _compute_position_mv_and_weight(
    positions: List[Mapping[str, Any]]
) -> Tuple[List[Dict[str, Any]], float, float, float]:
    """Compute market value / weight / exposures for each position.

    Returns:
      - enriched_positions: list of dicts with market_value and weight added
      - portfolio_value: sum of market_values
      - gross_exposure: sum of abs(market_values)
      - net_exposure: sum of market_values
    """
    enriched: List[Dict[str, Any]] = []
    total_mv = 0.0
    gross = 0.0
    net = 0.0

    for pos in positions:
        qty = float(pos["quantity"])
        price = float(pos["price"])
        mv = qty * price

        total_mv += mv
        gross += abs(mv)
        net += mv

        enriched_pos: Dict[str, Any] = dict(pos)
        enriched_pos["market_value"] = mv
        # weight filled later once we know total_mv
        enriched.append(enriched_pos)

    if total_mv <= 0:
        # avoid divide-by-zero; no meaningful weights
        for p in enriched:
            p["weight"] = 0.0
    else:
        for p in enriched:
            p["weight"] = p["market_value"] / total_mv

    return enriched, total_mv, gross, net


def build_portfolio_snapshot(
    positions: Iterable[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Build a normalized portfolio snapshot from raw positions.

    Input: iterable of position dicts, each with (at minimum):
      - symbol: str
      - quantity: numeric
      - price: numeric (current mark)

    Output structure:
    {
        "positions": [
            {
                "symbol": str,
                "quantity": float,
                "price": float,
                "market_value": float,
                "weight": float,
                "thesis_id": Optional[Any],
                "pnl": Optional[float],
                ...
            },
            ...
        ],
        "totals": {
            "portfolio_value": float,
            "gross_exposure": float,
            "net_exposure": float,
        },
    }

    This function is intentionally pure and deterministic: no DB, no IO, no LLM.
    """
    validated = _validate_positions(positions)
    enriched, total_mv, gross, net = _compute_position_mv_and_weight(validated)

    snapshot: Dict[str, Any] = {
        "positions": enriched,
        "totals": {
            "portfolio_value": total_mv,
            "gross_exposure": gross,
            "net_exposure": net,
        },
    }
    return snapshot
