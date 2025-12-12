"""
Tests for SizingService.
"""
import pytest
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

from voyager.services.v3.sizing_service import (
    SizingService,
    compute_kelly_size,
    compute_vol_target_size
)
from voyager.models.thesis import Thesis, RiskRails, ThesisExpressionLeg
from voyager.models.common import ThesisStatus, Direction
from voyager.models.v3 import BacktestResult, BacktestMetrics, EquityPoint


@pytest.fixture
def mock_engine():
    return MagicMock()


@pytest.fixture
def mock_backtest_repo():
    return MagicMock()


@pytest.fixture
def mock_trade_repo():
    return MagicMock()


@pytest.fixture
def sample_backtest():
    return BacktestResult(
        thesis_id="test",
        expression={"GLD": 0.7, "TIP": 0.3},
        period_start="2020-01-01",
        period_end="2023-12-31",
        metrics=BacktestMetrics(
            total_return=0.25,
            cagr=0.08,
            volatility=0.15,
            sharpe=0.53,
            max_drawdown=0.18
        ),
        equity_curve=[
            EquityPoint(date="2020-01-01", value=100.0),
            EquityPoint(date="2023-12-31", value=125.0)
        ],
        iteration_count=1
    )


@pytest.fixture
def sample_rails():
    return RiskRails(
        max_dd_tolerance=0.08,
        position_cap=0.10
    )


@pytest.fixture
def sample_thesis():
    return Thesis(
        id="test",
        title="Test Thesis",
        hypothesis="Test hypothesis",
        drivers=["driver1"],
        disconfirmers=["disconfirmer1"],
        expression=[ThesisExpressionLeg(asset="GLD", direction=Direction.LONG, size_pct=100.0)],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=[],
        notes=None,
        risk_rails=None,
        final_size=None
    )


@pytest.fixture
def sizing_service(mock_engine, mock_backtest_repo, mock_trade_repo):
    return SizingService(mock_engine, mock_backtest_repo, mock_trade_repo)


class TestSizingService:

    def test_basic_sizing(self, sizing_service, sample_thesis, sample_backtest, sample_rails):
        """Test basic sizing calculation"""
        result = sizing_service.compute(
            sample_thesis, sample_rails, sample_backtest, include_portfolio_impact=False
        )

        # implied_size = 0.08 / 0.18 = 0.444
        # capped at 0.10
        assert result.suggested_size == 0.10
        assert result.implied_size == pytest.approx(0.444, rel=0.01)
        assert result.historical_max_dd == 0.18
        assert result.tolerance == 0.08
        assert result.position_cap == 0.10

    def test_sizing_no_cap_binding(self, sizing_service, sample_thesis, sample_backtest):
        """Test sizing when cap doesn't bind"""
        # High position cap, won't bind
        rails = RiskRails(max_dd_tolerance=0.05, position_cap=0.50)
        result = sizing_service.compute(
            sample_thesis, rails, sample_backtest, include_portfolio_impact=False
        )

        # implied_size = 0.05 / 0.18 = 0.278
        # Not capped
        assert result.suggested_size == pytest.approx(0.278, rel=0.01)
        assert result.implied_size == pytest.approx(0.278, rel=0.01)

    def test_sizing_zero_dd_raises(self, sizing_service, sample_thesis, sample_rails):
        """Test ValueError when max_dd is 0"""
        backtest = BacktestResult(
            thesis_id="test",
            expression={},
            period_start="2020-01-01",
            period_end="2023-12-31",
            metrics=BacktestMetrics(
                total_return=0.1,
                cagr=0.03,
                volatility=0.01,
                sharpe=3.0,
                max_drawdown=0.0  # Invalid
            ),
            equity_curve=[],
            iteration_count=1
        )

        with pytest.raises(ValueError, match="Invalid historical max DD"):
            sizing_service.compute(sample_thesis, sample_rails, backtest)

    def test_sizing_negative_dd_raises(self, sizing_service, sample_thesis, sample_rails):
        """Test ValueError when max_dd is negative"""
        backtest = BacktestResult(
            thesis_id="test",
            expression={},
            period_start="2020-01-01",
            period_end="2023-12-31",
            metrics=BacktestMetrics(
                total_return=0.1,
                cagr=0.03,
                volatility=0.01,
                sharpe=3.0,
                max_drawdown=-0.05  # Invalid
            ),
            equity_curve=[],
            iteration_count=1
        )

        with pytest.raises(ValueError, match="Invalid historical max DD"):
            sizing_service.compute(sample_thesis, sample_rails, backtest)

    def test_sizing_none_backtest_raises(self, sizing_service, sample_thesis, sample_rails):
        """Test ValueError when backtest is None"""
        with pytest.raises(ValueError, match="Backtest required"):
            sizing_service.compute(sample_thesis, sample_rails, None)

    def test_portfolio_impact_empty_portfolio(self, sizing_service, sample_thesis, sample_backtest, sample_rails, mock_engine):
        """Test portfolio impact returns None when no positions"""
        # Mock empty portfolio query
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []

        result = sizing_service.compute(
            sample_thesis, sample_rails, sample_backtest, include_portfolio_impact=True
        )

        assert result.portfolio_impact is None

    def test_portfolio_impact_insufficient_data(self, sizing_service, sample_thesis, sample_backtest, sample_rails, mock_engine):
        """Test portfolio impact returns None when < 60 days overlap"""
        # Mock portfolio with positions
        mock_row = MagicMock()
        mock_row.asset = "SPY"
        mock_row.net_quantity = 100.0
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [mock_row]

        # Mock market_data query to return insufficient data
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "ticker": ["SPY"] * 30,
            "close": [100.0] * 30
        })
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]
        pd.read_sql = MagicMock(return_value=mock_df)

        # Create backtest with short equity curve
        short_backtest = BacktestResult(
            thesis_id="test",
            expression={"GLD": 1.0},
            period_start="2024-01-01",
            period_end="2024-01-30",
            metrics=BacktestMetrics(
                total_return=0.05,
                cagr=0.10,
                volatility=0.12,
                sharpe=0.8,
                max_drawdown=0.08
            ),
            equity_curve=[
                EquityPoint(date=f"2024-01-{i:02d}", value=100.0 + i)
                for i in range(1, 31)
            ],
            iteration_count=1
        )

        result = sizing_service.compute(
            sample_thesis, sample_rails, short_backtest, include_portfolio_impact=True
        )

        # Should return None due to insufficient overlap
        assert result.portfolio_impact is None


class TestSizingHelpers:

    def test_kelly_size(self):
        """Test Kelly criterion calculation"""
        size = compute_kelly_size(
            expected_return=0.10,
            volatility=0.15,
            kelly_fraction=0.25
        )
        assert 0 < size <= 0.5

    def test_kelly_size_zero_vol(self):
        """Test Kelly size returns 0.0 for zero volatility"""
        size = compute_kelly_size(
            expected_return=0.10,
            volatility=0.0
        )
        assert size == 0.0

    def test_vol_target_size(self):
        """Test volatility targeting calculation"""
        size = compute_vol_target_size(
            expression_vol=0.20,
            target_vol_contribution=0.02
        )
        assert size == pytest.approx(0.10, rel=0.01)

    def test_vol_target_size_zero_vol(self):
        """Test vol target size returns 0.0 for zero volatility"""
        size = compute_vol_target_size(
            expression_vol=0.0,
            target_vol_contribution=0.02
        )
        assert size == 0.0
