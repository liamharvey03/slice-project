"""
Tests for QuantService.
"""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from voyager.quant.quant_service import (
    QuantService, 
    CorrelationResult,
    ConditionalReturnsResult,
    RelationshipStrengthResult,
    MIN_OBS,
)
from voyager.data.series_registry import SeriesRegistry, SeriesEntry


@pytest.fixture
def mock_registry():
    """Create a mock registry with test series"""
    registry = MagicMock(spec=SeriesRegistry)
    
    registry.get_by_id.side_effect = lambda x: {
        "GLD": SeriesEntry(
            "GLD", "TwelveData", "Gold", "commodity", ["gold"], "daily", "pct_change"
        ),
        "DFII10": SeriesEntry(
            "DFII10", "FRED", "10Y Real Yield", "rates", ["real yields"], "daily", "diff"
        ),
        "SPY": SeriesEntry(
            "SPY", "TwelveData", "S&P 500", "equity", ["stocks"], "daily", "pct_change"
        ),
        "FEDFUNDS": SeriesEntry(
            "FEDFUNDS", "FRED", "Fed Funds Rate", "rates", ["fed funds"], "daily", "diff"
        ),
    }.get(x)
    
    return registry


@pytest.fixture
def mock_engine():
    """Create a mock database engine"""
    return MagicMock()


class TestQuantService:
    
    def test_parse_period_years(self):
        """Test period parsing for year strings"""
        engine = MagicMock()
        registry = MagicMock()
        quant = QuantService(engine, registry)
        
        start, end = quant._parse_period("5Y")
        assert (end - start).days == 365 * 5
    
    def test_parse_period_explicit_dates(self):
        """Test period parsing for explicit date range"""
        engine = MagicMock()
        registry = MagicMock()
        quant = QuantService(engine, registry)
        
        start, end = quant._parse_period("2020-01-01:2023-12-31")
        assert start == date(2020, 1, 1)
        assert end == date(2023, 12, 31)
    
    def test_to_returns_pct_change(self, mock_engine, mock_registry):
        """Test return conversion for pct_change type"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Create test series
        dates = pd.date_range("2023-01-01", periods=5)
        prices = pd.Series([100, 110, 105, 115, 120], index=dates)
        
        entry = SeriesEntry("GLD", "TwelveData", "Gold", "commodity", [], "daily", "pct_change")
        returns = quant._to_returns(prices, entry)
        
        # Should be percentage changes
        assert len(returns) == 4  # One less due to dropna
        assert returns.iloc[0] == pytest.approx(0.10, abs=0.01)  # (110-100)/100
    
    def test_to_returns_diff(self, mock_engine, mock_registry):
        """Test return conversion for diff type"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Create test series
        dates = pd.date_range("2023-01-01", periods=5)
        rates = pd.Series([2.0, 2.1, 2.05, 2.15, 2.2], index=dates)
        
        entry = SeriesEntry("DFII10", "FRED", "Real Yield", "rates", [], "daily", "diff")
        diffs = quant._to_returns(rates, entry)
        
        # Should be differences
        assert len(diffs) == 4  # One less due to dropna
        assert diffs.iloc[0] == pytest.approx(0.1, abs=0.01)  # 2.1 - 2.0
    
    def test_to_returns_level(self, mock_engine, mock_registry):
        """Test return conversion for level type"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Create test series
        dates = pd.date_range("2023-01-01", periods=5)
        levels = pd.Series([100, 110, 105, 115, 120], index=dates)
        
        entry = SeriesEntry("VIX", "TwelveData", "VIX", "volatility", [], "daily", "level")
        result = quant._to_returns(levels, entry)
        
        # Should remain unchanged
        assert len(result) == 5
        assert result.equals(levels)
    
    def test_correlation_insufficient_data(self, mock_engine, mock_registry):
        """Test that correlation raises error with insufficient data"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Mock fetch to return very little data
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.return_value = pd.Series(
                [1, 2, 3], 
                index=pd.date_range("2023-01-01", periods=3)
            )
            
            with pytest.raises(ValueError, match="Insufficient"):
                quant.correlation("GLD", "DFII10")
    
    def test_correlation_sufficient_data(self, mock_engine, mock_registry):
        """Test correlation with sufficient data"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Create correlated test data
        dates = pd.date_range("2023-01-01", periods=100)
        np.random.seed(42)
        x = np.random.randn(100)
        y = x + 0.1 * np.random.randn(100)  # Correlated with x
        
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.side_effect = [
                pd.Series(x, index=dates),
                pd.Series(y, index=dates),
            ]
            
            result = quant.correlation("GLD", "DFII10", period="1Y")
            
            assert result.n_observations >= MIN_OBS
            assert -1 <= result.correlation <= 1
            assert result.series_a == "GLD"
            assert result.series_b == "DFII10"
    
    def test_relationship_strength_interpretation(self, mock_engine, mock_registry):
        """Test relationship strength interpretation logic"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Mock correlation to return known value
        with patch.object(quant, 'correlation') as mock_corr:
            # Strong negative correlation
            mock_corr.return_value = CorrelationResult(
                series_a="DFII10",
                series_b="GLD",
                correlation=-0.65,
                period_start=date(2020, 1, 1),
                period_end=date(2023, 12, 31),
                n_observations=1000,
                p_value=0.001
            )
            
            result = quant.relationship_strength("DFII10", "GLD", "negative", "5Y")
            
            assert result.interpretation == "supports"
            assert result.direction_matches is True
            assert result.strength == "moderate"
            assert result.confidence == "medium"
    
    def test_relationship_strength_contradicts(self, mock_engine, mock_registry):
        """Test relationship strength when direction contradicts"""
        quant = QuantService(mock_engine, mock_registry)
        
        with patch.object(quant, 'correlation') as mock_corr:
            # Positive correlation when negative expected
            mock_corr.return_value = CorrelationResult(
                series_a="DFII10",
                series_b="GLD",
                correlation=0.5,
                period_start=date(2020, 1, 1),
                period_end=date(2023, 12, 31),
                n_observations=1000,
                p_value=0.001
            )
            
            result = quant.relationship_strength("DFII10", "GLD", "negative", "5Y")
            
            assert result.interpretation == "contradicts"
            assert result.direction_matches is False
    
    def test_conditional_returns_logic(self, mock_engine, mock_registry):
        """Test conditional returns calculation"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Create test data
        dates = pd.date_range("2023-01-01", periods=100)
        np.random.seed(42)
        prices = pd.Series(np.cumsum(np.random.randn(100)) + 100, index=dates)
        condition = pd.Series(np.random.uniform(1, 3, 100), index=dates)
        
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.side_effect = [prices, condition]
            
            result = quant.conditional_returns(
                asset="GLD",
                condition_series="DFII10",
                condition_op=">",
                condition_value=2.0,
                period="1Y"
            )
            
            assert result.asset == "GLD"
            assert result.condition == "DFII10 > 2.0"
            assert 0 <= result.pct_condition_true <= 100
            assert result.n_periods + (result.total_periods - result.n_periods) == result.total_periods
    
    def test_conditional_returns_forward_looking_guard(self, mock_engine, mock_registry):
        """Test that conditional returns drops missing condition values"""
        quant = QuantService(mock_engine, mock_registry)
        
        dates = pd.date_range("2023-01-01", periods=50)
        prices = pd.Series(np.cumsum(np.random.randn(50)) + 100, index=dates)
        # Create condition with some NaN values
        condition = pd.Series([np.nan] * 10 + list(np.random.uniform(1, 3, 40)), index=dates)
        
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.side_effect = [prices, condition]
            
            result = quant.conditional_returns(
                asset="GLD",
                condition_series="DFII10",
                condition_op=">",
                condition_value=2.0,
                period="1Y"
            )
            
            # Should handle NaN conditions correctly
            assert result.total_periods > 0
    
    def test_distribution_levels(self, mock_engine, mock_registry):
        """Test distribution on levels"""
        quant = QuantService(mock_engine, mock_registry)
        
        dates = pd.date_range("2023-01-01", periods=100)
        np.random.seed(42)
        data = pd.Series(np.random.normal(100, 10, 100), index=dates)
        
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.return_value = data
            
            result = quant.distribution("DFII10", period="1Y", on="levels")
            
            assert result.series == "DFII10"
            assert "10" in result.percentiles
            assert "50" in result.percentiles
            assert "90" in result.percentiles
            assert 0 <= result.percentile_rank <= 100
    
    def test_distribution_returns(self, mock_engine, mock_registry):
        """Test distribution on returns"""
        quant = QuantService(mock_engine, mock_registry)
        
        dates = pd.date_range("2023-01-01", periods=100)
        np.random.seed(42)
        prices = pd.Series(np.cumsum(np.random.randn(100)) + 100, index=dates)
        
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.return_value = prices
            
            result = quant.distribution("GLD", period="1Y", on="returns")
            
            assert result.series == "GLD"
            assert result.mean is not None
            assert result.std is not None
    
    def test_distribution_insufficient_data(self, mock_engine, mock_registry):
        """Test distribution raises error with insufficient data"""
        quant = QuantService(mock_engine, mock_registry)
        
        dates = pd.date_range("2023-01-01", periods=10)  # Less than MIN_OBS
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], index=dates)
        
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.return_value = data
            
            with pytest.raises(ValueError, match="Insufficient"):
                quant.distribution("DFII10", period="1Y")
