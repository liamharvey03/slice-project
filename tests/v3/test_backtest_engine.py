"""
Tests for BacktestEngine.
"""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from voyager.quant.backtest_engine import (
    BacktestEngine, 
    BacktestConfig, 
    expression_from_legs
)


@pytest.fixture
def mock_engine():
    return MagicMock()


@pytest.fixture
def sample_prices():
    """Create sample price data with DatetimeIndex"""
    dates = pd.date_range("2020-01-01", "2023-12-31", freq="B")  # Business days
    np.random.seed(42)
    
    gld = 150 * np.cumprod(1 + np.random.randn(len(dates)) * 0.01)
    tip = 120 * np.cumprod(1 + np.random.randn(len(dates)) * 0.005)
    
    return pd.DataFrame({
        "GLD": gld,
        "TIP": tip
    }, index=dates)  # DatetimeIndex, not column


class TestExpressionFromLegs:
    
    def test_long_only(self):
        legs = [
            {"asset": "GLD", "direction": "LONG", "size_pct": 70},
            {"asset": "TIP", "direction": "LONG", "size_pct": 30}
        ]
        result = expression_from_legs(legs)
        assert result == {"GLD": 0.7, "TIP": 0.3}
    
    def test_with_short(self):
        legs = [
            {"asset": "GLD", "direction": "LONG", "size_pct": 50},
            {"asset": "TLT", "direction": "SHORT", "size_pct": 30}
        ]
        result = expression_from_legs(legs)
        assert result == {"GLD": 0.5, "TLT": -0.3}
    
    def test_default_direction_long(self):
        legs = [
            {"asset": "GLD", "size_pct": 100}  # No direction specified
        ]
        result = expression_from_legs(legs)
        assert result == {"GLD": 1.0}


class TestBacktestEngine:
    
    def test_validate_expression_valid(self, mock_engine):
        engine = BacktestEngine(mock_engine)
        # Should not raise
        engine._validate_expression({"GLD": 0.7, "TIP": 0.3})
    
    def test_validate_expression_exceeds_100(self, mock_engine):
        engine = BacktestEngine(mock_engine)
        with pytest.raises(ValueError, match="exceeds 100%"):
            engine._validate_expression({"GLD": 0.8, "TIP": 0.5})
    
    def test_validate_expression_empty(self, mock_engine):
        engine = BacktestEngine(mock_engine)
        with pytest.raises(ValueError, match="cannot be empty"):
            engine._validate_expression({})
    
    def test_validate_expression_high_leverage(self, mock_engine):
        engine = BacktestEngine(mock_engine)
        with pytest.raises(ValueError, match="exceeds 200%"):
            engine._validate_expression({"GLD": 1.0, "TLT": -1.5})  # 100% long + 150% short = 250% gross
    
    def test_run_backtest(self, mock_engine, sample_prices):
        engine = BacktestEngine(mock_engine)
        
        with patch.object(engine, '_fetch_prices', return_value=sample_prices):
            result = engine.run(
                expression={"GLD": 0.7, "TIP": 0.3},
                start_date=date(2020, 1, 1),
                end_date=date(2023, 12, 31),
                thesis_id="test_thesis"
            )
        
        assert result.thesis_id == "test_thesis"
        assert result.expression == {"GLD": 0.7, "TIP": 0.3}
        assert result.metrics.total_return != 0
        assert result.metrics.volatility > 0
        assert len(result.equity_curve) > 0
        assert result.period_start is not None
        assert result.period_end is not None
    
    def test_metrics_calculation(self, mock_engine, sample_prices):
        engine = BacktestEngine(mock_engine)
        
        with patch.object(engine, '_fetch_prices', return_value=sample_prices):
            result = engine.run(
                expression={"GLD": 1.0},
                start_date=date(2020, 1, 1),
                end_date=date(2023, 12, 31)
            )
        
        # Metrics should be reasonable
        assert -1 < result.metrics.total_return < 10  # Not crazy
        assert 0 < result.metrics.volatility < 1     # Annualized vol
        assert -5 < result.metrics.sharpe < 5        # Reasonable Sharpe
        assert 0 < result.metrics.max_drawdown < 1   # Max DD as fraction
        assert result.metrics.cagr is not None
    
    def test_default_dates(self, mock_engine, sample_prices):
        engine = BacktestEngine(mock_engine)
        
        with patch.object(engine, '_fetch_prices', return_value=sample_prices):
            result = engine.run(expression={"GLD": 1.0})
        
        # Should use default dates (5 years ago to today)
        assert result.period_start is not None
        assert result.period_end is not None
    
    def test_equity_curve_sampling(self, mock_engine):
        """Test that equity curve is sampled to max 500 points"""
        # Create a very long price series
        dates = pd.date_range("2020-01-01", "2023-12-31", freq="D")
        prices = pd.DataFrame({"GLD": np.random.randn(len(dates)).cumsum() + 100}, index=dates)
        
        engine = BacktestEngine(mock_engine)
        
        with patch.object(engine, '_fetch_prices', return_value=prices):
            result = engine.run(expression={"GLD": 1.0})
        
        # Should be sampled down to <= 500 points
        assert len(result.equity_curve) <= 500
