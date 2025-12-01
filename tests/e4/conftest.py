"""
E4: Shared test fixtures.
"""
import pytest
from datetime import date, datetime, timezone
from sqlalchemy import text

from slice.db import get_engine
from slice.repositories.evaluation_repo import EvaluationRepository
from slice.repositories.alert_repo import AlertRepository
from slice.repositories.daily_summary_repo import DailySummaryRepository
from slice.models.evaluation import ThesisEvaluationResult, EquityPoint, ScenarioImpact
from slice.models.llm_outputs import ThesisReview, DailySummary
from slice.models.llm_inputs import Alert


@pytest.fixture(scope="function")
def e4_tables(db_engine):
    """
    Ensure E4 tables exist and clean them before/after each test.
    """
    from slice.db import apply_e4_schema
    
    # Apply E4 schema (idempotent)
    apply_e4_schema()
    
    # Pre-test cleanup
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE thesis_evaluation CASCADE"))
        conn.execute(text("TRUNCATE alert CASCADE"))
        conn.execute(text("TRUNCATE daily_summary CASCADE"))
    yield
    # Post-test cleanup
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE thesis_evaluation CASCADE"))
        conn.execute(text("TRUNCATE alert CASCADE"))
        conn.execute(text("TRUNCATE daily_summary CASCADE"))


@pytest.fixture
def evaluation_repo(db_engine, e4_tables):
    """Create an EvaluationRepository instance."""
    return EvaluationRepository(engine=db_engine)


@pytest.fixture
def alert_repo(db_engine, e4_tables):
    """Create an AlertRepository instance."""
    return AlertRepository(engine=db_engine)


@pytest.fixture
def daily_summary_repo(db_engine, e4_tables):
    """Create a DailySummaryRepository instance."""
    return DailySummaryRepository(engine=db_engine)


@pytest.fixture
def sample_evaluation():
    """Create a sample ThesisEvaluationResult for testing."""
    return ThesisEvaluationResult(
        performance={
            "total_return": 10.0,
            "cagr": 5.0,
            "volatility": 15.0,
            "sharpe": 0.5,
            "max_drawdown": 5.0,
        },
        timeseries=[
            EquityPoint(date=datetime.now(timezone.utc), value=1.0),
        ],
        risk_metrics={
            "max_weight_pct": 100.0,
            "VaR_95": 2.0,
            "max_drawdown_pct": 5.0,
        },
        scenarios=[
            ScenarioImpact(name="All -10%", pnl_abs=-100.0, pnl_pct=-10.0),
            ScenarioImpact(name="All +10%", pnl_abs=100.0, pnl_pct=10.0),
        ],
    )


@pytest.fixture
def sample_review():
    """Create a sample ThesisReview for testing."""
    return ThesisReview(
        critique="Plausible but over-concentrated.",
        questions=["What if inflation re-accelerates?"],
        risk_flags=["Concentration in energy"],
        insufficient_context=False,
    )


@pytest.fixture
def sample_alert():
    """Create a sample Alert for testing."""
    return Alert(
        thesis_id="T1",
        thesis_title="Test Thesis",
        message="Disconfirmer detected",
        observation_id="O1",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_daily_summary():
    """Create a sample DailySummary for testing."""
    return DailySummary(
        key_narratives=["Market volatility increased"],
        risk_highlights=["Concentration risk"],
        thesis_references=["T1"],
        insufficient_context=False,
    )

