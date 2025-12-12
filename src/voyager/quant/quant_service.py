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
# Constants
# ===========================================

MIN_OBS = 20  # Minimum observations for statistical validity (referenceable by LLM)


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


@dataclass
class RelationshipStrengthResult:
    """Result of relationship strength evaluation"""
    correlation: float
    expected_direction: str
    actual_direction: str
    direction_matches: bool
    strength: str  # "strong" | "moderate" | "weak" | "negligible"
    interpretation: str  # "supports" | "contradicts" | "weak"
    confidence: str
    n_observations: int
    p_value: Optional[float] = None
    # Future extensibility: rolling_corr, beta, stability


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
        Convert series to returns based on entry.return_type.
        
        Uses explicit return_type from registry, not heuristics.
        """
        if entry.return_type == "pct_change":
            return series.pct_change().dropna()
        elif entry.return_type == "diff":
            return series.diff().dropna()
        elif entry.return_type == "level":
            return series
        else:  # "none" or unknown
            return series
    
    def _align_series(
        self, 
        sa: pd.Series, 
        sb: pd.Series, 
        rule: Literal["inner", "asof", "ffill"] = "inner"
    ) -> pd.DataFrame:
        """
        Align two series on common dates.
        
        Args:
            sa: First series
            sb: Second series
            rule: Alignment rule ("inner", "asof", "ffill")
            
        Returns:
            DataFrame with aligned series
        """
        if rule == "inner":
            aligned = pd.concat([sa, sb], axis=1, join="inner").dropna()
            aligned.columns = ["a", "b"]
            return aligned
        # Future: asof, ffill for mismatched calendars
        raise NotImplementedError(f"Alignment rule '{rule}' not yet implemented")
    
    # -------------------------------------------
    # Query Methods
    # -------------------------------------------
    
    def correlation(
        self,
        series_a: str,
        series_b: str,
        period: str = "5Y",
        use_returns: bool = True,
        align: Literal["inner", "asof", "ffill"] = "inner"
    ) -> CorrelationResult:
        """
        Compute correlation between two series.
        
        Args:
            series_a: First series ID (e.g., "DFII10")
            series_b: Second series ID (e.g., "GLD")
            period: Time period ("1Y", "5Y", "10Y", "MAX", or "YYYY-MM-DD:YYYY-MM-DD")
            use_returns: If True, correlate returns/changes. If False, correlate levels.
            align: Alignment rule for mismatched calendars
            
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
        aligned = self._align_series(sa, sb, rule=align)
        
        if len(aligned) < MIN_OBS:
            raise ValueError(
                f"Insufficient overlapping data: only {len(aligned)} observations "
                f"(minimum: {MIN_OBS})"
            )
        
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
            
        Note:
            Returns refer to the next period after the condition is met.
            Condition is shifted by 1 day to avoid forward-looking bias.
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
        aligned = pd.concat([returns, condition_shifted], axis=1, join="inner")
        aligned.columns = ["returns", "condition"]
        
        # Explicitly drop rows where condition is missing
        aligned = aligned[aligned["condition"].notna()]
        
        if len(aligned) < MIN_OBS:
            raise ValueError(
                f"Insufficient overlapping data: only {len(aligned)} observations "
                f"(minimum: {MIN_OBS})"
            )
        
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
        period: str = "10Y",
        on: Literal["levels", "returns"] = "levels"
    ) -> DistributionResult:
        """
        Get historical distribution statistics for a series.
        
        Useful for understanding where current value sits historically.
        
        Args:
            series: Series ID
            period: Time period
            on: Whether to compute on "levels" or "returns"
            
        Returns:
            DistributionResult with distribution statistics
        """
        start, end = self._parse_period(period)
        
        data = self._fetch_series(series, start, end)
        
        # Convert to returns if requested
        if on == "returns":
            entry = self._registry.get_by_id(series)
            data = self._to_returns(data, entry)
        
        if len(data) < MIN_OBS:
            raise ValueError(
                f"Insufficient data: only {len(data)} observations "
                f"(minimum: {MIN_OBS})"
            )
        
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
    ) -> RelationshipStrengthResult:
        """
        Evaluate the strength of a claimed relationship.
        
        Convenience method that combines correlation with interpretation.
        
        Args:
            series_a: First series
            series_b: Second series
            expected_direction: What the thesis claims ("positive" or "negative")
            period: Time period
            
        Returns:
            RelationshipStrengthResult with correlation, interpretation, and confidence
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
        
        return RelationshipStrengthResult(
            correlation=corr,
            expected_direction=expected_direction,
            actual_direction="positive" if corr > 0 else "negative",
            direction_matches=direction_matches,
            strength=strength,
            interpretation=interpretation,
            confidence=confidence,
            n_observations=result.n_observations,
            p_value=result.p_value
        )
