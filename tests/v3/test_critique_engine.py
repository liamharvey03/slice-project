"""
Tests for CritiqueEngine.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from voyager.llm.critique_engine import CritiqueEngine
from voyager.models.thesis import Thesis, LogicValidation, LogicLink, ThesisExpressionLeg
from voyager.models.common import Direction
from voyager.models.v3 import BacktestResult, BacktestMetrics


@pytest.fixture
def mock_llm_client():
    """Mock LLM client"""
    client = AsyncMock()
    return client


@pytest.fixture
def sample_thesis():
    """Sample thesis for testing"""
    return Thesis(
        id="test_thesis_1",
        title="Gold vs Real Yields",
        hypothesis="Rising real yields will pressure gold prices",
        drivers=["Fed tightening"],
        disconfirmers=["Flight to safety"],
        expression=[
            ThesisExpressionLeg(asset="GLD", direction=Direction.LONG, size_pct=100.0)
        ],
        start_date="2024-01-01",
        review_date=None,
        status="WATCHLIST",
        tags=["test"],
        monitor_indices=["DXY"]
    )


@pytest.fixture
def sample_validation():
    """Sample validation results"""
    return LogicValidation(
        id="val_123",
        thesis_id="test_thesis_1",
        links=[
            LogicLink(
                claim="Real yields lead to gold prices",
                series_a="DFII10",
                series_b="GLD",
                query_type="correlation",
                result=-0.38,
                interpretation="weak"
            )
        ],
        created_at="2024-01-01T00:00:00Z"
    )


@pytest.fixture
def sample_backtest():
    """Sample backtest results"""
    return BacktestResult(
        id="bt_123",
        thesis_id="test_thesis_1",
        expression={"GLD": 1.0},
        period_start="2020-01-01",
        period_end="2024-01-01",
        metrics=BacktestMetrics(
            total_return=0.15,
            cagr=0.035,
            volatility=0.12,
            sharpe=0.5,
            max_drawdown=0.08
        ),
        equity_curve=[],
        factor_exposure=None,
        iteration_count=1,
        created_at="2024-01-01T00:00:00Z"
    )


@pytest.mark.asyncio
async def test_critique_with_concerns(mock_llm_client, sample_thesis, sample_validation):
    """Test critique generation with concerns"""
    mock_llm_client.chat.return_value = {
        "content": '''{
            "concerns": [
                {
                    "dimension": "empirical_grounding",
                    "severity": "medium",
                    "summary": "Correlation is weak (-0.38), may not support strong causal claim"
                }
            ],
            "opening_message": "I have some concerns about the empirical grounding of this thesis."
        }'''
    }
    
    engine = CritiqueEngine(mock_llm_client)
    summary = await engine.critique(sample_thesis, sample_validation, None)
    
    assert len(summary.concerns) == 1
    assert summary.concerns[0].dimension == "empirical_grounding"
    assert summary.concerns[0].severity == "medium"
    assert len(summary.opening_message) > 0


@pytest.mark.asyncio
async def test_critique_no_concerns(mock_llm_client, sample_thesis):
    """Test critique with no concerns"""
    mock_llm_client.chat.return_value = {
        "content": '''{
            "concerns": [],
            "opening_message": "This thesis looks solid. No major concerns."
        }'''
    }
    
    engine = CritiqueEngine(mock_llm_client)
    summary = await engine.critique(sample_thesis, None, None)
    
    assert len(summary.concerns) == 0
    assert "solid" in summary.opening_message.lower() or "no" in summary.opening_message.lower()


@pytest.mark.asyncio
async def test_critique_with_backtest(mock_llm_client, sample_thesis, sample_validation, sample_backtest):
    """Test critique with backtest data"""
    mock_llm_client.chat.return_value = {
        "content": '''{
            "concerns": [
                {
                    "dimension": "expression_fit",
                    "severity": "low",
                    "summary": "Expression captures thesis well"
                }
            ],
            "opening_message": "Thesis looks good overall."
        }'''
    }
    
    engine = CritiqueEngine(mock_llm_client)
    summary = await engine.critique(sample_thesis, sample_validation, sample_backtest)
    
    # Verify backtest data was included in prompt
    call_args = mock_llm_client.chat.call_args
    assert call_args is not None
    user_message = call_args[0][0][1]["content"]
    assert "BACKTEST RESULTS" in user_message or "Total Return" in user_message


@pytest.mark.asyncio
async def test_drill_down(mock_llm_client, sample_thesis, sample_validation):
    """Test drill-down conversation"""
    mock_llm_client.chat.return_value = {
        "content": '''{
            "message": "I understand your point. However, the correlation of -0.38 is still relatively weak.",
            "thesis_edit_suggestion": null
        }'''
    }
    
    engine = CritiqueEngine(mock_llm_client)
    history = [
        {"role": "user", "content": "I think the correlation is actually stronger"},
        {"role": "assistant", "content": "Let me check the data..."}
    ]
    
    response = await engine.drill_down(
        sample_thesis,
        "empirical_grounding",
        "Can you look at rolling correlations?",
        history,
        sample_validation
    )
    
    assert len(response.message) > 0
    assert response.thesis_edit_suggestion is None


@pytest.mark.asyncio
async def test_drill_down_with_edit_suggestion(mock_llm_client, sample_thesis, sample_validation):
    """Test drill-down with edit suggestion"""
    mock_llm_client.chat.return_value = {
        "content": '''{
            "message": "I suggest refining the hypothesis to be more specific.",
            "thesis_edit_suggestion": {
                "field": "hypothesis",
                "action": "replace",
                "value": "Rising real yields above 2% will pressure gold prices"
            }
        }'''
    }
    
    engine = CritiqueEngine(mock_llm_client)
    response = await engine.drill_down(
        sample_thesis,
        "causal_mechanism",
        "How can I improve this?",
        [],
        sample_validation
    )
    
    assert response.thesis_edit_suggestion is not None
    assert response.thesis_edit_suggestion["field"] == "hypothesis"


@pytest.mark.asyncio
async def test_drill_down_invalid_dimension(mock_llm_client, sample_thesis):
    """Test drill-down with invalid dimension"""
    engine = CritiqueEngine(mock_llm_client)
    
    with pytest.raises(ValueError, match="Invalid dimension"):
        await engine.drill_down(
            sample_thesis,
            "invalid_dimension",
            "Test",
            [],
            None
        )


@pytest.mark.asyncio
async def test_critique_empty_response(mock_llm_client, sample_thesis):
    """Test handling of empty LLM response"""
    mock_llm_client.chat.return_value = {"content": ""}
    
    engine = CritiqueEngine(mock_llm_client)
    summary = await engine.critique(sample_thesis, None, None)
    
    # Should return safe default
    assert len(summary.concerns) == 0
    assert "issue" in summary.opening_message.lower() or "trouble" in summary.opening_message.lower()


@pytest.mark.asyncio
async def test_critique_malformed_json(mock_llm_client, sample_thesis):
    """Test handling of malformed JSON"""
    mock_llm_client.chat.return_value = {
        "content": "This is not JSON"
    }
    
    engine = CritiqueEngine(mock_llm_client)
    summary = await engine.critique(sample_thesis, None, None)
    
    # Should handle gracefully
    assert len(summary.concerns) == 0
