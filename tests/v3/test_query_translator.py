"""
Tests for QueryTranslator.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from voyager.llm.query_translator import QueryTranslator
from voyager.models.thesis import Thesis, ThesisExpressionLeg
from voyager.models.common import Direction
from voyager.models.v3 import CausalLink, ResolvedLink, Ambiguity, QueryTranslatorOutput
from voyager.data.series_registry import SeriesRegistry, SeriesEntry


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns JSON responses"""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_registry():
    """Mock SeriesRegistry"""
    registry = MagicMock(spec=SeriesRegistry)
    return registry


@pytest.fixture
def sample_thesis():
    """Sample thesis for testing"""
    return Thesis(
        id="test_thesis_1",
        title="Gold vs Real Yields",
        hypothesis="Rising real yields will pressure gold prices",
        drivers=["Fed tightening", "Inflation falling"],
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


@pytest.mark.asyncio
async def test_extract_links_success(mock_llm_client, mock_registry, sample_thesis):
    """Test successful link extraction"""
    # Mock LLM response
    mock_llm_client.chat.return_value = {
        "content": '{"links": [{"claim": "Real yields lead to gold prices", "concept_a": "real yields", "concept_b": "gold", "direction": "negative"}]}'
    }
    
    # Mock registry - unique resolution
    mock_registry.search_by_concept.side_effect = lambda c: [
        SeriesEntry(id="DFII10", source="FRED", name="10Y Real Yield", category="rates", aliases=["real yields"], frequency="daily", return_type="diff")
    ] if c == "real yields" else [
        SeriesEntry(id="GLD", source="TwelveData", name="Gold ETF", category="commodity", aliases=["gold"], frequency="daily", return_type="pct_change")
    ]
    
    translator = QueryTranslator(mock_llm_client, mock_registry)
    output = await translator.extract_and_resolve(sample_thesis)
    
    assert len(output.links) == 1
    assert output.links[0].concept_a == "real yields"
    assert output.links[0].concept_b == "gold"
    assert len(output.resolved) == 1
    assert output.resolved[0].series_a == "DFII10"
    assert output.resolved[0].series_b == "GLD"
    assert len(output.ambiguities) == 0


@pytest.mark.asyncio
async def test_extract_links_ambiguous(mock_llm_client, mock_registry, sample_thesis):
    """Test ambiguous concept resolution"""
    mock_llm_client.chat.return_value = {
        "content": '{"links": [{"claim": "Bonds affect yields", "concept_a": "bonds", "concept_b": "yields", "direction": "positive"}]}'
    }
    
    # Mock registry - ambiguous resolution for "bonds"
    mock_registry.search_by_concept.side_effect = lambda c: [
        SeriesEntry(id="TLT", source="TwelveData", name="20Y+ Treasury", category="rates", aliases=["bonds", "treasury"], frequency="daily", return_type="pct_change"),
        SeriesEntry(id="IEF", source="TwelveData", name="7-10Y Treasury", category="rates", aliases=["bonds", "treasury"], frequency="daily", return_type="pct_change")
    ] if c == "bonds" else [
        SeriesEntry(id="DGS10", source="FRED", name="10Y Yield", category="rates", aliases=["yields"], frequency="daily", return_type="diff")
    ]
    
    translator = QueryTranslator(mock_llm_client, mock_registry)
    output = await translator.extract_and_resolve(sample_thesis)
    
    assert len(output.ambiguities) == 1
    assert output.ambiguities[0].concept == "bonds"
    assert len(output.ambiguities[0].candidates) == 2
    assert len(output.resolved) == 0


@pytest.mark.asyncio
async def test_extract_links_not_found(mock_llm_client, mock_registry, sample_thesis):
    """Test concept not found in registry"""
    mock_llm_client.chat.return_value = {
        "content": '{"links": [{"claim": "Sentiment affects prices", "concept_a": "sentiment", "concept_b": "prices", "direction": "positive"}]}'
    }
    
    # Mock registry - no match for "sentiment"
    mock_registry.search_by_concept.side_effect = lambda c: [] if c == "sentiment" else [
        SeriesEntry(id="SPY", source="TwelveData", name="S&P 500", category="equity", aliases=["prices"], frequency="daily", return_type="pct_change")
    ]
    
    translator = QueryTranslator(mock_llm_client, mock_registry)
    output = await translator.extract_and_resolve(sample_thesis)
    
    assert len(output.ambiguities) == 1
    assert output.ambiguities[0].concept == "sentiment"
    assert len(output.ambiguities[0].candidates) == 0  # Not found


@pytest.mark.asyncio
async def test_extract_links_empty_response(mock_llm_client, mock_registry, sample_thesis):
    """Test empty LLM response"""
    mock_llm_client.chat.return_value = {"content": ""}
    
    translator = QueryTranslator(mock_llm_client, mock_registry)
    output = await translator.extract_and_resolve(sample_thesis)
    
    assert len(output.links) == 0
    assert len(output.resolved) == 0
    assert len(output.ambiguities) == 0


@pytest.mark.asyncio
async def test_resolve_with_clarifications(mock_llm_client, mock_registry, sample_thesis):
    """Test resolution with PM clarifications"""
    # First call - ambiguous
    mock_llm_client.chat.return_value = {
        "content": '{"links": [{"claim": "Bonds affect yields", "concept_a": "bonds", "concept_b": "yields", "direction": "positive"}]}'
    }
    
    mock_registry.search_by_concept.side_effect = lambda c: [
        SeriesEntry(id="TLT", source="TwelveData", name="20Y+ Treasury", category="rates", aliases=["bonds"], frequency="daily", return_type="pct_change"),
        SeriesEntry(id="IEF", source="TwelveData", name="7-10Y Treasury", category="rates", aliases=["bonds"], frequency="daily", return_type="pct_change")
    ] if c == "bonds" else [
        SeriesEntry(id="DGS10", source="FRED", name="10Y Yield", category="rates", aliases=["yields"], frequency="daily", return_type="diff")
    ]
    
    translator = QueryTranslator(mock_llm_client, mock_registry)
    
    # Initial extraction
    initial_output = await translator.extract_and_resolve(sample_thesis)
    assert len(initial_output.ambiguities) == 1
    
    # Resolve with clarifications
    clarifications = {"bonds": "TLT"}
    output = await translator.resolve_with_clarifications(sample_thesis, clarifications)
    
    assert len(output.resolved) == 1
    assert output.resolved[0].series_a == "TLT"
    assert len(output.ambiguities) == 0


@pytest.mark.asyncio
async def test_extract_links_malformed_json(mock_llm_client, mock_registry, sample_thesis):
    """Test handling of malformed JSON response"""
    mock_llm_client.chat.return_value = {
        "content": "This is not JSON at all"
    }
    
    translator = QueryTranslator(mock_llm_client, mock_registry)
    output = await translator.extract_and_resolve(sample_thesis)
    
    # Should handle gracefully
    assert len(output.links) == 0
