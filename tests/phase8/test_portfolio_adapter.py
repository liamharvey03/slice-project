import math

from voyager.intelligence.context.portfolio_adapter import (
    build_portfolio_snapshot,
    PortfolioAdapterError,
)


def test_build_portfolio_snapshot_weights_and_exposures():
    positions = [
        {"symbol": "AAPL", "quantity": 10, "price": 100.0},  # MV = 1000
        {"symbol": "MSFT", "quantity": 5, "price": 200.0},   # MV = 1000
        {"symbol": "TLT", "quantity": -2, "price": 150.0},   # MV = -300 (short)
    ]
    snapshot = build_portfolio_snapshot(positions)

    assert "positions" in snapshot
    assert "totals" in snapshot

    totals = snapshot["totals"]
    # portfolio value = sum of market values
    expected_portfolio_value = 1000.0 + 1000.0 - 300.0
    assert math.isclose(totals["portfolio_value"], expected_portfolio_value, rel_tol=1e-9)

    # gross exposure = sum of absolute market values
    expected_gross = abs(1000.0) + abs(1000.0) + abs(-300.0)
    assert math.isclose(totals["gross_exposure"], expected_gross, rel_tol=1e-9)

    # net exposure = sum of market values
    expected_net = 1000.0 + 1000.0 - 300.0
    assert math.isclose(totals["net_exposure"], expected_net, rel_tol=1e-9)

    # weights should sum to ~1 when portfolio_value > 0
    weights = [p["weight"] for p in snapshot["positions"]]
    assert all(isinstance(w, float) for w in weights)
    assert math.isclose(sum(weights), 1.0, rel_tol=1e-9)


def test_build_portfolio_snapshot_validation_errors():
    # Missing symbol
    with pytest.raises(PortfolioAdapterError):
        build_portfolio_snapshot([{"quantity": 1, "price": 100.0}])

    # Non-numeric quantity
    with pytest.raises(PortfolioAdapterError):
        build_portfolio_snapshot([{"symbol": "AAPL", "quantity": "x", "price": 100.0}])


# pytest import comes last to keep the top of file focused on SUT imports
import pytest  # noqa: E402
