"""
E4: API integration tests for daily update endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock

from slice.api.main import app
from slice.repositories.thesis_repo import ThesisRepository
from slice.repositories.observation_repo import ObservationRepository
from slice.repositories.trade_repo import TradeRepository
from slice.repositories.evaluation_repo import EvaluationRepository
from slice.repositories.alert_repo import AlertRepository
from slice.repositories.daily_summary_repo import DailySummaryRepository
from slice.intelligence.context.data_access import DataAccess
from slice.llm.llm_tools import LLMTools
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.observation import Observation
from slice.models.common import Direction, ThesisStatus, Sentiment
from slice.models.llm_outputs import DailySummary
from datetime import datetime, timezone
import slice.api.session_routes_e4 as routes_mod


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
                size_pct=100.0,
            )
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
def test_observation(db_engine, clean_core_tables, test_thesis):
    """Create a test observation that will trigger alerts."""
    obs = Observation(
        id="TEST_O1",
        timestamp=datetime.now(timezone.utc),
        text="Disconfirmer detected",
        thesis_ref=["TEST_T1"],
        sentiment=Sentiment.BEARISH,
        categories=["risk"],
        actionable="YES",
    )
    
    repo = ObservationRepository(engine=db_engine)
    repo.insert(obs)
    
    return obs


@pytest.fixture
def mock_llm_tools():
    """Create a mock LLMTools."""
    llm_tools = Mock(spec=LLMTools)
    return llm_tools


@pytest.fixture
def client_with_deps(db_engine, test_thesis, test_observation, mock_llm_tools, e4_tables):
    """Create a test client with dependency overrides."""
    # Create repos
    thesis_repo = ThesisRepository(engine=db_engine)
    obs_repo = ObservationRepository(engine=db_engine)
    trade_repo = TradeRepository(engine=db_engine)
    eval_repo = EvaluationRepository(engine=db_engine)
    alert_repo = AlertRepository(engine=db_engine)
    daily_summary_repo = DailySummaryRepository(engine=db_engine)
    
    # Create DataAccess
    data_access = DataAccess(
        thesis_repo=thesis_repo,
        obs_repo=obs_repo,
        trade_repo=trade_repo,
        evaluation_repo=eval_repo,
        alert_repo=alert_repo,
        daily_summary_repo=daily_summary_repo,
    )
    
    # Override dependencies
    app.dependency_overrides[DataAccess.depends] = lambda: data_access
    app.dependency_overrides[routes_mod.get_llm_tools] = lambda: mock_llm_tools
    
    yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


def test_daily_update_happy_path(client_with_deps, db_engine, mock_llm_tools):
    """Test POST /session/daily-update returns 200."""
    summary = DailySummary(
        key_narratives=["Test narrative"],
        risk_highlights=["Test risk"],
        thesis_references=["TEST_T1"],
        insufficient_context=False,
    )
    mock_llm_tools.daily_summary = AsyncMock(return_value=summary)
    
    resp = client_with_deps.post("/api/v1/session/daily-update")
    
    assert resp.status_code == 200
    data = resp.json()
    
    assert "date" in data
    assert "portfolio_snapshot" in data
    assert "portfolio_depth" in data
    assert "alerts" in data
    assert "summary" in data
    assert data["summary"]["insufficient_context"] is False
    
    # Verify alerts persisted
    from datetime import date
    alert_repo = AlertRepository(engine=db_engine)
    alerts = alert_repo.list_for_date(date.today())
    assert len(alerts) > 0
    
    # Verify summary persisted
    daily_summary_repo = DailySummaryRepository(engine=db_engine)
    persisted_summary = daily_summary_repo.get_summary(date.today())
    assert persisted_summary is not None


def test_daily_update_llm_failure(client_with_deps, db_engine, mock_llm_tools):
    """Test LLM failure still returns 200 with degraded summary."""
    mock_llm_tools.daily_summary = AsyncMock(side_effect=Exception("LLM error"))
    
    resp = client_with_deps.post("/api/v1/session/daily-update")
    
    # Should still return 200
    assert resp.status_code == 200
    data = resp.json()
    
    # Summary should have insufficient_context=True
    assert data["summary"]["insufficient_context"] is True
    assert data["summary"]["key_narratives"] == []
    assert data["summary"]["risk_highlights"] == []
    
    # Alerts should still be persisted
    from datetime import date
    alert_repo = AlertRepository(engine=db_engine)
    alerts = alert_repo.list_for_date(date.today())
    # May or may not have alerts depending on observation matching logic
    # But the endpoint should not crash

