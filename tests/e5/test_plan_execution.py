"""
E5: Unit tests for TradePlan execution.
"""
import pytest
from datetime import date, datetime
from unittest.mock import Mock

from slice.execution.paper import PaperExecutionAdapter
from slice.models.execution import TradePlan, TradeLeg
from slice.models.trade import Trade
from slice.models.common import TradeType
from slice.repositories.trade_repo import TradeRepository


class StubPriceSource:
    """Stub PriceSource with configurable prices."""
    def __init__(self, prices: dict[str, float]):
        self.prices = prices
    
    def get_history(self, asset: str, start, end):
        raise NotImplementedError
    
    def get_current_price(self, asset: str) -> float:
        if asset not in self.prices:
            raise ValueError(f"No price configured for {asset}")
        return self.prices[asset]


class StubTradeRepository:
    """In-memory TradeRepository for testing."""
    def __init__(self):
        self.trades: list[Trade] = []
    
    def insert(self, trade: Trade) -> Trade:
        self.trades.append(trade)
        return trade
    
    def list_by_thesis(self, thesis_id: str) -> list[Trade]:
        return [t for t in self.trades if t.thesis_ref == thesis_id]


@pytest.fixture
def stub_trade_repo():
    return StubTradeRepository()


@pytest.fixture
def price_source():
    return StubPriceSource({"A": 50.0, "B": 200.0})


@pytest.fixture
def adapter(stub_trade_repo, price_source):
    return PaperExecutionAdapter(
        trade_repo=stub_trade_repo,
        price_source=price_source,
    )


def test_two_leg_execution_long_only(adapter, stub_trade_repo):
    """Two-leg execution, long-only → correct Trade quantities."""
    plan = TradePlan(
        thesis_id="T1",
        total_notional=10_000.0,
        legs=[
            TradeLeg(asset="A", direction="LONG", size_pct=60.0),
            TradeLeg(asset="B", direction="LONG", size_pct=40.0),
        ],
    )
    
    trades = adapter.execute_plan(plan)
    
    assert len(trades) == 2
    assert len(stub_trade_repo.trades) == 2
    
    trade_a = next(t for t in trades if t.asset == "A")
    trade_b = next(t for t in trades if t.asset == "B")
    
    # A: 60% of 10k = 6k, price 50 → quantity 120
    assert trade_a.asset == "A"
    assert trade_a.action == "BUY"
    assert trade_a.type == TradeType.SIMULATED
    assert trade_a.thesis_ref == "T1"
    assert abs(trade_a.quantity - 120.0) < 0.01
    assert trade_a.price == 50.0
    
    # B: 40% of 10k = 4k, price 200 → quantity 20
    assert trade_b.asset == "B"
    assert trade_b.action == "BUY"
    assert trade_b.type == TradeType.SIMULATED
    assert trade_b.thesis_ref == "T1"
    assert abs(trade_b.quantity - 20.0) < 0.01
    assert trade_b.price == 200.0


def test_zero_sized_legs_filtered(adapter, stub_trade_repo):
    """Zero-sized legs filtered (no Trade inserted)."""
    plan = TradePlan(
        thesis_id="T2",
        total_notional=10_000.0,
        legs=[
            TradeLeg(asset="A", direction="LONG", size_pct=50.0),
            TradeLeg(asset="B", direction="LONG", size_pct=0.0),  # Zero-sized
        ],
    )
    
    trades = adapter.execute_plan(plan)
    
    assert len(trades) == 1
    assert len(stub_trade_repo.trades) == 1
    assert trades[0].asset == "A"


def test_bad_price_error(adapter):
    """Bad price (0 or negative) → RuntimeError."""
    bad_price_source = StubPriceSource({"A": 0.0})
    bad_adapter = PaperExecutionAdapter(
        trade_repo=StubTradeRepository(),
        price_source=bad_price_source,
    )
    
    plan = TradePlan(
        thesis_id="T3",
        total_notional=10_000.0,
        legs=[
            TradeLeg(asset="A", direction="LONG", size_pct=50.0),
        ],
    )
    
    with pytest.raises(RuntimeError, match="Invalid price"):
        bad_adapter.execute_plan(plan)
    
    # Negative price
    bad_price_source2 = StubPriceSource({"A": -10.0})
    bad_adapter2 = PaperExecutionAdapter(
        trade_repo=StubTradeRepository(),
        price_source=bad_price_source2,
    )
    
    with pytest.raises(RuntimeError, match="Invalid price"):
        bad_adapter2.execute_plan(plan)


def test_execute_plan_with_as_of_date(adapter, stub_trade_repo):
    """Execute plan with as_of date → trades have that timestamp."""
    plan = TradePlan(
        thesis_id="T4",
        total_notional=10_000.0,
        legs=[
            TradeLeg(asset="A", direction="LONG", size_pct=100.0),
        ],
    )
    
    as_of = date(2024, 1, 15)
    trades = adapter.execute_plan(plan, as_of=as_of)
    
    assert len(trades) == 1
    expected_dt = datetime.combine(as_of, datetime.min.time())
    assert trades[0].timestamp == expected_dt


def test_empty_plan_no_trades(adapter, stub_trade_repo):
    """Empty plan → no trades."""
    plan = TradePlan(
        thesis_id="T5",
        total_notional=10_000.0,
        legs=[],
    )
    
    trades = adapter.execute_plan(plan)
    
    assert len(trades) == 0
    assert len(stub_trade_repo.trades) == 0

