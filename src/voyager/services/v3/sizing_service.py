"""
Sizing Service for V3 Screen 4.

Computes position size based on:
- Risk constraints (Max DD tolerance, position cap)
- Backtest metrics (historical max DD)
- Portfolio context (correlation, marginal vol)
"""
from dataclasses import dataclass
from typing import Optional, List
import logging
import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text

from voyager.models.v3 import SizingResult, PortfolioImpact, BacktestResult
from voyager.models.thesis import Thesis, RiskRails
from voyager.repositories.backtest_result_repository import BacktestResultRepository
from voyager.repositories.trade_repo import TradeRepository


logger = logging.getLogger(__name__)


@dataclass
class PortfolioPosition:
    """Current portfolio position"""
    asset: str
    weight: float
    thesis_id: Optional[str] = None


class SizingService:
    """
    Computes position sizing for thesis activation.

    Core logic:
    1. implied_size = max_dd_tolerance / historical_max_dd
    2. capped_size = min(implied_size, position_cap)
    3. Compute portfolio impact (correlation, marginal vol)
    4. PM can manually adjust based on impact

    Usage:
        result = service.compute(thesis, rails, backtest)

        # PM sees:
        # - Suggested size: 10%
        # - Portfolio correlation: 0.58
        # - Marginal vol: +2.3%

        # PM can adjust final_size before activation
    """

    def __init__(
        self,
        engine: Engine,
        backtest_repo: BacktestResultRepository,
        trade_repo: TradeRepository
    ):
        self._engine = engine
        self._backtest_repo = backtest_repo
        self._trade_repo = trade_repo

    def compute(
        self,
        thesis: Thesis,
        rails: RiskRails,
        backtest: BacktestResult,
        include_portfolio_impact: bool = True
    ) -> SizingResult:
        """
        Compute sizing for a thesis.

        Args:
            thesis: The thesis to size
            rails: Risk constraints from PM
            backtest: Backtest results with metrics
            include_portfolio_impact: Whether to compute portfolio impact

        Returns:
            SizingResult with suggested size and portfolio impact

        Raises:
            ValueError: If backtest is None or max_drawdown is invalid
        """
        # Validate inputs
        if backtest is None:
            raise ValueError("Backtest required for sizing")

        historical_max_dd = backtest.metrics.max_drawdown

        if historical_max_dd <= 0:
            raise ValueError(
                f"Invalid historical max DD: {historical_max_dd}. "
                "Cannot compute sizing without valid drawdown data."
            )

        # Core sizing calculation
        implied_size = rails.max_dd_tolerance / historical_max_dd
        suggested_size = min(implied_size, rails.position_cap)

        # Ensure reasonable bounds
        suggested_size = max(0.0, min(1.0, suggested_size))

        # Portfolio impact
        portfolio_impact = None
        if include_portfolio_impact:
            try:
                portfolio_impact = self._compute_portfolio_impact(thesis, backtest)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Portfolio impact calculation failed: %s", e, exc_info=True)
                portfolio_impact = None

        return SizingResult(
            historical_max_dd=round(historical_max_dd, 4),
            tolerance=rails.max_dd_tolerance,
            implied_size=round(implied_size, 4),
            position_cap=rails.position_cap,
            suggested_size=round(suggested_size, 4),
            portfolio_impact=portfolio_impact
        )

    def _compute_portfolio_impact(
        self,
        thesis: Thesis,
        backtest: BacktestResult
    ) -> Optional[PortfolioImpact]:
        """
        Compute impact of adding this thesis to existing portfolio.

        Returns:
            PortfolioImpact with correlation and marginal vol, or None if no portfolio
        """
        # Get current portfolio positions
        portfolio = self._get_current_portfolio()

        if not portfolio:
            return None

        try:
            # Get thesis expression returns
            thesis_returns = self._get_expression_returns(backtest)

            # Get portfolio returns
            portfolio_returns = self._get_portfolio_returns(portfolio)

            if thesis_returns is None or portfolio_returns is None:
                return None

            # Align returns
            aligned = pd.concat([thesis_returns, portfolio_returns], axis=1, join="inner").dropna()

            if len(aligned) < 60:
                return None

            aligned.columns = ["thesis", "portfolio"]

            # Correlation
            correlation = aligned["thesis"].corr(aligned["portfolio"])

            # Marginal volatility contribution
            # Simplified: assume equal weight addition and compute new vol
            thesis_vol = aligned["thesis"].std() * np.sqrt(252)
            portfolio_vol = aligned["portfolio"].std() * np.sqrt(252)

            # New portfolio vol (simplified calculation)
            # Assumes adding thesis at some weight increases vol
            marginal_vol = self._compute_marginal_vol(
                thesis_vol, portfolio_vol, correlation
            )

            return PortfolioImpact(
                correlation_to_book=round(correlation, 4),
                marginal_vol=round(marginal_vol, 4)
            )

        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def _get_current_portfolio(self) -> List[PortfolioPosition]:
        """Get current portfolio positions from trades"""
        # Query active positions
        query = text("""
            SELECT
                asset,
                SUM(CASE WHEN action = 'BUY' THEN quantity ELSE -quantity END) as net_quantity
            FROM trade
            WHERE type = 'SIMULATED'
            GROUP BY asset
            HAVING SUM(CASE WHEN action = 'BUY' THEN quantity ELSE -quantity END) != 0
        """)

        try:
            with self._engine.connect() as conn:
                result = conn.execute(query)
                rows = result.fetchall()
        except Exception:  # pylint: disable=broad-exception-caught
            # Table might not exist or query might fail
            return []

        if not rows:
            return []

        # Convert to positions (simplified - assumes equal weighting)
        total = sum(abs(row.net_quantity) for row in rows)
        if total == 0:
            return []

        return [
            PortfolioPosition(
                asset=row.asset,
                weight=abs(row.net_quantity) / total
            )
            for row in rows
        ]

    def _get_expression_returns(self, backtest: BacktestResult) -> Optional[pd.Series]:
        """
        Reconstruct expression returns from backtest equity curve.

        Note: Precision loss due to Phase 2 sampling to 500 points.
        For more accurate portfolio impact, consider re-fetching price data.
        Acceptable for V3 sizing approximation.
        """
        if not backtest.equity_curve:
            return None

        # Convert equity curve to returns
        values = pd.Series(
            [ep.value for ep in backtest.equity_curve],
            index=pd.to_datetime([ep.date for ep in backtest.equity_curve])
        )

        returns = values.pct_change().dropna()
        return returns

    def _get_portfolio_returns(self, portfolio: List[PortfolioPosition]) -> Optional[pd.Series]:
        """Get weighted portfolio returns"""
        if not portfolio:
            return None

        # Fetch price data for portfolio assets
        assets = [p.asset for p in portfolio]
        weights = {p.asset: p.weight for p in portfolio}

        query = text("""
            SELECT date, ticker, close
            FROM market_data
            WHERE ticker = ANY(:tickers)
            AND date >= CURRENT_DATE - INTERVAL '2 years'
            ORDER BY date
        """)

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(query, conn, params={"tickers": assets})
        except Exception:  # pylint: disable=broad-exception-caught
            return None

        if df.empty:
            return None

        # Pivot and compute weighted returns
        df["date"] = pd.to_datetime(df["date"])
        prices = df.pivot(index="date", columns="ticker", values="close")

        returns = prices.pct_change().dropna()

        # Weight returns
        portfolio_returns = sum(
            returns[asset] * weights.get(asset, 0)
            for asset in returns.columns
            if asset in weights
        )

        return portfolio_returns

    def _compute_marginal_vol(
        self,
        thesis_vol: float,
        portfolio_vol: float,
        correlation: float,
        thesis_weight: float = 0.1  # Assume 10% allocation for marginal calc
    ) -> float:
        """
        Compute marginal volatility contribution.

        Uses portfolio variance formula:
        new_var = (1-w)²*port_var + w²*thesis_var + 2*w*(1-w)*corr*port_vol*thesis_vol
        """
        w = thesis_weight

        # Current portfolio variance
        port_var = portfolio_vol ** 2
        thesis_var = thesis_vol ** 2

        # New portfolio variance
        new_var = (
            (1 - w) ** 2 * port_var +
            w ** 2 * thesis_var +
            2 * w * (1 - w) * correlation * portfolio_vol * thesis_vol
        )

        new_vol = np.sqrt(new_var)
        marginal = new_vol - portfolio_vol

        return marginal


# ===========================================
# Sizing Helpers
# ===========================================

def compute_kelly_size(
    expected_return: float,
    volatility: float,
    win_rate: float = 0.5,
    kelly_fraction: float = 0.25  # Quarter Kelly by default
) -> float:
    """
    Compute Kelly criterion position size.

    This is NOT used in V3 default sizing but available for future use.

    Args:
        expected_return: Expected annualized return
        volatility: Annualized volatility
        win_rate: Probability of positive outcome
        kelly_fraction: Fraction of full Kelly (0.25 = quarter Kelly)

    Returns:
        Suggested position size as fraction
    """
    if volatility <= 0:
        return 0.0

    # Edge
    edge = expected_return

    # Kelly formula (simplified for continuous outcomes)
    kelly = edge / (volatility ** 2)

    # Apply fraction
    size = kelly * kelly_fraction

    # Bound to reasonable range
    return max(0.0, min(0.5, size))


def compute_vol_target_size(
    expression_vol: float,
    target_vol_contribution: float = 0.02  # 2% vol contribution
) -> float:
    """
    Compute size based on volatility targeting.

    This is NOT used in V3 default sizing but available for future use.

    Args:
        expression_vol: Annualized volatility of expression
        target_vol_contribution: Target vol contribution to portfolio

    Returns:
        Suggested position size as fraction
    """
    if expression_vol <= 0:
        return 0.0

    size = target_vol_contribution / expression_vol

    # Bound to reasonable range
    return max(0.0, min(0.5, size))
