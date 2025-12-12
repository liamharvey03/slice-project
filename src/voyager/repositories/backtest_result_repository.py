"""
Repository for backtest results.
"""
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
import json
from datetime import datetime
import uuid

from voyager.models.v3 import BacktestResult, BacktestMetrics, EquityPoint, FactorExposureResult


class BacktestResultRepository:
    """CRUD operations for backtest results"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
    
    def insert(self, result: BacktestResult) -> BacktestResult:
        """Insert a new backtest result"""
        query = text("""
            INSERT INTO backtest_result 
            (id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at)
            VALUES (:id, :thesis_id, :expression, :period_start, :period_end, :metrics, :equity_curve, :factor_exposure, :iteration_count, :created_at)
            RETURNING id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at
        """)
        
        result_id = result.id or f"bt_{uuid.uuid4().hex[:12]}"
        created_at = result.created_at or datetime.utcnow().isoformat()
        
        with self._engine.connect() as conn:
            db_result = conn.execute(query, {
                "id": result_id,
                "thesis_id": result.thesis_id,
                "expression": json.dumps(result.expression),
                "period_start": result.period_start,
                "period_end": result.period_end,
                "metrics": json.dumps(result.metrics.dict()),
                "equity_curve": json.dumps([ep.dict() for ep in result.equity_curve]),
                "factor_exposure": json.dumps(result.factor_exposure.dict()) if result.factor_exposure else None,
                "iteration_count": result.iteration_count,
                "created_at": created_at
            })
            conn.commit()
            row = db_result.fetchone()
        
        return self._row_to_model(row)
    
    def get_latest_by_thesis(self, thesis_id: str) -> Optional[BacktestResult]:
        """Get most recent backtest for a thesis"""
        query = text("""
            SELECT id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at
            FROM backtest_result
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def count_by_thesis(self, thesis_id: str) -> int:
        """Count backtest iterations for a thesis"""
        query = text("""
            SELECT COUNT(*) FROM backtest_result WHERE thesis_id = :thesis_id
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            return result.scalar() or 0
    
    def list_by_thesis(self, thesis_id: str) -> List[BacktestResult]:
        """List all backtests for a thesis"""
        query = text("""
            SELECT id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at
            FROM backtest_result
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            rows = result.fetchall()
        
        return [self._row_to_model(row) for row in rows]
    
    def _row_to_model(self, row) -> BacktestResult:
        """Convert DB row to model"""
        metrics_data = row.metrics if isinstance(row.metrics, dict) else json.loads(row.metrics)
        equity_data = row.equity_curve if isinstance(row.equity_curve, list) else json.loads(row.equity_curve)
        factor_data = None
        if row.factor_exposure:
            factor_data = row.factor_exposure if isinstance(row.factor_exposure, dict) else json.loads(row.factor_exposure)
        
        return BacktestResult(
            id=str(row.id),
            thesis_id=str(row.thesis_id),
            expression=row.expression if isinstance(row.expression, dict) else json.loads(row.expression),
            period_start=str(row.period_start),
            period_end=str(row.period_end),
            metrics=BacktestMetrics(**metrics_data),
            equity_curve=[EquityPoint(**ep) for ep in equity_data],
            factor_exposure=FactorExposureResult(**factor_data) if factor_data else None,
            iteration_count=row.iteration_count,
            created_at=row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at)
        )
