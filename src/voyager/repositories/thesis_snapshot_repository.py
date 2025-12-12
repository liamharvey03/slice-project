"""
Repository for thesis snapshots.
"""
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
import json
from datetime import datetime, UTC
import uuid

from voyager.models.thesis import ThesisSnapshot


class ThesisSnapshotRepository:
    """CRUD operations for thesis snapshots"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
    
    def insert(self, snapshot: ThesisSnapshot) -> ThesisSnapshot:
        """Insert a new snapshot"""
        query = text("""
            INSERT INTO thesis_snapshot (id, thesis_id, snapshot_type, content, created_at)
            VALUES (:id, :thesis_id, :snapshot_type, :content, :created_at)
            RETURNING id, thesis_id, snapshot_type, content, created_at
        """)
        
        snapshot_id = snapshot.id or f"snap_{uuid.uuid4().hex[:12]}"
        created_at = snapshot.created_at or datetime.now(UTC).isoformat()
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {
                "id": snapshot_id,
                "thesis_id": snapshot.thesis_id,
                "snapshot_type": snapshot.snapshot_type,
                "content": json.dumps(snapshot.content),
                "created_at": created_at
            })
            conn.commit()
            row = result.fetchone()
        
        return self._row_to_model(row)
    
    def get_by_id(self, snapshot_id: str) -> Optional[ThesisSnapshot]:
        """Get snapshot by ID"""
        query = text("""
            SELECT id, thesis_id, snapshot_type, content, created_at
            FROM thesis_snapshot
            WHERE id = :id
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"id": snapshot_id})
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def list_by_thesis(self, thesis_id: str) -> List[ThesisSnapshot]:
        """List all snapshots for a thesis"""
        query = text("""
            SELECT id, thesis_id, snapshot_type, content, created_at
            FROM thesis_snapshot
            WHERE thesis_id = :thesis_id
            ORDER BY created_at ASC
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            rows = result.fetchall()
        
        return [self._row_to_model(row) for row in rows]
    
    def get_latest_by_type(self, thesis_id: str, snapshot_type: str) -> Optional[ThesisSnapshot]:
        """Get most recent snapshot of a specific type"""
        query = text("""
            SELECT id, thesis_id, snapshot_type, content, created_at
            FROM thesis_snapshot
            WHERE thesis_id = :thesis_id AND snapshot_type = :snapshot_type
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {
                "thesis_id": thesis_id,
                "snapshot_type": snapshot_type
            })
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def _row_to_model(self, row) -> ThesisSnapshot:
        """Convert DB row to model"""
        return ThesisSnapshot(
            id=str(row.id),
            thesis_id=str(row.thesis_id),
            snapshot_type=row.snapshot_type,
            content=row.content if isinstance(row.content, dict) else json.loads(row.content),
            created_at=row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at)
        )
