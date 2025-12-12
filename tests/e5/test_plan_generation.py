"""
E5: Unit tests for TradePlan generation (NaiveSizingEngine behavior).
"""
import pytest

from voyager.execution.paper import PaperExecutionAdapter
from voyager.models.thesis import Thesis, ThesisExpressionLeg
from voyager.models.common import Direction, ThesisStatus
from voyager.repositories.trade_repo import TradeRepository
from voyager.quant.price_source import PriceSource


class StubPriceSource:
    """Stub PriceSource for testing plan generation (not used in create_plan_from_thesis)."""
    def get_history(self, asset: str, start, end):
        raise NotImplementedError
    
    def get_current_price(self, asset: str) -> float:
        return 100.0


@pytest.fixture
def stub_price_source():
    return StubPriceSource()


@pytest.fixture
def stub_trade_repo():
    return TradeRepository()


@pytest.fixture
def adapter(stub_trade_repo, stub_price_source):
    return PaperExecutionAdapter(
        trade_repo=stub_trade_repo,
        price_source=stub_price_source,
    )


def test_basic_60_40_long_only_thesis(adapter):
    """Basic 60/40 long-only thesis → valid TradePlan."""
    thesis = Thesis(
        id="T1",
        title="Test",
        hypothesis="Test",
        drivers=["d1"],
        disconfirmers=["d1"],
        expression=[
            ThesisExpressionLeg(asset="A", direction=Direction.LONG, size_pct=60.0),
            ThesisExpressionLeg(asset="B", direction=Direction.LONG, size_pct=40.0),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    plan = adapter.create_plan_from_thesis(thesis, total_notional=10_000.0)
    
    assert plan.thesis_id == "T1"
    assert plan.total_notional == 10_000.0
    assert len(plan.legs) == 2
    
    leg_a = next(l for l in plan.legs if l.asset == "A")
    leg_b = next(l for l in plan.legs if l.asset == "B")
    
    assert leg_a.direction == "LONG"
    assert leg_a.size_pct == 60.0
    assert leg_b.direction == "LONG"
    assert leg_b.size_pct == 40.0


def test_allocations_sum_less_than_100(adapter):
    """Allocations sum < 100 → accepted (remaining = cash)."""
    thesis = Thesis(
        id="T2",
        title="Test",
        hypothesis="Test",
        drivers=["d1"],
        disconfirmers=["d1"],
        expression=[
            ThesisExpressionLeg(asset="A", direction=Direction.LONG, size_pct=50.0),
            ThesisExpressionLeg(asset="B", direction=Direction.LONG, size_pct=25.0),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    plan = adapter.create_plan_from_thesis(thesis, total_notional=10_000.0)
    
    assert len(plan.legs) == 2
    total_pct = sum(l.size_pct for l in plan.legs)
    assert total_pct == 75.0
    assert total_pct < 100.0


def test_allocations_sum_greater_than_100_error(adapter):
    """Allocations sum > 100 → ValueError."""
    thesis = Thesis(
        id="T3",
        title="Test",
        hypothesis="Test",
        drivers=["d1"],
        disconfirmers=["d1"],
        expression=[
            ThesisExpressionLeg(asset="A", direction=Direction.LONG, size_pct=70.0),
            ThesisExpressionLeg(asset="B", direction=Direction.LONG, size_pct=40.0),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    with pytest.raises(ValueError, match="must be <= 100"):
        adapter.create_plan_from_thesis(thesis, total_notional=10_000.0)


def test_short_leg_error(adapter):
    """Short leg → ValueError."""
    thesis = Thesis(
        id="T4",
        title="Test",
        hypothesis="Test",
        drivers=["d1"],
        disconfirmers=["d1"],
        expression=[
            ThesisExpressionLeg(asset="A", direction=Direction.SHORT, size_pct=50.0),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    with pytest.raises(ValueError, match="only supports long legs"):
        adapter.create_plan_from_thesis(thesis, total_notional=10_000.0)


def test_non_positive_notional_error(adapter):
    """Non-positive notional → ValueError."""
    thesis = Thesis(
        id="T5",
        title="Test",
        hypothesis="Test",
        drivers=["d1"],
        disconfirmers=["d1"],
        expression=[
            ThesisExpressionLeg(asset="A", direction=Direction.LONG, size_pct=50.0),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    with pytest.raises(ValueError, match="must be positive"):
        adapter.create_plan_from_thesis(thesis, total_notional=0.0)
    
    with pytest.raises(ValueError, match="must be positive"):
        adapter.create_plan_from_thesis(thesis, total_notional=-100.0)

