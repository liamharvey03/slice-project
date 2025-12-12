from datetime import date
from typing import Dict

import pandas as pd
import pytest
from pydantic import ValidationError

from voyager.evaluation.thesis_evaluation import ThesisEvaluationService
from voyager.models.common import Direction, ThesisStatus
from voyager.models.thesis import Thesis, ThesisExpressionLeg


class FakePriceSource:
    """
    Simple in-memory PriceSource implementation for tests.

    It ignores the requested date window and just returns the preconfigured
    series for each asset. Tests control the index and values directly.
    """

    def __init__(self, series_by_asset: Dict[str, pd.Series]) -> None:
        self._series_by_asset = series_by_asset

    def get_history(self, asset: str, start: date, end: date) -> pd.Series:
        return self._series_by_asset.get(asset, pd.Series(dtype=float))

    def get_current_price(self, asset: str) -> float:
        series = self._series_by_asset[asset]
        return float(series.iloc[-1])


def _make_basic_thesis_single_leg(
    asset: str,
    direction: Direction,
    size_pct: float,
    start_date: str,
    review_date: str,
) -> Thesis:
    """
    Helper to build a minimal valid Thesis for tests.
    """
    return Thesis(
        id=1,
        title="Test Thesis",
        hypothesis="Test hypothesis",
        drivers=["driver"],
        disconfirmers=["disconfirmer"],
        expression=[
            ThesisExpressionLeg(
                asset=asset,
                direction=direction,
                size_pct=size_pct,
            )
        ],
        start_date=start_date,
        review_date=review_date,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
        notes=None,
    )


def test_single_asset_monotonic_up():
    """
    100% long in an asset that goes up monotonically.

    Expectations:
      - total_return > 0
      - max_drawdown approximately 0
      - timeseries length matches price series length
      - initial equity value ~ 1.0
      - max_weight_pct == 100
    """
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    prices = pd.Series([100.0 + i for i in range(10)], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.LONG,
        size_pct=100.0,
        start_date="2020-01-01",
        review_date="2020-01-10",
    )

    result = service.evaluate_thesis(thesis)

    perf = result.performance
    risk = result.risk_metrics

    # strictly positive performance
    assert perf["total_return"] > 0.0

    # monotonic up -> max drawdown should be effectively zero
    assert abs(perf["max_drawdown"]) < 1e-6

    # risk metrics
    assert risk["max_weight_pct"] == 100.0

    # equity curve timeseries sanity
    assert len(result.timeseries) == len(idx)
    assert abs(result.timeseries[0].value - 1.0) < 1e-6


def test_single_asset_monotonic_down():
    """
    100% long in an asset that goes down monotonically.

    Expectations:
      - total_return < 0
      - max_drawdown ~ |total_return| (no recovery)
    """
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    prices = pd.Series([100.0 - i for i in range(10)], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.LONG,
        size_pct=100.0,
        start_date="2020-01-01",
        review_date="2020-01-10",
    )

    result = service.evaluate_thesis(thesis)

    perf = result.performance

    assert perf["total_return"] < 0.0
    # monotonic down -> max drawdown should match |total_return|
    assert perf["max_drawdown"] > 0.0
    assert abs(perf["max_drawdown"] - abs(perf["total_return"])) < 1e-6


def test_two_assets_offsetting_returns():
    """
    50% long asset A (up) and 50% long asset B (down) with symmetric daily
    moves: portfolio should be approximately flat.
    """
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    prices_a = pd.Series([100.0 * (1.1 ** i) for i in range(10)], index=idx)
    prices_b = pd.Series([100.0 * (0.9 ** i) for i in range(10)], index=idx)

    price_source = FakePriceSource({"A": prices_a, "B": prices_b})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = Thesis(
        id=2,
        title="Two-asset offset",
        hypothesis="",
        drivers=["d"],
        disconfirmers=["dc"],
        expression=[
            ThesisExpressionLeg(
                asset="A",
                direction=Direction.LONG,
                size_pct=50.0,
            ),
            ThesisExpressionLeg(
                asset="B",
                direction=Direction.LONG,
                size_pct=50.0,
            ),
        ],
        start_date="2020-01-01",
        review_date="2020-01-10",
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
        notes=None,
    )

    result = service.evaluate_thesis(thesis)
    perf = result.performance
    risk = result.risk_metrics

    assert abs(perf["total_return"]) < 1e-4
    assert risk["max_weight_pct"] == 50.0


def test_single_asset_short_position():
    """
    100% short an asset that goes up.

    Expectations:
      - total_return < 0
      - All -10% scenario => positive P&L
      - All +10% scenario => negative P&L
    """
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    prices = pd.Series([100.0 + i for i in range(10)], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.SHORT,
        size_pct=100.0,
        start_date="2020-01-01",
        review_date="2020-01-10",
    )

    result = service.evaluate_thesis(thesis)
    perf = result.performance
    scenarios = {s.name: s for s in result.scenarios}

    assert perf["total_return"] < 0.0

    assert "All -10%" in scenarios
    assert "All +10%" in scenarios

    down = scenarios["All -10%"]
    up = scenarios["All +10%"]

    # For a 100% short, -10% price shock => +10% P&L; +10% shock => -10% P&L
    assert pytest.approx(down.pnl_pct, rel=1e-3) == 10.0
    assert pytest.approx(up.pnl_pct, rel=1e-3) == -10.0


def test_partial_cash_allocation():
    """
    50% long in a doubling asset, 50% cash.

    Asset return: +100% => portfolio return ~ +50%.
    """
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    prices = pd.Series([100.0, 200.0], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.LONG,
        size_pct=50.0,
        start_date="2020-01-01",
        review_date="2020-01-02",
    )

    result = service.evaluate_thesis(thesis)
    perf = result.performance
    risk = result.risk_metrics

    assert pytest.approx(perf["total_return"], rel=1e-6) == 50.0
    assert risk["max_weight_pct"] == 50.0


def test_scenarios_all_plus_minus_10_present():
    """
    Basic sanity: scenarios should contain 'All -10%' and 'All +10%' for a
    simple 100% long thesis.
    """
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = pd.Series([100.0 + i for i in range(5)], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.LONG,
        size_pct=100.0,
        start_date="2020-01-01",
        review_date="2020-01-05",
    )

    result = service.evaluate_thesis(thesis)
    scenario_names = {s.name for s in result.scenarios}

    assert "All -10%" in scenario_names
    assert "All +10%" in scenario_names
    assert len(result.scenarios) >= 2


def test_weights_exceed_100_raises():
    """
    Two legs whose size_pct sum to more than 100% should be rejected.
    """
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    prices_a = pd.Series([100.0 + i for i in range(5)], index=idx)
    prices_b = pd.Series([50.0 + i for i in range(5)], index=idx)

    price_source = FakePriceSource({"A": prices_a, "B": prices_b})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = Thesis(
        id=3,
        title="Overallocated",
        hypothesis="",
        drivers=["d"],
        disconfirmers=["dc"],
        expression=[
            ThesisExpressionLeg(
                asset="A",
                direction=Direction.LONG,
                size_pct=60.0,
            ),
            ThesisExpressionLeg(
                asset="B",
                direction=Direction.LONG,
                size_pct=50.0,
            ),
        ],
        start_date="2020-01-01",
        review_date="2020-01-05",
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
        notes=None,
    )

    with pytest.raises(ValueError) as excinfo:
        service.evaluate_thesis(thesis)

    assert "exceeds 100%" in str(excinfo.value)


def test_empty_expression_raises():
    """
    A thesis with no expression legs should be rejected at the model level.

    The Thesis model itself enforces non-empty expression, so constructing such
    a Thesis should raise a ValidationError before the evaluation service runs.
    """
    with pytest.raises(ValidationError) as excinfo:
        Thesis(
            id=4,
            title="No legs",
            hypothesis="",
            drivers=["d"],
            disconfirmers=["dc"],
            expression=[],
            start_date="2020-01-01",
            review_date="2020-01-05",
            status=ThesisStatus.ACTIVE,
            tags=[],
            monitor_indices=["SPX"],
            notes=None,
        )

    assert "expression cannot be empty" in str(excinfo.value)


def test_missing_price_data_raises():
    """
    If the PriceSource returns an empty series for any asset, evaluation should
    fail with a clear error.
    """
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = pd.Series([100.0 + i for i in range(5)], index=idx)

    # Only A has data; B is missing
    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = Thesis(
        id=5,
        title="Missing price",
        hypothesis="",
        drivers=["d"],
        disconfirmers=["dc"],
        expression=[
            ThesisExpressionLeg(
                asset="A",
                direction=Direction.LONG,
                size_pct=50.0,
            ),
            ThesisExpressionLeg(
                asset="B",
                direction=Direction.LONG,
                size_pct=50.0,
            ),
        ],
        start_date="2020-01-01",
        review_date="2020-01-05",
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
        notes=None,
    )

    with pytest.raises(ValueError) as excinfo:
        service.evaluate_thesis(thesis)

    assert "No price data for asset B" in str(excinfo.value)


def test_var_95_for_constant_minus_10_returns():
    """
    If the portfolio has a constant -10% daily return, the 5% quantile of
    returns is -10%, so VaR_95 should be approximately 10.
    """
    idx = pd.date_range("2020-01-01", periods=6, freq="D")
    prices = pd.Series([100.0 * (0.9 ** i) for i in range(len(idx))], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.LONG,
        size_pct=100.0,
        start_date="2020-01-01",
        review_date="2020-01-06",
    )

    result = service.evaluate_thesis(thesis)
    risk = result.risk_metrics

    assert pytest.approx(risk["VaR_95"], rel=1e-3) == 10.0


def test_risk_max_drawdown_pct_matches_performance():
    """
    Path engineered so that max drawdown is exactly 25%:
    prices: 100 -> 200 -> 150 -> 300
    equity: 1.0 -> 2.0 -> 1.5 -> 3.0
    max DD = (1.5 / 2.0 - 1) = -25%.
    """
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    prices = pd.Series([100.0, 200.0, 150.0, 300.0], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.LONG,
        size_pct=100.0,
        start_date="2020-01-01",
        review_date="2020-01-04",
    )

    result = service.evaluate_thesis(thesis)
    perf = result.performance
    risk = result.risk_metrics

    assert pytest.approx(perf["max_drawdown"], rel=1e-6) == 25.0
    assert pytest.approx(risk["max_drawdown_pct"], rel=1e-6) == 25.0


def test_scenario_pnl_abs_uses_final_equity():
    """
    For a flat price path (no P&L yet), final equity ~1.0 for a 100% long leg.
    A +10% shock should produce:
      - pnl_pct ~ +10
      - pnl_abs ~ 0.10 * final_equity
    """
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = pd.Series([100.0] * len(idx), index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    thesis = _make_basic_thesis_single_leg(
        asset="A",
        direction=Direction.LONG,
        size_pct=100.0,
        start_date="2020-01-01",
        review_date="2020-01-05",
    )

    result = service.evaluate_thesis(thesis)

    base_equity = result.timeseries[-1].value
    assert pytest.approx(base_equity, rel=1e-6) == 1.0
    assert pytest.approx(result.performance["total_return"], abs=1e-6) == 0.0

    scenarios = {s.name: s for s in result.scenarios}
    up = scenarios["All +10%"]

    assert pytest.approx(up.pnl_pct, rel=1e-6) == 10.0
    assert pytest.approx(up.pnl_abs, rel=1e-6) == base_equity * 0.10


def test_invalid_direction_raises_value_error_from_service():
    """
    If a Thesis somehow contains a leg with an invalid direction value, the
    ThesisEvaluationService should raise a ValueError during validation.

    We bypass Pydantic validation using `.construct()` to simulate a corrupted
    Thesis object.
    """
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = pd.Series([100.0 + i for i in range(5)], index=idx)

    price_source = FakePriceSource({"A": prices})
    service = ThesisEvaluationService(price_source=price_source)

    bad_leg = ThesisExpressionLeg.construct(
        asset="A",
        direction="INVALID",
        size_pct=100.0,
    )

    thesis = Thesis.construct(
        id=6,
        title="Bad direction",
        hypothesis="",
        drivers=["d"],
        disconfirmers=["dc"],
        expression=[bad_leg],
        start_date="2020-01-01",
        review_date="2020-01-05",
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
        notes=None,
    )

    with pytest.raises(ValueError) as excinfo:
        service.evaluate_thesis(thesis)

    assert "Invalid direction for asset A" in str(excinfo.value)