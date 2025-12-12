# V3 Phase 2: Backtest Engine

## Overview

This phase replaces the existing Backtrader-based backtesting with VectorBT. The new engine is faster, more Pythonic, and better suited for the portfolio-level analysis V3 requires.

## Prerequisites

- Phase 0 complete (schema, models)
- Phase 1 complete (QuantService for data fetching patterns)
- `market_data` table populated with price data

---

## Task 1: Install VectorBT

Add to `requirements.txt`:

```
vectorbt>=0.26.0
```

Note: We're using the free/open-source version. VectorBT Pro is not required for V3.

---

## Task 2: Backtest Engine Core

**File:** `src/voyager/quant/backtest_engine.py` (NEW FILE)

```python
"""
VectorBT-based backtest engine for V3.

Replaces Backtrader for thesis expression backtesting.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Dict, List
import pandas as pd
import numpy as np
import vectorbt as vbt
from sqlalchemy import text
from sqlalchemy.engine import Engine

from voyager.models.v3 import BacktestResult, BacktestMetrics, EquityPoint, FactorExposureResult


@dataclass
class BacktestConfig:
    """Configuration for backtest runs"""
    initial_cash: float = 100_000.0
    commission: float = 0.001  # 0.1% per trade
    slippage: float = 0.0005   # 0.05% slippage
    rebalance_freq: str = "never"  # "never" | "daily" | "weekly" | "monthly"
    risk_free_rate: float = 0.03  # 3% for Sharpe calculation


class BacktestEngine:
    """
    Backtests thesis expressions using VectorBT.
    
    An expression is a dict mapping assets to weights:
        {"GLD": 0.7, "TIP": 0.3}  # 70% gold, 30% TIPS
        {"GLD": 0.5, "TLT": -0.3}  # 50% long gold, 30% short treasuries
    
    Usage:
        engine = BacktestEngine(db_engine)
        result = engine.run({"GLD": 0.7, "TIP": 0.3}, start_date=date(2020, 1, 1))
    """
    
    def __init__(self, engine: Engine, config: BacktestConfig = None):
        self._engine = engine
        self._config = config or BacktestConfig()
    
    # -------------------------------------------
    # Data Fetching
    # -------------------------------------------
    
    def _fetch_prices(
        self, 
        tickers: List[str], 
        start: date, 
        end: date
    ) -> pd.DataFrame:
        """
        Fetch aligned OHLCV data for multiple tickers.
        
        Returns DataFrame with DatetimeIndex and ticker columns.
        """
        query = text("""
            SELECT date, ticker, open, high, low, close, volume
            FROM market_data
            WHERE ticker = ANY(:tickers)
            AND date >= :start AND date <= :end
            ORDER BY date, ticker
        """)
        
        with self._engine.connect() as conn:
            df = pd.read_sql(query, conn, params={
                "tickers": tickers,
                "start": start,
                "end": end
            })
        
        if df.empty:
            raise ValueError(f"No price data for {tickers} between {start} and {end}")
        
        # Pivot to get tickers as columns (using close prices)
        df["date"] = pd.to_datetime(df["date"])
        prices = df.pivot(index="date", columns="ticker", values="close")
        
        # Check for missing tickers
        missing = set(tickers) - set(prices.columns)
        if missing:
            raise ValueError(f"No data for tickers: {missing}")
        
        # Reorder columns to match input order
        prices = prices[tickers]
        
        # Forward fill small gaps (up to 5 days), then drop remaining NaNs
        prices = prices.ffill(limit=5).dropna()
        
        if len(prices) < 20:
            raise ValueError(f"Insufficient price history: only {len(prices)} days")
        
        return prices
    
    # -------------------------------------------
    # Backtest Execution
    # -------------------------------------------
    
    def run(
        self,
        expression: Dict[str, float],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        thesis_id: str = None
    ) -> BacktestResult:
        """
        Run backtest on an expression.
        
        Args:
            expression: Dict mapping ticker to weight (e.g., {"GLD": 0.7, "TIP": 0.3})
                        Negative weights indicate short positions.
            start_date: Start of backtest period (default: 5 years ago)
            end_date: End of backtest period (default: today)
            thesis_id: Optional thesis ID for tracking
            
        Returns:
            BacktestResult with metrics and equity curve
        """
        # Validate expression
        self._validate_expression(expression)
        
        tickers = list(expression.keys())
        weights = np.array([expression[t] for t in tickers])
        
        # Default dates
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365 * 5)
        
        # Fetch price data
        prices = self._fetch_prices(tickers, start_date, end_date)
        
        # Run VectorBT portfolio simulation
        portfolio = self._run_portfolio(prices, weights, tickers)
        
        # Extract metrics
        metrics = self._compute_metrics(portfolio, prices)
        
        # Build equity curve
        equity_curve = self._build_equity_curve(portfolio)
        
        return BacktestResult(
            thesis_id=thesis_id or "unknown",
            expression=expression,
            period_start=str(prices.index[0].date()),
            period_end=str(prices.index[-1].date()),
            metrics=metrics,
            equity_curve=equity_curve,
            factor_exposure=None,  # Computed separately if needed
            iteration_count=1
        )
    
    def _validate_expression(self, expression: Dict[str, float]) -> None:
        """Validate expression weights"""
        if not expression:
            raise ValueError("Expression cannot be empty")
        
        total_long = sum(w for w in expression.values() if w > 0)
        total_short = sum(abs(w) for w in expression.values() if w < 0)
        
        # Allow some tolerance for rounding
        if total_long > 1.01:
            raise ValueError(f"Long weights sum to {total_long:.2%}, exceeds 100%")
        
        # For V3, we allow shorts but warn if leverage is high
        gross_exposure = total_long + total_short
        if gross_exposure > 2.0:
            raise ValueError(f"Gross exposure {gross_exposure:.2%} exceeds 200%")
    
    def _run_portfolio(
        self, 
        prices: pd.DataFrame, 
        weights: np.ndarray,
        tickers: List[str]
    ) -> vbt.Portfolio:
        """
        Run VectorBT portfolio simulation.
        
        Uses from_orders with target percent sizing for static weight allocation.
        """
        # For static weights (no rebalancing), we simulate initial allocation
        # and let positions drift with price changes
        
        if self._config.rebalance_freq == "never":
            # Single allocation at start
            portfolio = vbt.Portfolio.from_orders(
                close=prices,
                size=weights,
                size_type="targetpercent",
                init_cash=self._config.initial_cash,
                fees=self._config.commission,
                slippage=self._config.slippage,
                freq="D",
                call_seq="auto"  # Handle shorts properly
            )
        else:
            # Periodic rebalancing
            rebal_map = {
                "daily": "D",
                "weekly": "W",
                "monthly": "M"
            }
            freq = rebal_map.get(self._config.rebalance_freq, "M")
            
            # Create rebalancing signal
            rebal_dates = prices.resample(freq).first().index
            rebal_mask = prices.index.isin(rebal_dates)
            
            # Allocate on rebalancing dates
            size = np.zeros((len(prices), len(tickers)))
            size[rebal_mask] = weights
            
            portfolio = vbt.Portfolio.from_orders(
                close=prices,
                size=size,
                size_type="targetpercent",
                init_cash=self._config.initial_cash,
                fees=self._config.commission,
                slippage=self._config.slippage,
                freq="D",
                call_seq="auto"
            )
        
        return portfolio
    
    def _compute_metrics(
        self, 
        portfolio: vbt.Portfolio,
        prices: pd.DataFrame
    ) -> BacktestMetrics:
        """Extract performance metrics from portfolio"""
        
        # Total return
        total_return = float(portfolio.total_return())
        
        # CAGR
        n_years = len(prices) / 252  # Trading days
        if n_years > 0 and total_return > -1:
            cagr = float((1 + total_return) ** (1 / n_years) - 1)
        else:
            cagr = 0.0
        
        # Volatility (annualized)
        returns = portfolio.returns()
        volatility = float(returns.std() * np.sqrt(252))
        
        # Sharpe ratio
        excess_return = cagr - self._config.risk_free_rate
        sharpe = float(excess_return / volatility) if volatility > 0 else 0.0
        
        # Max drawdown
        max_drawdown = float(portfolio.max_drawdown())
        
        return BacktestMetrics(
            total_return=round(total_return, 4),
            cagr=round(cagr, 4),
            volatility=round(volatility, 4),
            sharpe=round(sharpe, 4),
            max_drawdown=round(abs(max_drawdown), 4)  # Store as positive number
        )
    
    def _build_equity_curve(self, portfolio: vbt.Portfolio) -> List[EquityPoint]:
        """Build equity curve from portfolio"""
        equity = portfolio.value()
        
        # Sample to avoid huge arrays (max 500 points)
        if len(equity) > 500:
            step = len(equity) // 500
            equity = equity.iloc[::step]
        
        return [
            EquityPoint(
                date=str(idx.date()) if hasattr(idx, 'date') else str(idx),
                value=round(float(val), 2)
            )
            for idx, val in equity.items()
        ]
    
    # -------------------------------------------
    # Factor Analysis
    # -------------------------------------------
    
    def compute_factor_exposure(
        self,
        expression: Dict[str, float],
        start_date: date,
        end_date: date,
        factor_tickers: Dict[str, str] = None
    ) -> FactorExposureResult:
        """
        Compute factor exposures for an expression.
        
        Regresses expression returns against factor returns.
        
        Args:
            expression: Thesis expression
            start_date: Start date
            end_date: End date
            factor_tickers: Override default factor proxies
            
        Returns:
            FactorExposureResult with betas and R²
        """
        # Default factor proxies
        default_factors = {
            "rates_level": "TLT",      # Long-term rates
            "rates_curve": None,        # Computed as TLT - IEF (handled specially)
            "real_yields": "TIP",       # TIPS
            "fx": "UUP",               # Dollar index
            "commodities": "DBC",      # Broad commodities (or GLD as fallback)
            "equity": "SPY"            # S&P 500
        }
        
        factors = factor_tickers or default_factors
        
        # Get expression returns
        tickers = list(expression.keys())
        weights = np.array([expression[t] for t in tickers])
        prices = self._fetch_prices(tickers, start_date, end_date)
        returns = (prices.pct_change().dropna() * weights).sum(axis=1)
        
        # Get factor returns
        factor_tickers_list = [t for t in factors.values() if t is not None]
        try:
            factor_prices = self._fetch_prices(factor_tickers_list, start_date, end_date)
        except ValueError:
            # Some factors may not have data, return partial result
            return FactorExposureResult(
                betas={},
                r_squared=0.0,
                residual_vol=float(returns.std() * np.sqrt(252))
            )
        
        factor_returns = factor_prices.pct_change().dropna()
        
        # Align dates
        aligned = pd.concat([returns, factor_returns], axis=1, join="inner").dropna()
        if len(aligned) < 60:
            return FactorExposureResult(
                betas={},
                r_squared=0.0,
                residual_vol=float(returns.std() * np.sqrt(252))
            )
        
        y = aligned.iloc[:, 0]  # Expression returns
        X = aligned.iloc[:, 1:]  # Factor returns
        
        # Add constant for regression
        X_with_const = np.column_stack([np.ones(len(X)), X.values])
        
        # OLS regression
        try:
            coeffs, residuals, rank, s = np.linalg.lstsq(X_with_const, y.values, rcond=None)
            
            # Extract betas (skip intercept)
            betas = {}
            for i, col in enumerate(X.columns):
                factor_name = [k for k, v in factors.items() if v == col]
                if factor_name:
                    betas[factor_name[0]] = round(float(coeffs[i + 1]), 4)
            
            # R-squared
            y_pred = X_with_const @ coeffs
            ss_res = np.sum((y.values - y_pred) ** 2)
            ss_tot = np.sum((y.values - y.mean()) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
            
            # Residual volatility
            residual_returns = y.values - y_pred
            residual_vol = float(np.std(residual_returns) * np.sqrt(252))
            
            return FactorExposureResult(
                betas=betas,
                r_squared=round(float(r_squared), 4),
                residual_vol=round(residual_vol, 4)
            )
            
        except Exception:
            return FactorExposureResult(
                betas={},
                r_squared=0.0,
                residual_vol=float(returns.std() * np.sqrt(252))
            )


# -------------------------------------------
# Convenience Functions
# -------------------------------------------

def expression_from_legs(legs: List[dict]) -> Dict[str, float]:
    """
    Convert thesis expression legs to backtest expression dict.
    
    Args:
        legs: List of {"asset": "GLD", "direction": "LONG", "size_pct": 70}
        
    Returns:
        {"GLD": 0.7}
    """
    expression = {}
    for leg in legs:
        asset = leg["asset"]
        direction = leg.get("direction", "LONG")
        size_pct = leg.get("size_pct", 0)
        
        weight = size_pct / 100
        if direction == "SHORT":
            weight = -weight
        
        expression[asset] = weight
    
    return expression
```

---

## Task 3: Backtest Service

**File:** `src/voyager/services/v3/backtest_service.py` (NEW FILE)

```python
"""
Backtest Service for V3.

Orchestrates backtest execution and result persistence.
"""
from datetime import date, datetime
from typing import Optional
import uuid

from voyager.quant.backtest_engine import BacktestEngine, BacktestConfig, expression_from_legs
from voyager.models.v3 import BacktestResult
from voyager.models.thesis import ThesisV3
from voyager.repositories.backtest_result_repository import BacktestResultRepository
from voyager.repositories.thesis_repository import ThesisRepository


class BacktestService:
    """
    Orchestrates thesis backtesting.
    
    - Runs backtests via BacktestEngine
    - Tracks iteration counts
    - Persists results
    - Optionally computes factor exposure
    """
    
    def __init__(
        self,
        backtest_engine: BacktestEngine,
        backtest_repo: BacktestResultRepository,
        thesis_repo: ThesisRepository
    ):
        self._engine = backtest_engine
        self._backtest_repo = backtest_repo
        self._thesis_repo = thesis_repo
    
    def run(
        self,
        thesis_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_factor_exposure: bool = True
    ) -> BacktestResult:
        """
        Run backtest for a thesis.
        
        Args:
            thesis_id: Thesis ID
            start_date: Optional start date (ISO string)
            end_date: Optional end date (ISO string)
            include_factor_exposure: Whether to compute factor exposures
            
        Returns:
            BacktestResult with metrics and optional factor exposure
        """
        # Load thesis
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        # Convert expression legs to dict
        expression = expression_from_legs([leg.dict() for leg in thesis.expression])
        
        if not expression:
            raise ValueError("Thesis has no expression legs")
        
        # Parse dates
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
        
        # Get iteration count
        current_count = self._backtest_repo.count_by_thesis(thesis_id)
        
        # Run backtest
        result = self._engine.run(
            expression=expression,
            start_date=start,
            end_date=end,
            thesis_id=thesis_id
        )
        
        # Compute factor exposure if requested
        if include_factor_exposure and start and end:
            try:
                factor_exposure = self._engine.compute_factor_exposure(
                    expression=expression,
                    start_date=start or date.fromisoformat(result.period_start),
                    end_date=end or date.fromisoformat(result.period_end)
                )
                result.factor_exposure = factor_exposure
            except Exception:
                # Factor exposure is optional, don't fail the whole backtest
                pass
        
        # Update iteration count
        result.iteration_count = current_count + 1
        result.id = f"bt_{uuid.uuid4().hex[:12]}"
        result.created_at = datetime.utcnow().isoformat()
        
        # Persist result
        self._backtest_repo.insert(result)
        
        return result
    
    def get_latest(self, thesis_id: str) -> Optional[BacktestResult]:
        """Get most recent backtest for a thesis"""
        return self._backtest_repo.get_latest_by_thesis(thesis_id)
    
    def list_history(self, thesis_id: str) -> list:
        """List all backtests for a thesis"""
        return self._backtest_repo.list_by_thesis(thesis_id)
    
    def get_iteration_count(self, thesis_id: str) -> int:
        """Get number of backtest iterations for a thesis"""
        return self._backtest_repo.count_by_thesis(thesis_id)
```

---

## Task 4: Tests

**File:** `tests/v3/test_backtest_engine.py` (NEW FILE)

```python
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
    """Create sample price data"""
    dates = pd.date_range("2020-01-01", "2023-12-31", freq="B")
    np.random.seed(42)
    
    gld = 150 * np.cumprod(1 + np.random.randn(len(dates)) * 0.01)
    tip = 120 * np.cumprod(1 + np.random.randn(len(dates)) * 0.005)
    
    return pd.DataFrame({
        "GLD": gld,
        "TIP": tip
    }, index=dates)


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
            engine._validate_expression({"GLD": 1.5, "TLT": -1.0})
    
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
```

---

## Task 5: Integration

**File:** `src/voyager/api/deps.py`

Add factory function for BacktestEngine and BacktestService:

```python
# Add to existing deps.py

from voyager.quant.backtest_engine import BacktestEngine, BacktestConfig
from voyager.services.v3.backtest_service import BacktestService
from voyager.repositories.backtest_result_repository import BacktestResultRepository

_backtest_engine_instance: Optional[BacktestEngine] = None
_backtest_service_instance: Optional[BacktestService] = None

def get_backtest_engine_instance() -> BacktestEngine:
    """Singleton factory for BacktestEngine"""
    global _backtest_engine_instance
    if _backtest_engine_instance is None:
        from voyager.db import get_engine
        db_engine = get_engine()
        config = BacktestConfig()  # Use defaults
        _backtest_engine_instance = BacktestEngine(db_engine, config)
    return _backtest_engine_instance

def get_backtest_service_instance() -> BacktestService:
    """Singleton factory for BacktestService"""
    global _backtest_service_instance
    if _backtest_service_instance is None:
        from voyager.db import get_engine
        db_engine = get_engine()
        
        backtest_engine = get_backtest_engine_instance()
        backtest_repo = BacktestResultRepository(db_engine)
        thesis_repo = get_data_access_instance().thesis_repo  # Reuse existing
        
        _backtest_service_instance = BacktestService(
            backtest_engine=backtest_engine,
            backtest_repo=backtest_repo,
            thesis_repo=thesis_repo
        )
    return _backtest_service_instance
```

---

## Task 6: CLI Tool

**File:** `src/voyager/scripts/backtest_cli.py` (NEW FILE)

```python
"""
CLI tool for testing backtests.

Usage:
    python -m voyager.scripts.backtest_cli run '{"GLD": 0.7, "TIP": 0.3}' --start 2020-01-01
    python -m voyager.scripts.backtest_cli thesis <thesis_id>
"""
import argparse
import json
from datetime import date

from voyager.api.deps import get_backtest_engine_instance, get_backtest_service_instance


def main():
    parser = argparse.ArgumentParser(description="Backtest CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Run expression directly
    run_parser = subparsers.add_parser("run", help="Run backtest on expression")
    run_parser.add_argument("expression", help="JSON expression, e.g., '{\"GLD\": 0.7}'")
    run_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    run_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    
    # Run for thesis
    thesis_parser = subparsers.add_parser("thesis", help="Run backtest for thesis")
    thesis_parser.add_argument("thesis_id", help="Thesis ID")
    thesis_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    thesis_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    if args.command == "run":
        engine = get_backtest_engine_instance()
        expression = json.loads(args.expression)
        
        result = engine.run(
            expression=expression,
            start_date=date.fromisoformat(args.start) if args.start else None,
            end_date=date.fromisoformat(args.end) if args.end else None
        )
        
        print(f"\n=== Backtest Results ===")
        print(f"Period: {result.period_start} to {result.period_end}")
        print(f"Total Return: {result.metrics.total_return:.2%}")
        print(f"CAGR: {result.metrics.cagr:.2%}")
        print(f"Volatility: {result.metrics.volatility:.2%}")
        print(f"Sharpe: {result.metrics.sharpe:.2f}")
        print(f"Max Drawdown: {result.metrics.max_drawdown:.2%}")
        print(f"Equity Curve Points: {len(result.equity_curve)}")
    
    elif args.command == "thesis":
        service = get_backtest_service_instance()
        
        result = service.run(
            thesis_id=args.thesis_id,
            start_date=args.start,
            end_date=args.end
        )
        
        print(f"\n=== Backtest Results for {args.thesis_id} ===")
        print(f"Iteration: #{result.iteration_count}")
        print(f"Period: {result.period_start} to {result.period_end}")
        print(f"Total Return: {result.metrics.total_return:.2%}")
        print(f"CAGR: {result.metrics.cagr:.2%}")
        print(f"Volatility: {result.metrics.volatility:.2%}")
        print(f"Sharpe: {result.metrics.sharpe:.2f}")
        print(f"Max Drawdown: {result.metrics.max_drawdown:.2%}")
        
        if result.factor_exposure:
            print(f"\n=== Factor Exposure ===")
            print(f"R²: {result.factor_exposure.r_squared:.2%}")
            for factor, beta in result.factor_exposure.betas.items():
                print(f"  {factor}: {beta:.3f}")


if __name__ == "__main__":
    main()
```

---

## Verification

After completing this phase:

1. Install VectorBT:
   ```bash
   pip install vectorbt
   ```

2. Test CLI:
   ```bash
   python -m voyager.scripts.backtest_cli run '{"GLD": 0.7, "TIP": 0.3}' --start 2020-01-01
   ```

3. Run tests:
   ```bash
   pytest tests/v3/test_backtest_engine.py -v
   ```

4. Verify results are persisted:
   ```sql
   SELECT * FROM backtest_result ORDER BY created_at DESC LIMIT 5;
   ```

---

## Dependencies

New:
- `vectorbt>=0.26.0`

Existing:
- `pandas`
- `numpy`
- `sqlalchemy`

---

## Migration Note: Backtrader

The existing Backtrader code in `src/voyager/quant_engine/` is NOT deleted by this phase. It can coexist while V3 is being built. Once V3 is stable, consider deprecating the old Backtrader code.

---

## Next Phase

Phase 3: LLM Layer — implements QueryTranslator and CritiqueEngine for Screens 1 and 2.