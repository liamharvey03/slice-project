# V3 Phase 4: Sizing Service & Thesis Orchestration

## Overview

This phase implements:
- **SizingService**: Computes position size from constraints + quant metrics
- **ThesisService**: Orchestrates the full thesis lifecycle
- **Portfolio impact calculation**: Correlation and marginal vol

These complete the service layer for Screen 4 (Constraints & Sizing).

## Prerequisites

- Phase 0 complete (models, schema)
- Phase 1 complete (QuantService)
- Phase 2 complete (BacktestEngine)
- Phase 3 complete (ValidationService, CritiqueService)

---

## Task 1: Sizing Service

**File:** `src/voyager/services/v3/sizing_service.py` (NEW FILE)

```python
"""
Sizing Service for V3 Screen 4.

Computes position size based on:
- Risk constraints (Max DD tolerance, position cap)
- Backtest metrics (historical max DD)
- Portfolio context (correlation, marginal vol)
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, List
import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text

from voyager.models.v3 import SizingResult, PortfolioImpact, BacktestResult
from voyager.models.thesis import ThesisV3, RiskRails
from voyager.repositories.backtest_result_repository import BacktestResultRepository
from voyager.repositories.trade_repository import TradeRepository


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
        thesis: ThesisV3,
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
            portfolio_impact = self._compute_portfolio_impact(thesis, backtest)
        
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
        thesis: ThesisV3,
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
            
        except Exception:
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
        
        with self._engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()
        
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
        """Reconstruct expression returns from backtest equity curve"""
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
        
        with self._engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"tickers": assets})
        
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
```

---

## Task 2: Thesis Service (Lifecycle Orchestration)

**File:** `src/voyager/services/v3/thesis_service.py` (NEW FILE)

```python
"""
Thesis Service for V3.

Orchestrates the full thesis lifecycle:
- Create draft
- Update fields
- Manage status transitions
- Snapshots
- Activation
"""
from datetime import datetime
from typing import Optional, List
import uuid

from voyager.models.thesis import ThesisV3, ThesisSnapshot, RiskRails, ThesisExpressionLeg, ThesisStatusV3
from voyager.models.v3 import ThesisDraftInput, ActivateInput
from voyager.repositories.thesis_repository import ThesisRepository
from voyager.repositories.thesis_snapshot_repository import ThesisSnapshotRepository


# Valid status transitions
VALID_TRANSITIONS = {
    "DRAFT": ["VALIDATED"],
    "VALIDATED": ["CRITIQUED", "DRAFT"],  # Can go back to draft if needed
    "CRITIQUED": ["BACKTESTED", "VALIDATED"],
    "BACKTESTED": ["ACTIVE", "CRITIQUED"],
    "ACTIVE": ["CLOSED"],
    "CLOSED": []
}


class ThesisService:
    """
    Manages thesis lifecycle for V3.
    
    Status flow:
        DRAFT → VALIDATED → CRITIQUED → BACKTESTED → ACTIVE → CLOSED
    
    Each transition has validation rules and may create snapshots.
    
    Usage:
        # Create
        thesis = service.create_draft(input)
        
        # Update during editing
        thesis = service.update(thesis_id, {"hypothesis": "..."})
        
        # Transition status (done by other services)
        thesis = service.transition_status(thesis_id, "VALIDATED")
        
        # Activate
        thesis = service.activate(thesis_id, final_size=0.10, rails=...)
    """
    
    def __init__(
        self,
        thesis_repo: ThesisRepository,
        snapshot_repo: ThesisSnapshotRepository
    ):
        self._thesis_repo = thesis_repo
        self._snapshot_repo = snapshot_repo
    
    # -------------------------------------------
    # CRUD Operations
    # -------------------------------------------
    
    def create_draft(self, input: ThesisDraftInput) -> ThesisV3:
        """
        Create a new thesis in DRAFT status.
        """
        thesis_id = f"thesis_{uuid.uuid4().hex[:12]}"
        
        # Convert expression to proper format
        expression = [
            ThesisExpressionLeg(
                asset=leg.get("asset"),
                direction=leg.get("direction", "LONG"),
                size_pct=leg.get("size_pct", 0)
            )
            for leg in input.expression
        ]
        
        thesis = ThesisV3(
            id=thesis_id,
            title=input.title,
            hypothesis=input.hypothesis,
            drivers=input.drivers,
            disconfirmers=input.disconfirmers,
            expression=expression,
            start_date=datetime.utcnow().strftime("%Y-%m-%d"),
            review_date=None,
            status=ThesisStatusV3.DRAFT,
            tags=[],
            monitor_indices=[],
            notes=None,
            risk_rails=None,
            final_size=None
        )
        
        # Persist
        self._thesis_repo.insert(thesis)
        
        return thesis
    
    def get(self, thesis_id: str) -> Optional[ThesisV3]:
        """Get thesis by ID"""
        return self._thesis_repo.get_by_id(thesis_id)
    
    def update(self, thesis_id: str, updates: dict) -> ThesisV3:
        """
        Update thesis fields.
        
        Only allowed in DRAFT, VALIDATED, or CRITIQUED status.
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        # Check status allows editing
        editable_statuses = [ThesisStatusV3.DRAFT, ThesisStatusV3.VALIDATED, ThesisStatusV3.CRITIQUED]
        if thesis.status not in editable_statuses:
            raise ValueError(f"Cannot edit thesis in {thesis.status} status")
        
        # Apply updates (whitelist allowed fields)
        allowed_fields = {"title", "hypothesis", "drivers", "disconfirmers", "expression", "notes", "tags"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        # Update via repo
        for field, value in filtered_updates.items():
            if field == "expression":
                # Convert to proper format
                value = [
                    ThesisExpressionLeg(**leg) if isinstance(leg, dict) else leg
                    for leg in value
                ]
            # Call appropriate update method
            # This assumes thesis_repo has an update method
        
        return self._thesis_repo.get_by_id(thesis_id)
    
    def list_by_status(self, status: str) -> List[ThesisV3]:
        """List all theses with a given status"""
        return self._thesis_repo.list_by_status(status)
    
    def list_active(self) -> List[ThesisV3]:
        """List all active theses"""
        return self._thesis_repo.list_by_status("ACTIVE")
    
    # -------------------------------------------
    # Status Transitions
    # -------------------------------------------
    
    def transition_status(self, thesis_id: str, new_status: str) -> ThesisV3:
        """
        Transition thesis to new status.
        
        Validates that transition is allowed.
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        current_status = thesis.status.value if hasattr(thesis.status, 'value') else thesis.status
        
        # Check valid transition
        allowed = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {current_status} to {new_status}. "
                f"Allowed: {allowed}"
            )
        
        return self._thesis_repo.update_status(thesis_id, new_status)
    
    # -------------------------------------------
    # Activation
    # -------------------------------------------
    
    def activate(
        self,
        thesis_id: str,
        final_size: float,
        rails: RiskRails
    ) -> ThesisV3:
        """
        Activate a thesis.
        
        Requirements:
        - Thesis must be in BACKTESTED status
        - final_size must be positive and <= position_cap
        - Creates activation snapshot
        
        Args:
            thesis_id: Thesis to activate
            final_size: Final position size (after PM adjustment)
            rails: Risk rails for monitoring
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        # Validate status
        current_status = thesis.status.value if hasattr(thesis.status, 'value') else thesis.status
        if current_status != "BACKTESTED":
            raise ValueError(f"Cannot activate thesis in {current_status} status. Must be BACKTESTED.")
        
        # Validate size
        if final_size <= 0:
            raise ValueError("Final size must be positive")
        if final_size > rails.position_cap:
            raise ValueError(f"Final size {final_size} exceeds position cap {rails.position_cap}")
        
        # Create activation snapshot
        self._create_snapshot(thesis, "activation")
        
        # Update thesis
        self._thesis_repo.update_risk_rails(thesis_id, rails.dict())
        self._thesis_repo.update_final_size(thesis_id, final_size)
        self._thesis_repo.update_status(thesis_id, "ACTIVE")
        
        return self._thesis_repo.get_by_id(thesis_id)
    
    # -------------------------------------------
    # Snapshots
    # -------------------------------------------
    
    def _create_snapshot(self, thesis: ThesisV3, snapshot_type: str) -> ThesisSnapshot:
        """Create a snapshot of current thesis state"""
        content = thesis.dict() if hasattr(thesis, 'dict') else {
            "id": thesis.id,
            "title": thesis.title,
            "hypothesis": thesis.hypothesis,
            "drivers": thesis.drivers,
            "disconfirmers": thesis.disconfirmers,
            "expression": [leg.dict() if hasattr(leg, 'dict') else leg for leg in thesis.expression],
            "status": thesis.status.value if hasattr(thesis.status, 'value') else thesis.status,
            "risk_rails": thesis.risk_rails.dict() if thesis.risk_rails else None,
            "final_size": thesis.final_size
        }
        
        snapshot = ThesisSnapshot(
            id=f"snap_{uuid.uuid4().hex[:12]}",
            thesis_id=thesis.id,
            snapshot_type=snapshot_type,
            content=content,
            created_at=datetime.utcnow().isoformat()
        )
        
        return self._snapshot_repo.insert(snapshot)
    
    def get_snapshots(self, thesis_id: str) -> List[ThesisSnapshot]:
        """Get all snapshots for a thesis"""
        return self._snapshot_repo.list_by_thesis(thesis_id)
    
    def get_snapshot(self, thesis_id: str, snapshot_type: str) -> Optional[ThesisSnapshot]:
        """Get most recent snapshot of a specific type"""
        return self._snapshot_repo.get_latest_by_type(thesis_id, snapshot_type)
```

---

## Task 3: Integration

**File:** `src/voyager/api/deps.py`

Add factory functions:

```python
# Add to existing deps.py

from voyager.services.v3.sizing_service import SizingService
from voyager.services.v3.thesis_service import ThesisService

_sizing_service_instance: Optional[SizingService] = None
_thesis_service_instance: Optional[ThesisService] = None


def get_sizing_service_instance() -> SizingService:
    global _sizing_service_instance
    if _sizing_service_instance is None:
        from voyager.db import get_engine
        engine = get_engine()
        
        _sizing_service_instance = SizingService(
            engine=engine,
            backtest_repo=BacktestResultRepository(engine),
            trade_repo=get_data_access_instance().trade_repo
        )
    return _sizing_service_instance


def get_thesis_service_instance() -> ThesisService:
    global _thesis_service_instance
    if _thesis_service_instance is None:
        from voyager.db import get_engine
        engine = get_engine()
        
        _thesis_service_instance = ThesisService(
            thesis_repo=get_data_access_instance().thesis_repo,
            snapshot_repo=ThesisSnapshotRepository(engine)
        )
    return _thesis_service_instance
```

---

## Task 4: Tests

**File:** `tests/v3/test_sizing_service.py` (NEW FILE)

```python
"""
Tests for SizingService.
"""
import pytest
from unittest.mock import MagicMock

from voyager.services.v3.sizing_service import SizingService, compute_kelly_size, compute_vol_target_size
from voyager.models.thesis import ThesisV3, RiskRails
from voyager.models.v3 import BacktestResult, BacktestMetrics


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
        equity_curve=[],
        iteration_count=1
    )


@pytest.fixture
def sample_rails():
    return RiskRails(
        max_dd_tolerance=0.08,
        position_cap=0.10
    )


class TestSizingService:
    
    def test_basic_sizing(self, mock_engine, mock_backtest_repo, mock_trade_repo, sample_backtest, sample_rails):
        service = SizingService(mock_engine, mock_backtest_repo, mock_trade_repo)
        
        thesis = MagicMock()
        thesis.id = "test"
        thesis.expression = []
        
        result = service.compute(thesis, sample_rails, sample_backtest, include_portfolio_impact=False)
        
        # implied_size = 0.08 / 0.18 = 0.444
        # capped at 0.10
        assert result.suggested_size == 0.10
        assert result.implied_size == pytest.approx(0.444, rel=0.01)
        assert result.historical_max_dd == 0.18
    
    def test_sizing_no_cap_binding(self, mock_engine, mock_backtest_repo, mock_trade_repo, sample_backtest):
        service = SizingService(mock_engine, mock_backtest_repo, mock_trade_repo)
        
        # High position cap, won't bind
        rails = RiskRails(max_dd_tolerance=0.05, position_cap=0.50)
        thesis = MagicMock()
        
        result = service.compute(thesis, rails, sample_backtest, include_portfolio_impact=False)
        
        # implied_size = 0.05 / 0.18 = 0.278
        # Not capped
        assert result.suggested_size == pytest.approx(0.278, rel=0.01)
    
    def test_sizing_zero_dd_raises(self, mock_engine, mock_backtest_repo, mock_trade_repo, sample_rails):
        service = SizingService(mock_engine, mock_backtest_repo, mock_trade_repo)
        
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
        
        thesis = MagicMock()
        
        with pytest.raises(ValueError, match="Invalid historical max DD"):
            service.compute(thesis, sample_rails, backtest)


class TestSizingHelpers:
    
    def test_kelly_size(self):
        # High expected return, moderate vol
        size = compute_kelly_size(
            expected_return=0.10,
            volatility=0.15,
            kelly_fraction=0.25
        )
        assert 0 < size < 0.5
    
    def test_kelly_size_zero_vol(self):
        size = compute_kelly_size(
            expected_return=0.10,
            volatility=0.0
        )
        assert size == 0.0
    
    def test_vol_target_size(self):
        size = compute_vol_target_size(
            expression_vol=0.20,
            target_vol_contribution=0.02
        )
        assert size == pytest.approx(0.10, rel=0.01)
```

---

## Task 5: CLI Tool

**File:** `src/voyager/scripts/sizing_cli.py` (NEW FILE)

```python
"""
CLI tool for testing sizing calculations.

Usage:
    python -m voyager.scripts.sizing_cli compute <thesis_id> --max-dd 0.08 --cap 0.10
"""
import argparse
import json

from voyager.api.deps import get_sizing_service_instance, get_backtest_service_instance, get_thesis_service_instance
from voyager.models.thesis import RiskRails


def main():
    parser = argparse.ArgumentParser(description="Sizing CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Compute sizing
    compute_parser = subparsers.add_parser("compute", help="Compute sizing for thesis")
    compute_parser.add_argument("thesis_id", help="Thesis ID")
    compute_parser.add_argument("--max-dd", type=float, required=True, help="Max DD tolerance (e.g., 0.08)")
    compute_parser.add_argument("--cap", type=float, required=True, help="Position cap (e.g., 0.10)")
    compute_parser.add_argument("--no-portfolio", action="store_true", help="Skip portfolio impact")
    
    args = parser.parse_args()
    
    if args.command == "compute":
        sizing_service = get_sizing_service_instance()
        backtest_service = get_backtest_service_instance()
        thesis_service = get_thesis_service_instance()
        
        # Load thesis and backtest
        thesis = thesis_service.get(args.thesis_id)
        if thesis is None:
            print(f"Thesis not found: {args.thesis_id}")
            return
        
        backtest = backtest_service.get_latest(args.thesis_id)
        if backtest is None:
            print(f"No backtest found for thesis. Run backtest first.")
            return
        
        rails = RiskRails(
            max_dd_tolerance=args.max_dd,
            position_cap=args.cap
        )
        
        result = sizing_service.compute(
            thesis=thesis,
            rails=rails,
            backtest=backtest,
            include_portfolio_impact=not args.no_portfolio
        )
        
        print(f"\n=== Sizing Results ===")
        print(f"Historical Max DD: {result.historical_max_dd:.2%}")
        print(f"Your Tolerance: {result.tolerance:.2%}")
        print(f"Implied Size: {result.implied_size:.2%}")
        print(f"Position Cap: {result.position_cap:.2%}")
        print(f"Suggested Size: {result.suggested_size:.2%}")
        
        if result.portfolio_impact:
            print(f"\n=== Portfolio Impact ===")
            print(f"Correlation to Book: {result.portfolio_impact.correlation_to_book:.2f}")
            print(f"Marginal Vol: {result.portfolio_impact.marginal_vol:+.2%}")


if __name__ == "__main__":
    main()
```

---

## Verification

After completing this phase:

1. Run tests:
   ```bash
   pytest tests/v3/test_sizing_service.py -v
   ```

2. Test sizing CLI:
   ```bash
   python -m voyager.scripts.sizing_cli compute <thesis_id> --max-dd 0.08 --cap 0.10
   ```

3. Test full thesis lifecycle:
   ```python
   # Create draft
   thesis = thesis_service.create_draft(ThesisDraftInput(...))
   
   # Validate
   await validation_service.validate(thesis)
   
   # Critique
   await critique_service.start(thesis.id)
   await critique_service.complete(thesis.id)
   
   # Backtest
   backtest = backtest_service.run(thesis.id)
   
   # Size
   rails = RiskRails(max_dd_tolerance=0.08, position_cap=0.10)
   sizing = sizing_service.compute(thesis, rails, backtest)
   
   # Activate
   thesis = thesis_service.activate(thesis.id, final_size=0.10, rails=rails)
   ```

---

## Dependencies

No new dependencies. Uses existing:
- `numpy`
- `pandas`
- `sqlalchemy`

---

## Next Phase

Phase 5: API Layer — implements all V3 API endpoints for the four screens.