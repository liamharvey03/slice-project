"""
E4: API integration tests for thesis evaluation endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from voyager.api.main import app
from voyager.repositories.thesis_repo import ThesisRepository
from voyager.repositories.observation_repo import ObservationRepository
from voyager.repositories.trade_repo import TradeRepository
from voyager.repositories.evaluation_repo import EvaluationRepository
from voyager.repositories.alert_repo import AlertRepository
from voyager.repositories.daily_summary_repo import DailySummaryRepository
from voyager.intelligence.context.data_access import DataAccess
from voyager.evaluation.thesis_evaluation import ThesisEvaluationService
from voyager.quant.price_source import PriceSource
from voyager.llm.llm_tools import LLMTools
from voyager.models.thesis import Thesis, ThesisExpressionLeg
from voyager.models.common import Direction, ThesisStatus
from voyager.models.evaluation import ThesisEvaluationResult, EquityPoint, ScenarioImpact
from voyager.models.llm_outputs import ThesisReview
from datetime import datetime
import voyager.api.session_routes_e4 as routes_mod


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
def mock_price_source():
    """Create a mock PriceSource that returns deterministic prices."""
    price_source = Mock(spec=PriceSource)
    
    # Return a simple price series: 100 -> 110
    import pandas as pd
    from datetime import date, timedelta
    
    dates = pd.date_range(start=date(2024, 1, 1), end=date(2024, 12, 31), freq="D")
    prices = pd.Series([100.0 + (i * 10.0 / len(dates)) for i in range(len(dates))], index=dates)
    
    price_source.get_history = Mock(return_value=prices)
    return price_source


@pytest.fixture
def mock_llm_tools():
    """Create a mock LLMTools that returns deterministic review."""
    llm_tools = Mock(spec=LLMTools)
    
    review = ThesisReview(
        critique="Looks good",
        questions=[],
        risk_flags=[],
        insufficient_context=False,
    )
    llm_tools.review_thesis = AsyncMock(return_value=review)
    return llm_tools


@pytest.fixture
def client_with_deps(db_engine, test_thesis, mock_price_source, mock_llm_tools, e4_tables):
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
    
    # Create eval service
    eval_service = ThesisEvaluationService(price_source=mock_price_source)
    
    # Override dependencies
    app.dependency_overrides[DataAccess.depends] = lambda: data_access
    app.dependency_overrides[routes_mod.get_eval_service] = lambda: eval_service
    app.dependency_overrides[routes_mod.get_llm_tools] = lambda: mock_llm_tools
    
    yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()


def test_evaluate_thesis_happy_path(client_with_deps, db_engine):
    """Test POST /thesis/{id}/evaluate returns 200 + correct JSON."""
    resp = client_with_deps.post("/api/v1/thesis/TEST_T1/evaluate")
    
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["thesis_id"] == "TEST_T1"
    assert "evaluation" in data
    assert "review" in data
    assert data["review"]["critique"] == "Looks good"
    assert "evaluated_at" in data
    
    # Verify DB write occurred
    eval_repo = EvaluationRepository(engine=db_engine)
    result = eval_repo.get_latest_evaluation("TEST_T1")
    assert result is not None


def test_evaluate_thesis_not_found(client_with_deps):
    """Test unknown thesis returns 404."""
    resp = client_with_deps.post("/api/v1/thesis/UNKNOWN/evaluate")
    
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_evaluate_thesis_e2_failure(client_with_deps, db_engine, mock_price_source):
    """Test E2 failure returns 500 and no DB write."""
    # Make price source fail
    mock_price_source.get_history = Mock(side_effect=ValueError("No price data"))
    
    resp = client_with_deps.post("/api/v1/thesis/TEST_T1/evaluate")
    
    assert resp.status_code == 500
    
    # Verify no DB write
    eval_repo = EvaluationRepository(engine=db_engine)
    result = eval_repo.get_latest_evaluation("TEST_T1")
    assert result is None


def test_evaluate_thesis_e3_failure(client_with_deps, db_engine, mock_llm_tools):
    """Test E3 failure returns 500 and no DB write."""
    # Make LLM fail
    mock_llm_tools.review_thesis = AsyncMock(side_effect=Exception("LLM error"))
    
    resp = client_with_deps.post("/api/v1/thesis/TEST_T1/evaluate")
    
    assert resp.status_code == 500
    
    # Verify no DB write
    eval_repo = EvaluationRepository(engine=db_engine)
    result = eval_repo.get_latest_evaluation("TEST_T1")
    assert result is None

