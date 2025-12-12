"""
Backtest Service for V3.

Orchestrates backtest execution and result persistence.
"""
from datetime import date, datetime
from typing import Optional
import uuid

from voyager.quant.backtest_engine import BacktestEngine, BacktestConfig, expression_from_legs
from voyager.models.v3 import BacktestResult
from voyager.repositories.backtest_result_repository import BacktestResultRepository
from voyager.repositories.thesis_repo import ThesisRepository


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
        
        # Convert expression legs to dict (handle V2/V3 format compatibility)
        if not thesis.expression:
            raise ValueError("Thesis has no expression legs")
        
        # Handle both V2 (Pydantic models) and V3 (dicts) formats
        if hasattr(thesis.expression[0], 'dict'):
            legs = [leg.dict() for leg in thesis.expression]
        else:
            legs = thesis.expression  # Already dicts
        
        expression = expression_from_legs(legs)
        
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
        if include_factor_exposure:
            try:
                factor_start = start if start else date.fromisoformat(result.period_start)
                factor_end = end if end else date.fromisoformat(result.period_end)
                factor_exposure = self._engine.compute_factor_exposure(
                    expression=expression,
                    start_date=factor_start,
                    end_date=factor_end
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
        
        # Update thesis status to BACKTESTED
        self._thesis_repo.update_status(thesis_id, "BACKTESTED")
        
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
