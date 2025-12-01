"""
E5: Integration tests for approve-plan endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock

from slice.api.main import app
from slice.repositories.thesis_repo import ThesisRepository
from slice.repositories.trade_repo import TradeRepository
from slice.intelligence.context.data_access import DataAccess
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.common import Direction, ThesisStatus
from slice.api.deps import get_price_source_instance
import slice.api.session_routes_e4 as routes_mod


class StubPriceSource:
    """Stub PriceSource with configurable prices."""
    def __init__(self, prices: dict[str, float] | None = None):
        self.prices = prices or {"GLD": 200.0, "SLV": 25.0}
    
    def get_history(self, asset: str, start, end):
        raise NotImplementedError
    
    def get_current_price(self, asset: str) -> float:
        if asset not in self.prices:
            raise ValueError(f"No price configured for {asset}")
        return self.prices[asset]


@pytest.fixture
def test_thesis(db_engine, clean_core_tables):
    """Create a test thesis in the database."""
    thesis = Thesis(
        id="TEST_T1",
        title="Test Thesis",
        hypothesis="Test hypothesis",
        drivers=["driver1"],
        disconfirmers=["disconf1"],
        expression=[
            ThesisExpressionLeg(
                asset="GLD",
                direction=Direction.LONG,
                size_pct=60.0,
            ),
            ThesisExpressionLeg(
                asset="SLV",
                direction=Direction.LONG,
                size_pct=40.0,
            ),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    repo = ThesisRepository(engine=db_engine)
    repo.insert(thesis)
    return thesis


@pytest.fixture
def test_thesis_short(db_engine, clean_core_tables):
    """Create a test thesis with SHORT leg."""
    thesis = Thesis(
        id="TEST_T2",
        title="Short Thesis",
        hypothesis="Test",
        drivers=["d1"],
        disconfirmers=["d1"],
        expression=[
            ThesisExpressionLeg(
                asset="GLD",
                direction=Direction.SHORT,
                size_pct=50.0,
            ),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    repo = ThesisRepository(engine=db_engine)
    repo.insert(thesis)
    return thesis


@pytest.fixture
def test_thesis_active(db_engine, clean_core_tables):
    """Create an already ACTIVE test thesis."""
    thesis = Thesis(
        id="TEST_T3",
        title="Active Thesis",
        hypothesis="Test",
        drivers=["d1"],
        disconfirmers=["d1"],
        expression=[
            ThesisExpressionLeg(
                asset="GLD",
                direction=Direction.LONG,
                size_pct=100.0,
            ),
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
    )
    
    repo = ThesisRepository(engine=db_engine)
    repo.insert(thesis)
    return thesis


@pytest.fixture
def price_source():
    return StubPriceSource()


@pytest.fixture
def client(db_engine, price_source):
    """Test client with dependency overrides."""
    # Override price source
    app.dependency_overrides[get_price_source_instance] = lambda: price_source
    
    # Create data access with real repos
    from slice.repositories.observation_repo import ObservationRepository
    from slice.repositories.evaluation_repo import EvaluationRepository
    from slice.repositories.alert_repo import AlertRepository
    from slice.repositories.daily_summary_repo import DailySummaryRepository
    
    thesis_repo = ThesisRepository(engine=db_engine)
    obs_repo = ObservationRepository(engine=db_engine)
    trade_repo = TradeRepository(engine=db_engine)
    eval_repo = EvaluationRepository(engine=db_engine)
    alert_repo = AlertRepository(engine=db_engine)
    daily_summary_repo = DailySummaryRepository(engine=db_engine)
    
    data_access = DataAccess(
        thesis_repo=thesis_repo,
        obs_repo=obs_repo,
        trade_repo=trade_repo,
        price_source=price_source,
        evaluation_repo=eval_repo,
        alert_repo=alert_repo,
        daily_summary_repo=daily_summary_repo,
    )
    
    app.dependency_overrides[DataAccess.depends] = lambda: data_access
    
    yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


def test_happy_path(client, test_thesis, db_engine):
    """Happy path: 200, trades created, thesis ACTIVE, portfolio updated."""
    response = client.post(
        f"/api/v1/thesis/{test_thesis.id}/approve-plan",
        json={"total_notional": 50_000.0},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert data["thesis_id"] == test_thesis.id
    assert data["total_notional"] == 50_000.0
    assert len(data["executed_trades"]) == 2
    
    # Check trades in repo
    trade_repo = TradeRepository(engine=db_engine)
    trades = trade_repo.list_by_thesis(test_thesis.id)
    assert len(trades) == 2
    
    trade_gld = next(t for t in trades if t.asset == "GLD")
    trade_slv = next(t for t in trades if t.asset == "SLV")
    
    # GLD: 60% of 50k = 30k, price 200 → quantity 150
    assert abs(trade_gld.quantity - 150.0) < 0.01
    assert trade_gld.action == "BUY"
    
    # SLV: 40% of 50k = 20k, price 25 → quantity 800
    assert abs(trade_slv.quantity - 800.0) < 0.01
    assert trade_slv.action == "BUY"
    
    # Check thesis is ACTIVE
    thesis_repo = ThesisRepository(engine=db_engine)
    updated_thesis = thesis_repo.get_by_id(test_thesis.id)
    assert updated_thesis.status == ThesisStatus.ACTIVE
    
    # Check portfolio updated
    from slice.repositories.observation_repo import ObservationRepository
    from slice.repositories.evaluation_repo import EvaluationRepository
    from slice.repositories.alert_repo import AlertRepository
    from slice.repositories.daily_summary_repo import DailySummaryRepository
    
    data_access = DataAccess(
        thesis_repo=ThesisRepository(engine=db_engine),
        obs_repo=ObservationRepository(engine=db_engine),
        trade_repo=trade_repo,
        price_source=StubPriceSource({"GLD": 200.0, "SLV": 25.0}),
        evaluation_repo=EvaluationRepository(engine=db_engine),
        alert_repo=AlertRepository(engine=db_engine),
        daily_summary_repo=DailySummaryRepository(engine=db_engine),
    )
    portfolio = data_access.get_current_portfolio()
    assert len(portfolio.positions) == 2


def test_double_approval_blocked(client, test_thesis, db_engine):
    """Double approval → 400 "already active"."""
    # First approval
    response1 = client.post(
        f"/api/v1/thesis/{test_thesis.id}/approve-plan",
        json={"total_notional": 50_000.0},
    )
    assert response1.status_code == 200
    
    # Count trades after first approval
    trade_repo = TradeRepository(engine=db_engine)
    trades_after_first = trade_repo.list_by_thesis(test_thesis.id)
    trade_count_after_first = len(trades_after_first)
    
    # Second approval should fail
    response2 = client.post(
        f"/api/v1/thesis/{test_thesis.id}/approve-plan",
        json={"total_notional": 50_000.0},
    )
    assert response2.status_code == 400
    assert "already active" in response2.json()["detail"].lower()
    
    # Trade count should be unchanged
    trades_after_second = trade_repo.list_by_thesis(test_thesis.id)
    assert len(trades_after_second) == trade_count_after_first


def test_short_thesis_not_allowed(client, test_thesis_short):
    """Short thesis → 400."""
    response = client.post(
        f"/api/v1/thesis/{test_thesis_short.id}/approve-plan",
        json={"total_notional": 50_000.0},
    )
    
    assert response.status_code == 400
    assert "short" in response.json()["detail"].lower() or "long" in response.json()["detail"].lower()


def test_missing_thesis(client):
    """Missing thesis → 404."""
    response = client.post(
        "/api/v1/thesis/NONEXISTENT/approve-plan",
        json={"total_notional": 50_000.0},
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_bad_price_error(client, test_thesis, db_engine):
    """Bad price → 500."""
    # Create price source that raises error
    bad_price_source = StubPriceSource({"GLD": 0.0, "SLV": 25.0})
    app.dependency_overrides[get_price_source_instance] = lambda: bad_price_source
    
    response = client.post(
        f"/api/v1/thesis/{test_thesis.id}/approve-plan",
        json={"total_notional": 50_000.0},
    )
    
    assert response.status_code == 500
    assert "execution failed" in response.json()["detail"].lower() or "invalid price" in response.json()["detail"].lower()
    
    # Cleanup
    app.dependency_overrides.clear()


def test_default_notional(client, test_thesis, db_engine):
    """Default notional (100k) used when not provided."""
    response = client.post(
        f"/api/v1/thesis/{test_thesis.id}/approve-plan",
        json={},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_notional"] == 100_000.0


def test_already_active_thesis_error(client, test_thesis_active):
    """Thesis already ACTIVE → 400."""
    response = client.post(
        f"/api/v1/thesis/{test_thesis_active.id}/approve-plan",
        json={"total_notional": 50_000.0},
    )
    
    assert response.status_code == 400
    assert "already active" in response.json()["detail"].lower()

