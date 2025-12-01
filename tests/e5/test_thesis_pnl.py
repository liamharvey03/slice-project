"""
E5: Unit tests for DataAccess.get_thesis_pnl() helper.
"""
import pytest
from datetime import datetime

from slice.intelligence.context.data_access import DataAccess
from slice.models.execution import ThesisPnL
from slice.models.trade import Trade
from slice.models.common import TradeType
from slice.repositories.trade_repo import TradeRepository


class StubPriceSource:
    """Stub PriceSource with configurable current prices."""
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
    
    def list_by_thesis(self, thesis_id: str) -> list[Trade]:
        return [t for t in self.trades if t.thesis_ref == thesis_id]
    
    def insert(self, trade: Trade) -> Trade:
        self.trades.append(trade)
        return trade


@pytest.fixture
def stub_trade_repo():
    return StubTradeRepository()


@pytest.fixture
def price_source():
    return StubPriceSource({"A": 60.0})


@pytest.fixture
def data_access(stub_trade_repo, price_source):
    return DataAccess(
        thesis_repo=None,
        obs_repo=None,
        trade_repo=stub_trade_repo,
        price_source=price_source,
    )


def test_simple_long_only_pnl(data_access, stub_trade_repo):
    """Simple long-only: BUY 100 @ $50, price now $60 → P&L 20%."""
    # Create trade
    trade = Trade(
        trade_id="T1",
        timestamp=datetime.utcnow(),
        asset="A",
        action="BUY",
        quantity=100.0,
        price=50.0,
        type=TradeType.SIMULATED,
        thesis_ref="THESIS1",
    )
    stub_trade_repo.insert(trade)
    
    # Current price is 60
    pnl = data_access.get_thesis_pnl("THESIS1")
    
    assert pnl.thesis_id == "THESIS1"
    assert pnl.invested_notional == 5000.0  # 100 * 50
    assert pnl.current_value == 6000.0  # 100 * 60
    assert pnl.unrealized_pnl == 1000.0  # 6000 - 5000
    assert pnl.unrealized_pnl_pct == 20.0  # 1000 / 5000 * 100


def test_multiple_trades_same_asset(data_access, stub_trade_repo):
    """Multiple trades same asset → aggregated correctly."""
    # BUY 50 at 50, BUY 50 at 60
    trade1 = Trade(
        trade_id="T1",
        timestamp=datetime.utcnow(),
        asset="A",
        action="BUY",
        quantity=50.0,
        price=50.0,
        type=TradeType.SIMULATED,
        thesis_ref="THESIS2",
    )
    trade2 = Trade(
        trade_id="T2",
        timestamp=datetime.utcnow(),
        asset="A",
        action="BUY",
        quantity=50.0,
        price=60.0,
        type=TradeType.SIMULATED,
        thesis_ref="THESIS2",
    )
    stub_trade_repo.insert(trade1)
    stub_trade_repo.insert(trade2)
    
    # Current price is 55
    price_source = StubPriceSource({"A": 55.0})
    data_access.price_source = price_source
    
    pnl = data_access.get_thesis_pnl("THESIS2")
    
    assert pnl.invested_notional == 5500.0  # 50*50 + 50*60
    assert pnl.current_value == 5500.0  # 100*55
    assert pnl.unrealized_pnl == 0.0
    assert pnl.unrealized_pnl_pct == 0.0


def test_no_trades_returns_zeros(data_access):
    """No trades → zeros with unrealized_pnl_pct=None."""
    pnl = data_access.get_thesis_pnl("THESIS3")
    
    assert pnl.thesis_id == "THESIS3"
    assert pnl.invested_notional == 0.0
    assert pnl.current_value == 0.0
    assert pnl.unrealized_pnl == 0.0
    assert pnl.unrealized_pnl_pct is None


def test_multiple_assets_pnl(data_access, stub_trade_repo):
    """Multiple assets → P&L computed correctly."""
    price_source = StubPriceSource({"A": 60.0, "B": 220.0})
    data_access.price_source = price_source
    
    # Buy A and B
    trade_a = Trade(
        trade_id="T1",
        timestamp=datetime.utcnow(),
        asset="A",
        action="BUY",
        quantity=100.0,
        price=50.0,
        type=TradeType.SIMULATED,
        thesis_ref="THESIS4",
    )
    trade_b = Trade(
        trade_id="T2",
        timestamp=datetime.utcnow(),
        asset="B",
        action="BUY",
        quantity=20.0,
        price=200.0,
        type=TradeType.SIMULATED,
        thesis_ref="THESIS4",
    )
    stub_trade_repo.insert(trade_a)
    stub_trade_repo.insert(trade_b)
    
    pnl = data_access.get_thesis_pnl("THESIS4")
    
    assert pnl.invested_notional == 9000.0  # 100*50 + 20*200
    assert pnl.current_value == 10400.0  # 100*60 + 20*220
    assert pnl.unrealized_pnl == 1400.0
    assert abs(pnl.unrealized_pnl_pct - 15.56) < 0.1  # 1400/9000 * 100

