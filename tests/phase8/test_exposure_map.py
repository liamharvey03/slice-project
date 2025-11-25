import math

from slice.intelligence.context.portfolio_adapter import build_portfolio_snapshot
from slice.intelligence.context.exposure_map import build_exposure_map


def test_build_exposure_map_basic():
    positions = [
        {"symbol": "AAPL", "quantity": 10, "price": 100.0, "thesis_id": 1},  # 1000
        {"symbol": "MSFT", "quantity": 5,  "price": 200.0, "thesis_id": 1},  # 1000
        {"symbol": "TLT",  "quantity": -2, "price": 150.0, "thesis_id": 2},  # -300 (short)
        {"symbol": "SPY",  "quantity": 1,  "price": 50.0},                   # 50 (unassigned long)
    ]
    theses = [
        {"id": 1, "title": "Growth Tech"},
        {"id": 2, "title": "Rates Hedge"},
    ]

    snapshot = build_portfolio_snapshot(positions)
    exposure_map = build_exposure_map(theses, snapshot)

    assert "theses" in exposure_map
    assert "unassigned" in exposure_map

    theses_entries = {t["id"]: t for t in exposure_map["theses"]}

    # Thesis 1 should have AAPL + MSFT (both long)
    t1 = theses_entries[1]
    assert set(t1["positions"]) == {"AAPL", "MSFT"}
    assert t1["weight"] > 0.0  # long-only

    # Thesis 2 should have TLT which is short → negative weight
    t2 = theses_entries[2]
    assert set(t2["positions"]) == {"TLT"}
    assert t2["weight"] < 0.0  # MUST be negative

    # Unassigned SPY should be small positive weight
    unassigned = exposure_map["unassigned"]
    assert "SPY" in unassigned["positions"]
    assert unassigned["weight"] > 0.0

    # All weights sum to 1
    total_weight = t1["weight"] + t2["weight"] + unassigned["weight"]
    assert math.isclose(total_weight, 1.0, rel_tol=1e-9)
