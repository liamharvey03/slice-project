from slice.intelligence.context.macro_adapter import build_macro_snapshot, compute_regimes


def test_build_macro_snapshot_and_regimes():
    latest = {
        "pmi": 54.0,
        "payrolls_3m_avg": 250_000,
        "cpi_yoy": 5.5,
        "core_cpi_yoy": 4.8,
        "us_2y_yield": 4.5,
        "us_10y_yield": 4.0,
        "real_10y_yield": 2.0,
        "on_rrp": 1.0e12,
        "reserves": 8.0e11,
        "tga": 5.0e11,
        "dxy": 112.0,
        "eurusd": 1.05,
    }

    snapshot = build_macro_snapshot(latest)
    assert "growth" in snapshot
    assert "inflation" in snapshot
    assert "rates" in snapshot
    assert "liquidity" in snapshot
    assert "fx" in snapshot

    # Sanity checks on grouping
    assert snapshot["growth"]["pmi"] == 54.0
    assert snapshot["inflation"]["core_cpi_yoy"] == 4.8
    assert snapshot["rates"]["us_2y_yield"] == 4.5
    assert snapshot["fx"]["dxy"] == 112.0

    regimes = compute_regimes(snapshot)
    assert regimes["growth"] == "expansion"
    assert regimes["inflation"] == "high"
    # reserves < on_rrp → liq_index <= 0 → tight
    assert regimes["liquidity"] == "tight"
    assert regimes["usd"] == "strong"


def test_macro_adapter_handles_missing_values():
    latest = {
        "pmi": 49.0,
        # no inflation keys, no fx keys, etc.
    }

    snapshot = build_macro_snapshot(latest)
    regimes = compute_regimes(snapshot)

    # Growth with pmi=49 should be slowdown
    assert regimes["growth"] == "slowdown"

    # Missing inflation/fx/liquidity data -> unknown
    assert regimes["inflation"] == "unknown"
    assert regimes["liquidity"] == "unknown"
    assert regimes["usd"] == "unknown"
