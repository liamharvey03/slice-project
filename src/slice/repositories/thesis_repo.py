import json
from typing import Optional, List, Any, Mapping
from sqlalchemy import text

from slice.db import get_engine
from slice.models.thesis import Thesis


class ThesisRepository:
    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def insert(self, thesis: Thesis) -> Thesis:
        engine = self.engine

        # Base dict
        params = thesis.dict()

        # JSONB fields: convert lists → JSON strings
        json_fields = ["drivers", "disconfirmers", "tags", "monitor_indices"]
        for f in json_fields:
            params[f] = json.dumps(params[f])

        # Enums
        params["status"] = thesis.status.value

        # expression (list[ThesisExpressionLeg]) → JSON
        expr_payload = []
        for leg in thesis.expression:
            expr_payload.append(
                {
                    "asset": leg.asset,
                    "direction": leg.direction.value,
                    "size_pct": leg.size_pct,
                }
            )
        params["expression"] = json.dumps(expr_payload)

        sql = text("""
            INSERT INTO thesis (
                id, title, hypothesis, drivers, disconfirmers,
                expression, start_date, review_date, status,
                tags, monitor_indices, notes
            )
            VALUES (
                :id, :title, :hypothesis, :drivers, :disconfirmers,
                :expression, :start_date, :review_date, :status,
                :tags, :monitor_indices, :notes
            )
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                hypothesis = EXCLUDED.hypothesis,
                drivers = EXCLUDED.drivers,
                disconfirmers = EXCLUDED.disconfirmers,
                expression = EXCLUDED.expression,
                start_date = EXCLUDED.start_date,
                review_date = EXCLUDED.review_date,
                status = EXCLUDED.status,
                tags = EXCLUDED.tags,
                monitor_indices = EXCLUDED.monitor_indices,
                notes = EXCLUDED.notes;
        """)

        with engine.begin() as conn:
            conn.execute(sql, params)

        return thesis

    def _row_to_thesis(self, row: Mapping[str, Any]) -> Thesis:
        data = dict(row)

        json_fields = ["drivers", "disconfirmers", "tags", "monitor_indices", "expression"]
        for f in json_fields:
            if isinstance(data.get(f), str):
                try:
                    data[f] = json.loads(data[f])
                except Exception:
                    pass

        # Normalize date-like fields to strings for the Thesis model
        for date_field in ("start_date", "review_date"):
            value = data.get(date_field)
            if value is not None and not isinstance(value, str):
                # Handles datetime.date or datetime.datetime
                try:
                    data[date_field] = value.isoformat()
                except Exception:
                    # Last resort: cast to str
                    data[date_field] = str(value)

        return Thesis(**data)

    def get_by_id(self, thesis_id: str) -> Optional[Thesis]:
        engine = self.engine
        sql = text("SELECT * FROM thesis WHERE id = :tid")

        with engine.connect() as conn:
            row = conn.execute(sql, {"tid": thesis_id}).mappings().fetchone()

        if row is None:
            return None

        return self._row_to_thesis(row)

    def list_all(self) -> List[Thesis]:
        engine = self.engine
        sql = text("""
            SELECT * FROM thesis
            ORDER BY id ASC
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql).mappings().fetchall()

        return [self._row_to_thesis(r) for r in rows]

    def list_recent(self, limit: int) -> List[Thesis]:
        engine = self.engine
        sql = text("""
            SELECT * FROM thesis
            ORDER BY start_date DESC NULLS LAST, id DESC
            LIMIT :lim
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql, {"lim": limit}).mappings().fetchall()

        return [self._row_to_thesis(r) for r in rows]
