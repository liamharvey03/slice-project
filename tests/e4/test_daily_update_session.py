"""
E4: Unit tests for DailyUpdateSession.
"""
import pytest
from datetime import date, datetime, timezone
from unittest.mock import Mock, AsyncMock

from voyager.sessions.daily_update_session import DailyUpdateSession
from voyager.intelligence.context.data_access import DataAccess
from voyager.llm.llm_tools import LLMTools
from voyager.models.thesis import Thesis, ThesisExpressionLeg
from voyager.models.observation import Observation
from voyager.models.common import Direction, ThesisStatus, Sentiment
from voyager.models.llm_outputs import DailySummary
from voyager.models.llm_inputs import Alert
from voyager.models.portfolio import PortfolioSnapshot, PortfolioTotals, Position, PortfolioDepthSnapshot


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
def mock_observation():
    """Create a mock observation that will trigger alerts."""
    obs = Observation(
        id="O1",
        timestamp=datetime.now(timezone.utc),
        text="Disconfirmer detected",
        thesis_ref=["T1"],
        sentiment=Sentiment.BEARISH,
        categories=["risk"],
        actionable="YES",
    )
    return obs


@pytest.fixture
def mock_portfolio():
    """Create a mock portfolio snapshot."""
    return PortfolioSnapshot(
        positions=[Position(asset="GLD", quantity=10.0, value=1900.0)],
        totals=PortfolioTotals(portfolio_value=10000.0, gross_exposure=10000.0, net_exposure=10000.0),
    )


@pytest.fixture
def mock_depth():
    """Create a mock portfolio depth."""
    return PortfolioDepthSnapshot(
        concentration={"top_name_weight": 0.5},
        factors={"equity_beta": 1.0},
        thesis_exposures={"T1": 0.5},
    )


@pytest.fixture
def mock_data_access(mock_thesis, mock_observation, mock_portfolio, mock_depth):
    """Create a mock DataAccess."""
    data_access = Mock(spec=DataAccess)
    data_access.get_active_theses = Mock(return_value=[mock_thesis])
    data_access.get_current_portfolio = Mock(return_value=mock_portfolio)
    data_access.get_portfolio_depth = Mock(return_value=mock_depth)
    data_access.get_recent_observations = Mock(return_value=[mock_observation])
    data_access.get_daily_summary = Mock(return_value=None)
    data_access.save_alerts = Mock()
    data_access.save_daily_summary = Mock()
    # For read-back verification in degradation test
    data_access.list_alerts_for_date = Mock(return_value=[])
    return data_access


@pytest.fixture
def mock_llm_tools():
    """Create a mock LLMTools."""
    llm_tools = Mock(spec=LLMTools)
    return llm_tools


@pytest.mark.asyncio
async def test_daily_update_session_happy_path(
    mock_data_access, mock_llm_tools, mock_portfolio, mock_depth
):
    """Test happy path: alerts detected, summary generated, all persisted."""
    mock_summary = DailySummary(
        key_narratives=["Test narrative"],
        risk_highlights=["Test risk"],
        thesis_references=["T1"],
        insufficient_context=False,
    )
    mock_llm_tools.daily_summary = AsyncMock(return_value=mock_summary)
    
    session = DailyUpdateSession(
        data_access=mock_data_access,
        llm_tools=mock_llm_tools,
    )
    
    result = await session.run()
    
    # Verify result structure
    assert result.date == date.today()
    assert result.portfolio_snapshot == mock_portfolio
    assert result.portfolio_depth == mock_depth
    assert len(result.alerts) > 0  # Should have detected alerts
    assert result.summary == mock_summary
    
    # Verify persistence
    mock_data_access.save_alerts.assert_called_once()
    mock_data_access.save_daily_summary.assert_called_once()


@pytest.mark.asyncio
async def test_daily_update_session_llm_failure(
    mock_data_access, mock_llm_tools, mock_portfolio, mock_depth, mock_thesis
):
    """Test LLM failure degradation: alerts persisted, insufficient_context=True."""
    mock_llm_tools.daily_summary = AsyncMock(side_effect=Exception("LLM error"))
    
    # Setup read-back to return the alerts that were saved
    saved_alerts = []
    def capture_alerts(alerts):
        saved_alerts.extend(alerts)
    mock_data_access.save_alerts = Mock(side_effect=capture_alerts)
    mock_data_access.list_alerts_for_date = Mock(side_effect=lambda d: saved_alerts)
    
    session = DailyUpdateSession(
        data_access=mock_data_access,
        llm_tools=mock_llm_tools,
    )
    
    result = await session.run()
    
    # Verify alerts still persisted
    mock_data_access.save_alerts.assert_called_once()
    
    # Verify degraded summary
    assert result.summary.insufficient_context is True
    assert result.summary.key_narratives == []
    assert result.summary.risk_highlights == []
    
    # Summary should still be persisted
    mock_data_access.save_daily_summary.assert_called_once()
    
    # Verify read-back: alerts can be retrieved after LLM failure
    retrieved_alerts = mock_data_access.list_alerts_for_date(date.today())
    assert len(retrieved_alerts) == len(result.alerts)
    assert len(retrieved_alerts) > 0  # We should have alerts from mock_observation
    assert {a.thesis_id for a in retrieved_alerts} == {a.thesis_id for a in result.alerts}


@pytest.mark.asyncio
async def test_daily_update_session_empty_portfolio(mock_data_access, mock_llm_tools):
    """Test empty portfolio: no crash, empty alerts."""
    # No active theses
    mock_data_access.get_active_theses = Mock(return_value=[])
    mock_data_access.get_current_portfolio = Mock(return_value=PortfolioSnapshot(
        positions=[],
        totals=PortfolioTotals(portfolio_value=0.0, gross_exposure=0.0, net_exposure=0.0),
    ))
    mock_data_access.get_portfolio_depth = Mock(return_value=PortfolioDepthSnapshot(
        concentration={}, factors={}, thesis_exposures={}
    ))
    mock_data_access.get_recent_observations = Mock(return_value=[])
    
    mock_summary = DailySummary(
        key_narratives=[],
        risk_highlights=[],
        thesis_references=[],
        insufficient_context=False,
    )
    mock_llm_tools.daily_summary = AsyncMock(return_value=mock_summary)
    
    session = DailyUpdateSession(
        data_access=mock_data_access,
        llm_tools=mock_llm_tools,
    )
    
    result = await session.run()
    
    # Should not crash
    assert result.alerts == []
    assert result.summary is not None

