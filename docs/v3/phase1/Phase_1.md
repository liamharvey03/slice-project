# V3 Phase 1: Quant Service

## Overview

This phase implements the `QuantService` — the engine that executes quantitative queries against market and economic data. It powers the logic validation in Screen 1.

## Prerequisites

- Phase 0 complete (schema, models, series registry)
- Existing `market_data` and `econ_data` tables populated
- Existing FRED/TwelveData fetch infrastructure

---

## Task 1: Quant Service Core

**File:** `src/voyager/quant/quant_service.py` (NEW FILE)

```python
"""
Quant Service for V3 thesis validation.

Executes quantitative queries: correlations, conditional returns, distributions.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Literal
import pandas as pd
import numpy as np
from sqlalchemy import text
from sqlalchemy.engine import Engine

from voyager.data.series_registry import SeriesRegistry, SeriesEntry


# ===========================================
# Result Models
# ===========================================

@dataclass
class CorrelationResult:
    """Result of a correlation query"""
    series_a: str
    series_b: str
    correlation: float
    period_start: date
    period_end: date
    n_observations: int
    p_value: Optional[float] = None


@dataclass
class ConditionalReturnsResult:
    """Result of a conditional returns query"""
    asset: str
    condition: str
    mean_return: float
    median_return: float
    std_return: float
    n_periods: int
    total_periods: int
    pct_condition_true: float
    # Returns when condition is true vs false
    mean_return_when_false: Optional[float] = None


@dataclass
class DistributionResult:
    """Result of a distribution query"""
    series: str
    mean: float
    std: float
    min: float
    max: float
    current: float
    percentiles: dict  # {"10": ..., "25": ..., "50": ..., "75": ..., "90": ...}
    percentile_rank: float  # Where current value sits


# ===========================================
# Quant Service
# ===========================================

class QuantService:
    """
    Executes quantitative queries against market and economic data.
    
    Usage:
        quant = QuantService(engine, registry)
        result = quant.correlation("DFII10", "GLD", period="5Y")
    """
    
    def __init__(self, engine: Engine, registry: SeriesRegistry):
        self._engine = engine
        self._registry = registry
    
    # -------------------------------------------
    # Data Fetching
    # -------------------------------------------
    
    def _parse_period(self, period: str, end_date: date = None) -> tuple[date, date]:
        """
        Parse period string into start/end dates.
        
        Args:
            period: "1Y", "3Y", "5Y", "10Y", "MAX", or "YYYY-MM-DD:YYYY-MM-DD"
        """
        end = end_date or date.today()
        
        if ":" in period:
            # Explicit date range
            start_str, end_str = period.split(":")
            return date.fromisoformat(start_str), date.fromisoformat(end_str)
        
        period_map = {
            "1Y": 365,
            "2Y": 365 * 2,
            "3Y": 365 * 3,
            "5Y": 365 * 5,
            "10Y": 365 * 10,
            "MAX": 365 * 30,
        }
        
        days = period_map.get(period.upper(), 365 * 5)  # Default 5Y
        start = end - timedelta(days=days)
        
        return start, end
    
    def _fetch_series(
        self, 
        series_id: str, 
        start: date, 
        end: date
    ) -> pd.Series:
        """
        Fetch a data series from the appropriate table.
        
        Returns a pandas Series indexed by date.
        """
        entry = self._registry.get_by_id(series_id)
        if entry is None:
            raise ValueError(f"Unknown series: {series_id}")
        
        if entry.source == "FRED":
            query = text("""
                SELECT date, value 
                FROM econ_data 
                WHERE series_id = :series_id
                AND date >= :start AND date <= :end
                ORDER BY date
            """)
            value_col = "value"
        else:  # TwelveData
            query = text("""
                SELECT date, close as value 
                FROM market_data
                WHERE ticker = :series_id
                AND date >= :start AND date <= :end
                ORDER BY date
            """)
            value_col = "value"
        
        with self._engine.connect() as conn:
            df = pd.read_sql(query, conn, params={
                "series_id": series_id, 
                "start": start, 
                "end": end
            })
        
        if df.empty:
            raise ValueError(f"No data for {series_id} between {start} and {end}")
        
        # Convert to series with date index
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date")["value"]
    
    def _to_returns(self, series: pd.Series, entry: SeriesEntry) -> pd.Series:
        """
        Convert series to returns if it's a price series.
        FRED series (rates, levels) stay as-is or use changes.
        """
        if entry.source == "TwelveData":
            # Price series -> returns
            return series.pct_change().dropna()
        else:
            # FRED series -> use level changes for rates
            if entry.category == "rates":
                return series.diff().dropna()
            return series
    
    # -------------------------------------------
    # Query Methods
    # -------------------------------------------
    
    def correlation(
        self,
        series_a: str,
        series_b: str,
        period: str = "5Y",
        use_returns: bool = True
    ) -> CorrelationResult:
        """
        Compute correlation between two series.
        
        Args:
            series_a: First series ID (e.g., "DFII10")
            series_b: Second series ID (e.g., "GLD")
            period: Time period ("1Y", "5Y", "10Y", "MAX", or "YYYY-MM-DD:YYYY-MM-DD")
            use_returns: If True, correlate returns/changes. If False, correlate levels.
            
        Returns:
            CorrelationResult with correlation coefficient and metadata
        """
        start, end = self._parse_period(period)
        
        # Fetch series
        sa = self._fetch_series(series_a, start, end)
        sb = self._fetch_series(series_b, start, end)
        
        # Get entries for return conversion logic
        entry_a = self._registry.get_by_id(series_a)
        entry_b = self._registry.get_by_id(series_b)
        
        if use_returns:
            sa = self._to_returns(sa, entry_a)
            sb = self._to_returns(sb, entry_b)
        
        # Align on common dates
        aligned = pd.concat([sa, sb], axis=1, join="inner").dropna()
        aligned.columns = ["a", "b"]
        
        if len(aligned) < 20:
            raise ValueError(f"Insufficient overlapping data: only {len(aligned)} observations")
        
        # Compute correlation
        corr = aligned["a"].corr(aligned["b"])
        
        # Compute p-value using scipy if available
        p_value = None
        try:
            from scipy import stats
            _, p_value = stats.pearsonr(aligned["a"], aligned["b"])
        except ImportError:
            pass
        
        return CorrelationResult(
            series_a=series_a,
            series_b=series_b,
            correlation=round(corr, 4),
            period_start=aligned.index.min().date(),
            period_end=aligned.index.max().date(),
            n_observations=len(aligned),
            p_value=round(p_value, 4) if p_value is not None else None
        )
    
    def conditional_returns(
        self,
        asset: str,
        condition_series: str,
        condition_op: Literal[">", "<", ">=", "<="],
        condition_value: float,
        period: str = "5Y"
    ) -> ConditionalReturnsResult:
        """
        Compute returns of an asset conditional on another series.
        
        Example: "Returns of GLD when real yields (DFII10) > 2.0"
        
        Args:
            asset: Asset to measure returns (e.g., "GLD")
            condition_series: Series for condition (e.g., "DFII10")
            condition_op: Comparison operator
            condition_value: Threshold value
            period: Time period
            
        Returns:
            ConditionalReturnsResult with returns statistics
        """
        start, end = self._parse_period(period)
        
        # Fetch data
        prices = self._fetch_series(asset, start, end)
        condition_data = self._fetch_series(condition_series, start, end)
        
        # Convert prices to returns
        entry = self._registry.get_by_id(asset)
        returns = self._to_returns(prices, entry)
        
        # Align - use previous day's condition for current return (avoid look-ahead)
        condition_shifted = condition_data.shift(1)
        aligned = pd.concat([returns, condition_shifted], axis=1, join="inner").dropna()
        aligned.columns = ["returns", "condition"]
        
        # Apply condition
        ops = {
            ">": lambda x, v: x > v,
            "<": lambda x, v: x < v,
            ">=": lambda x, v: x >= v,
            "<=": lambda x, v: x <= v,
        }
        mask = ops[condition_op](aligned["condition"], condition_value)
        
        returns_when_true = aligned.loc[mask, "returns"]
        returns_when_false = aligned.loc[~mask, "returns"]
        
        return ConditionalReturnsResult(
            asset=asset,
            condition=f"{condition_series} {condition_op} {condition_value}",
            mean_return=round(returns_when_true.mean(), 6) if len(returns_when_true) > 0 else 0.0,
            median_return=round(returns_when_true.median(), 6) if len(returns_when_true) > 0 else 0.0,
            std_return=round(returns_when_true.std(), 6) if len(returns_when_true) > 0 else 0.0,
            n_periods=int(mask.sum()),
            total_periods=len(aligned),
            pct_condition_true=round(mask.mean() * 100, 2),
            mean_return_when_false=round(returns_when_false.mean(), 6) if len(returns_when_false) > 0 else None
        )
    
    def distribution(
        self,
        series: str,
        period: str = "10Y"
    ) -> DistributionResult:
        """
        Get historical distribution statistics for a series.
        
        Useful for understanding where current value sits historically.
        
        Args:
            series: Series ID
            period: Time period
            
        Returns:
            DistributionResult with distribution statistics
        """
        start, end = self._parse_period(period)
        
        data = self._fetch_series(series, start, end)
        current = data.iloc[-1]
        
        # Compute percentile rank of current value
        percentile_rank = (data < current).mean() * 100
        
        return DistributionResult(
            series=series,
            mean=round(data.mean(), 4),
            std=round(data.std(), 4),
            min=round(data.min(), 4),
            max=round(data.max(), 4),
            current=round(current, 4),
            percentiles={
                "10": round(data.quantile(0.10), 4),
                "25": round(data.quantile(0.25), 4),
                "50": round(data.quantile(0.50), 4),
                "75": round(data.quantile(0.75), 4),
                "90": round(data.quantile(0.90), 4),
            },
            percentile_rank=round(percentile_rank, 1)
        )
    
    def relationship_strength(
        self,
        series_a: str,
        series_b: str,
        expected_direction: Literal["positive", "negative"],
        period: str = "5Y"
    ) -> dict:
        """
        Evaluate the strength of a claimed relationship.
        
        Convenience method that combines correlation with interpretation.
        
        Args:
            series_a: First series
            series_b: Second series
            expected_direction: What the thesis claims ("positive" or "negative")
            period: Time period
            
        Returns:
            Dict with correlation, interpretation, and confidence
        """
        result = self.correlation(series_a, series_b, period)
        
        # Interpret
        corr = result.correlation
        expected_sign = 1 if expected_direction == "positive" else -1
        actual_sign = 1 if corr > 0 else -1
        
        # Direction match?
        direction_matches = (expected_sign == actual_sign)
        
        # Strength classification
        abs_corr = abs(corr)
        if abs_corr >= 0.7:
            strength = "strong"
        elif abs_corr >= 0.4:
            strength = "moderate"
        elif abs_corr >= 0.2:
            strength = "weak"
        else:
            strength = "negligible"
        
        # Overall interpretation
        if not direction_matches:
            interpretation = "contradicts"
            confidence = "high" if abs_corr >= 0.3 else "low"
        elif strength in ["strong", "moderate"]:
            interpretation = "supports"
            confidence = "high" if strength == "strong" else "medium"
        elif strength == "weak":
            interpretation = "weak"
            confidence = "low"
        else:
            interpretation = "contradicts"
            confidence = "low"
        
        return {
            "correlation": corr,
            "expected_direction": expected_direction,
            "actual_direction": "positive" if corr > 0 else "negative",
            "direction_matches": direction_matches,
            "strength": strength,
            "interpretation": interpretation,
            "confidence": confidence,
            "n_observations": result.n_observations,
            "p_value": result.p_value
        }
```

---

## Task 2: Quant Service Tests

**File:** `tests/v3/test_quant_service.py` (NEW FILE)

```python
"""
Tests for QuantService.
"""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from voyager.quant.quant_service import QuantService, CorrelationResult
from voyager.data.series_registry import SeriesRegistry, SeriesEntry


@pytest.fixture
def mock_registry():
    """Create a mock registry with test series"""
    registry = MagicMock(spec=SeriesRegistry)
    
    registry.get_by_id.side_effect = lambda x: {
        "GLD": SeriesEntry("GLD", "TwelveData", "Gold", "commodity", ["gold"], "daily"),
        "DFII10": SeriesEntry("DFII10", "FRED", "10Y Real Yield", "rates", ["real yields"], "daily"),
        "SPY": SeriesEntry("SPY", "TwelveData", "S&P 500", "equity", ["stocks"], "daily"),
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
    
    def test_correlation_insufficient_data(self, mock_engine, mock_registry):
        """Test that correlation raises error with insufficient data"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Mock fetch to return very little data
        with patch.object(quant, '_fetch_series') as mock_fetch:
            mock_fetch.return_value = pd.Series([1, 2, 3], index=pd.date_range("2023-01-01", periods=3))
            
            with pytest.raises(ValueError, match="Insufficient"):
                quant.correlation("GLD", "DFII10")
    
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
            
            assert result["interpretation"] == "supports"
            assert result["direction_matches"] is True
            assert result["strength"] == "moderate"
    
    def test_conditional_returns_logic(self, mock_engine, mock_registry):
        """Test conditional returns calculation"""
        quant = QuantService(mock_engine, mock_registry)
        
        # Create test data
        dates = pd.date_range("2023-01-01", periods=100)
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
```

---

## Task 3: Integration with Existing Data Layer

**File:** `src/voyager/api/deps.py`

Add factory function for QuantService:

```python
# Add to existing deps.py

from voyager.quant.quant_service import QuantService
from voyager.data.series_registry import SeriesRegistry

_quant_service_instance: Optional[QuantService] = None
_series_registry_instance: Optional[SeriesRegistry] = None

def get_series_registry_instance() -> SeriesRegistry:
    """Singleton factory for SeriesRegistry"""
    global _series_registry_instance
    if _series_registry_instance is None:
        _series_registry_instance = SeriesRegistry()
    return _series_registry_instance

def get_quant_service_instance() -> QuantService:
    """Singleton factory for QuantService"""
    global _quant_service_instance
    if _quant_service_instance is None:
        from voyager.db import get_engine  # Adjust import based on your setup
        engine = get_engine()
        registry = get_series_registry_instance()
        _quant_service_instance = QuantService(engine, registry)
    return _quant_service_instance
```

---

## Task 4: CLI Tool for Testing

**File:** `src/voyager/scripts/quant_cli.py` (NEW FILE)

```python
"""
CLI tool for testing quant queries.

Usage:
    python -m voyager.scripts.quant_cli correlation DFII10 GLD --period 5Y
    python -m voyager.scripts.quant_cli conditional GLD DFII10 ">" 2.0
    python -m voyager.scripts.quant_cli distribution DFII10
"""
import argparse
import json
from dataclasses import asdict

from voyager.api.deps import get_quant_service_instance


def main():
    parser = argparse.ArgumentParser(description="Quant Service CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Correlation command
    corr_parser = subparsers.add_parser("correlation", help="Compute correlation")
    corr_parser.add_argument("series_a", help="First series ID")
    corr_parser.add_argument("series_b", help="Second series ID")
    corr_parser.add_argument("--period", default="5Y", help="Time period (default: 5Y)")
    
    # Conditional returns command
    cond_parser = subparsers.add_parser("conditional", help="Compute conditional returns")
    cond_parser.add_argument("asset", help="Asset ID")
    cond_parser.add_argument("condition_series", help="Condition series ID")
    cond_parser.add_argument("operator", choices=[">", "<", ">=", "<="])
    cond_parser.add_argument("value", type=float, help="Condition threshold")
    cond_parser.add_argument("--period", default="5Y", help="Time period (default: 5Y)")
    
    # Distribution command
    dist_parser = subparsers.add_parser("distribution", help="Get distribution stats")
    dist_parser.add_argument("series", help="Series ID")
    dist_parser.add_argument("--period", default="10Y", help="Time period (default: 10Y)")
    
    # Relationship command
    rel_parser = subparsers.add_parser("relationship", help="Evaluate relationship strength")
    rel_parser.add_argument("series_a", help="First series ID")
    rel_parser.add_argument("series_b", help="Second series ID")
    rel_parser.add_argument("direction", choices=["positive", "negative"])
    rel_parser.add_argument("--period", default="5Y", help="Time period (default: 5Y)")
    
    args = parser.parse_args()
    quant = get_quant_service_instance()
    
    if args.command == "correlation":
        result = quant.correlation(args.series_a, args.series_b, args.period)
        print(json.dumps(asdict(result), indent=2, default=str))
    
    elif args.command == "conditional":
        result = quant.conditional_returns(
            args.asset, 
            args.condition_series, 
            args.operator, 
            args.value, 
            args.period
        )
        print(json.dumps(asdict(result), indent=2, default=str))
    
    elif args.command == "distribution":
        result = quant.distribution(args.series, args.period)
        print(json.dumps(asdict(result), indent=2, default=str))
    
    elif args.command == "relationship":
        result = quant.relationship_strength(
            args.series_a, 
            args.series_b, 
            args.direction, 
            args.period
        )
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
```

---

## Verification

After completing this phase:

1. Ensure `market_data` and `econ_data` tables have data:
   ```sql
   SELECT COUNT(*) FROM market_data WHERE ticker = 'GLD';
   SELECT COUNT(*) FROM econ_data WHERE series_id = 'DFII10';
   ```

2. Test CLI tool:
   ```bash
   python -m voyager.scripts.quant_cli correlation DFII10 GLD --period 5Y
   python -m voyager.scripts.quant_cli relationship DFII10 GLD negative --period 5Y
   python -m voyager.scripts.quant_cli distribution DFII10
   ```

3. Run tests:
   ```bash
   pytest tests/v3/test_quant_service.py -v
   ```

---

## Dependencies

New dependencies to add:
```
scipy  # For p-value calculation (optional but recommended)
```

Existing dependencies used:
- `pandas`
- `numpy`
- `sqlalchemy`

---

## Next Phase

Phase 2: Backtest Engine — implements VectorBT-based backtesting to replace Backtrader.