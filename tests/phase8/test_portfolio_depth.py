import math

from slice.intelligence.context.portfolio_adapter import build_portfolio_snapshot
from slice.intelligence.context.concentration import compute_concentration
from slice.intelligence.context.factors import compute_factor_exposures


def test_concentration_and_factors_end_to_end():
    positions = [
        {"symbol": "AAPL", "quantity": 10, "price": 100.0},  # 1000
        {"symbol": "MSFT", "quantity": 5, "price": 200.0},   # 1000
        {"symbol": "TLT", "quantity": -2, "price": 150.0},   # -300
    ]

    snapshot = build_portfolio_snapshot(positions)

    # --- Concentration test ---
    conc = compute_concentration(snapshot)
    # largest weight ~ 1000 / 1700 = 0.588...
    assert conc["largest_weight"] > 0.58
    # top3 sum = 1 when portfolio value > 0
    assert math.isclose(conc["top3_sum"], 1.0, rel_tol=1e-9)
    # single-name-over-20 flag should trigger
    assert conc["flags"]["single_name_over_20"] is True
    assert conc["flags"]["top3_over_50"] is True

    # --- Factor test ---
    fx = compute_factor_exposures(snapshot)
    assert "position_factors" in fx
    assert "aggregate" in fx
    # Deterministic keys
    assert "beta_real_yield" in fx["aggregate"]
    assert "beta_dxy" in fx["aggregate"]
    assert "beta_growth" in fx["aggregate"]
