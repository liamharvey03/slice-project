"""
E4: Unit tests for ThesisEvaluationSession.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from slice.sessions.thesis_evaluation_session import ThesisEvaluationSession
from slice.sessions.exceptions import ThesisNotFoundError
from slice.intelligence.context.data_access import DataAccess
from slice.evaluation.thesis_evaluation import ThesisEvaluationService
from slice.llm.llm_tools import LLMTools
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.common import Direction, ThesisStatus
from slice.models.evaluation import ThesisEvaluationResult, EquityPoint, ScenarioImpact
from slice.models.llm_outputs import ThesisReview


@pytest.fixture
def mock_thesis():
    """Create a mock thesis."""
    return Thesis(
        id="T1",
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


@pytest.fixture
def mock_eval_result():
    """Create a mock evaluation result."""
    return ThesisEvaluationResult(
        performance={"total_return": 10.0, "cagr": 5.0, "volatility": 15.0, "sharpe": 0.5, "max_drawdown": 5.0},
        timeseries=[EquityPoint(date=datetime.now(timezone.utc), value=1.0)],
        risk_metrics={"max_weight_pct": 100.0, "VaR_95": 2.0, "max_drawdown_pct": 5.0},
        scenarios=[ScenarioImpact(name="All -10%", pnl_abs=-100.0, pnl_pct=-10.0)],
    )


@pytest.fixture
def mock_review():
    """Create a mock review."""
    return ThesisReview(
        critique="Looks good",
        questions=[],
        risk_flags=[],
        insufficient_context=False,
    )


@pytest.fixture
def mock_data_access(mock_thesis):
    """Create a mock DataAccess."""
    data_access = Mock(spec=DataAccess)
    data_access.get_thesis = Mock(return_value=mock_thesis)
    data_access.save_thesis_evaluation = Mock()
    return data_access


@pytest.fixture
def mock_eval_service(mock_eval_result):
    """Create a mock ThesisEvaluationService."""
    eval_service = Mock(spec=ThesisEvaluationService)
    eval_service.evaluate_thesis = Mock(return_value=mock_eval_result)
    return eval_service


@pytest.fixture
def mock_llm_tools(mock_review):
    """Create a mock LLMTools."""
    llm_tools = Mock(spec=LLMTools)
    llm_tools.review_thesis = AsyncMock(return_value=mock_review)
    return llm_tools


@pytest.mark.asyncio
async def test_thesis_evaluation_session_happy_path(
    mock_data_access, mock_eval_service, mock_llm_tools, mock_thesis, mock_eval_result, mock_review
):
    """Test happy path: E2 + E3 succeed, result returned, evaluation persisted."""
    session = ThesisEvaluationSession(
        data_access=mock_data_access,
        eval_service=mock_eval_service,
        llm_tools=mock_llm_tools,
    )
    
    result = await session.run("T1")
    
    # Verify result structure
    assert result.thesis_id == "T1"
    assert result.evaluation == mock_eval_result
    assert result.review == mock_review
    assert result.trade_plan is None  # No exec_adapter provided
    
    # Verify calls
    mock_data_access.get_thesis.assert_called_once_with("T1")
    mock_eval_service.evaluate_thesis.assert_called_once_with(mock_thesis)
    mock_llm_tools.review_thesis.assert_called_once_with(mock_thesis, mock_eval_result)
    mock_data_access.save_thesis_evaluation.assert_called_once()


@pytest.mark.asyncio
async def test_thesis_evaluation_session_not_found(mock_data_access, mock_eval_service, mock_llm_tools):
    """Test that ThesisNotFoundError is raised for unknown thesis."""
    mock_data_access.get_thesis = Mock(return_value=None)
    
    session = ThesisEvaluationSession(
        data_access=mock_data_access,
        eval_service=mock_eval_service,
        llm_tools=mock_llm_tools,
    )
    
    with pytest.raises(ThesisNotFoundError) as exc_info:
        await session.run("UNKNOWN")
    
    assert exc_info.value.thesis_id == "UNKNOWN"
    # Verify no DB writes
    mock_data_access.save_thesis_evaluation.assert_not_called()


@pytest.mark.asyncio
async def test_thesis_evaluation_session_e2_failure(
    mock_data_access, mock_eval_service, mock_llm_tools, mock_thesis
):
    """Test that E2 failure propagates and no DB write occurs."""
    mock_eval_service.evaluate_thesis = Mock(side_effect=ValueError("Missing price data"))
    
    session = ThesisEvaluationSession(
        data_access=mock_data_access,
        eval_service=mock_eval_service,
        llm_tools=mock_llm_tools,
    )
    
    with pytest.raises(ValueError):
        await session.run("T1")
    
    # Verify no DB writes
    mock_data_access.save_thesis_evaluation.assert_not_called()
    mock_llm_tools.review_thesis.assert_not_called()


@pytest.mark.asyncio
async def test_thesis_evaluation_session_e3_failure(
    mock_data_access, mock_eval_service, mock_llm_tools, mock_thesis, mock_eval_result
):
    """Test that E3 failure propagates and no DB write occurs."""
    mock_llm_tools.review_thesis = AsyncMock(side_effect=Exception("LLM error"))
    
    session = ThesisEvaluationSession(
        data_access=mock_data_access,
        eval_service=mock_eval_service,
        llm_tools=mock_llm_tools,
    )
    
    with pytest.raises(Exception):
        await session.run("T1")
    
    # Verify no DB writes
    mock_data_access.save_thesis_evaluation.assert_not_called()
    # E2 should have succeeded
    mock_eval_service.evaluate_thesis.assert_called_once()

