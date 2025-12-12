"""
Repository for logic validation results.
"""
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
import json
from datetime import datetime, UTC
import uuid

from voyager.models.thesis import LogicValidation, LogicLink


class LogicValidationRepository:
    """CRUD operations for logic validations"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
    
    def insert(self, validation: LogicValidation) -> LogicValidation:
        """Insert a new validation"""
        query = text("""
            INSERT INTO logic_validation (id, thesis_id, links, created_at)
            VALUES (:id, :thesis_id, :links, :created_at)
            RETURNING id, thesis_id, links, created_at
        """)
        
        validation_id = validation.id or f"val_{uuid.uuid4().hex[:12]}"
        created_at = validation.created_at or datetime.now(UTC).isoformat()
        
        # Serialize links
        links_json = [link.model_dump() for link in validation.links]
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {
                "id": validation_id,
                "thesis_id": validation.thesis_id,
                "links": json.dumps(links_json),
                "created_at": created_at
            })
            conn.commit()
            row = result.fetchone()
        
        return self._row_to_model(row)
    
    def get_by_thesis(self, thesis_id: str) -> Optional[LogicValidation]:
        """Get most recent validation for a thesis"""
        query = text("""
            SELECT id, thesis_id, links, created_at
            FROM logic_validation
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def list_by_thesis(self, thesis_id: str) -> List[LogicValidation]:
        """List all validations for a thesis"""
        query = text("""
            SELECT id, thesis_id, links, created_at
            FROM logic_validation
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            rows = result.fetchall()
        
        return [self._row_to_model(row) for row in rows]
    
    def _row_to_model(self, row) -> LogicValidation:
        """Convert DB row to model"""
        links_data = row.links if isinstance(row.links, list) else json.loads(row.links)
        links = [LogicLink(**link) for link in links_data]
        
        return LogicValidation(
            id=str(row.id),
            thesis_id=str(row.thesis_id),
            links=links,
            created_at=row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at)
        )
