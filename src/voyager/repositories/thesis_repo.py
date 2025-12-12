"""Repository for thesis CRUD operations."""
import json
from typing import Optional, List, Any, Mapping
from sqlalchemy import text

from voyager.db import get_engine
from voyager.models.thesis import Thesis


class ThesisRepository:
    """Repository for managing thesis CRUD operations in the database."""
    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def insert(self, thesis: Thesis) -> Thesis:
        """Insert or update a thesis (upsert)."""
        engine = self.engine

        # Base dict
        params = thesis.model_dump()

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

        # risk_rails (RiskRails model) → JSON
        if params.get("risk_rails"):
            if hasattr(params["risk_rails"], 'model_dump'):
                params["risk_rails"] = json.dumps(params["risk_rails"].model_dump())
            elif hasattr(params["risk_rails"], 'dict'):
                params["risk_rails"] = json.dumps(params["risk_rails"].dict())
            elif isinstance(params["risk_rails"], dict):
                params["risk_rails"] = json.dumps(params["risk_rails"])
        else:
            params["risk_rails"] = None

        sql = text("""
            INSERT INTO thesis (
                id, title, hypothesis, drivers, disconfirmers,
                expression, start_date, review_date, status,
                tags, monitor_indices, notes, risk_rails, final_size
            )
            VALUES (
                :id, :title, :hypothesis, :drivers, :disconfirmers,
                :expression, :start_date, :review_date, :status,
                :tags, :monitor_indices, :notes, :risk_rails, :final_size
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
                notes = EXCLUDED.notes,
                risk_rails = EXCLUDED.risk_rails,
                final_size = EXCLUDED.final_size;
        """)

        with engine.begin() as conn:
            conn.execute(sql, params)

        return thesis

    def _row_to_thesis(self, row: Mapping[str, Any]) -> Thesis:
        data = dict(row)

        json_fields = ["drivers", "disconfirmers", "tags", "monitor_indices", "expression", "risk_rails"]
        for f in json_fields:
            if isinstance(data.get(f), str):
                try:
                    data[f] = json.loads(data[f])
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

        # Convert risk_rails dict to RiskRails model if present
        if data.get("risk_rails") and isinstance(data["risk_rails"], dict):
            from voyager.models.thesis import RiskRails
            try:
                data["risk_rails"] = RiskRails(**data["risk_rails"])
            except Exception:  # pylint: disable=broad-exception-caught
                # If parsing fails, leave as None
                data["risk_rails"] = None

        # Normalize date-like fields to strings for the Thesis model
        for date_field in ("start_date", "review_date"):
            value = data.get(date_field)
            if value is not None and not isinstance(value, str):
                # Handles datetime.date or datetime.datetime
                try:
                    data[date_field] = value.isoformat()
                except Exception:  # pylint: disable=broad-exception-caught
                    # Last resort: cast to str
                    data[date_field] = str(value)

        return Thesis(**data)

    def get_by_id(self, thesis_id: str) -> Optional[Thesis]:
        """Get a thesis by ID."""
        engine = self.engine
        sql = text("SELECT * FROM thesis WHERE id = :tid")

        with engine.connect() as conn:
            row = conn.execute(sql, {"tid": thesis_id}).mappings().fetchone()

        if row is None:
            return None

        return self._row_to_thesis(row)

    def list_all(self) -> List[Thesis]:
        """List all theses."""
        engine = self.engine
        sql = text("""
            SELECT * FROM thesis
            ORDER BY id ASC
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql).mappings().fetchall()

        return [self._row_to_thesis(r) for r in rows]

    def list_recent(self, limit: int) -> List[Thesis]:
        """List recent theses, ordered by start_date descending."""
        engine = self.engine
        sql = text("""
            SELECT * FROM thesis
            ORDER BY start_date DESC NULLS LAST, id DESC
            LIMIT :lim
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql, {"lim": limit}).mappings().fetchall()

        return [self._row_to_thesis(r) for r in rows]

    def list_active(self) -> List[Thesis]:
        """Return all theses with ACTIVE status."""
        engine = self.engine
        sql = text("""
            SELECT * FROM thesis
            WHERE status = 'ACTIVE'
            ORDER BY start_date DESC NULLS LAST, id DESC
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql).mappings().fetchall()

        return [self._row_to_thesis(r) for r in rows]

    def update(self, thesis: Thesis) -> Thesis:
        """
        Update an existing thesis.

        E5: Used primarily to update thesis status (e.g., mark as ACTIVE).
        For full updates, use insert() which does upsert.

        Args:
            thesis: Thesis with updated fields

        Returns:
            Updated thesis
        """
        engine = self.engine

        # Base dict
        params = thesis.model_dump()

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

        # risk_rails (RiskRails model) → JSON
        if params.get("risk_rails"):
            if hasattr(params["risk_rails"], 'model_dump'):
                params["risk_rails"] = json.dumps(params["risk_rails"].model_dump())
            elif hasattr(params["risk_rails"], 'dict'):
                params["risk_rails"] = json.dumps(params["risk_rails"].dict())
            elif isinstance(params["risk_rails"], dict):
                params["risk_rails"] = json.dumps(params["risk_rails"])
        else:
            params["risk_rails"] = None

        sql = text("""
            UPDATE thesis SET
                title = :title,
                hypothesis = :hypothesis,
                drivers = :drivers,
                disconfirmers = :disconfirmers,
                expression = :expression,
                start_date = :start_date,
                review_date = :review_date,
                status = :status,
                tags = :tags,
                monitor_indices = :monitor_indices,
                notes = :notes,
                risk_rails = :risk_rails,
                final_size = :final_size
            WHERE id = :id
        """)

        with engine.begin() as conn:
            conn.execute(sql, params)

        return thesis

    def update_status(self, thesis_id: str, status: str) -> Optional[Thesis]:
        """Update thesis status"""
        engine = self.engine
        query = text("""
            UPDATE thesis
            SET status = :status
            WHERE id = :thesis_id
            RETURNING *
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id, "status": status})
            conn.commit()
            row = result.mappings().fetchone()

        return self._row_to_thesis(row) if row else None

    def update_risk_rails(self, thesis_id: str, risk_rails: dict) -> Optional[Thesis]:
        """Update thesis risk rails"""
        engine = self.engine
        query = text("""
            UPDATE thesis
            SET risk_rails = :risk_rails
            WHERE id = :thesis_id
            RETURNING *
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {
                "thesis_id": thesis_id,
                "risk_rails": json.dumps(risk_rails)
            })
            conn.commit()
            row = result.mappings().fetchone()

        return self._row_to_thesis(row) if row else None

    def update_final_size(self, thesis_id: str, final_size: float) -> Optional[Thesis]:
        """Update thesis final size"""
        engine = self.engine
        query = text("""
            UPDATE thesis
            SET final_size = :final_size
            WHERE id = :thesis_id
            RETURNING *
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id, "final_size": final_size})
            conn.commit()
            row = result.mappings().fetchone()

        return self._row_to_thesis(row) if row else None

    def list_by_status(self, status: str) -> List[Thesis]:
        """List theses by status"""
        engine = self.engine
        query = text("""
            SELECT * FROM thesis WHERE status = :status ORDER BY start_date DESC
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"status": status})
            rows = result.mappings().fetchall()

        return [self._row_to_thesis(row) for row in rows]

    def update_hypothesis(self, thesis_id: str, hypothesis: str) -> Optional[Thesis]:
        """Update thesis hypothesis field."""
        engine = self.engine
        query = text("""
            UPDATE thesis
            SET hypothesis = :hypothesis
            WHERE id = :thesis_id
            RETURNING *
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id, "hypothesis": hypothesis})
            conn.commit()
            row = result.mappings().fetchone()

        return self._row_to_thesis(row) if row else None

    def update_list_field(
        self,
        thesis_id: str,
        field: str,  # "drivers" or "disconfirmers"
        value: list,
        action: str = "replace"  # "replace", "add", or "remove"
    ) -> Optional[Thesis]:
        """Update a list field (drivers/disconfirmers)."""
        if field not in ["drivers", "disconfirmers"]:
            raise ValueError(f"Cannot update field: {field}. Must be 'drivers' or 'disconfirmers'")

        engine = self.engine

        # Get current value
        current_thesis = self.get_by_id(thesis_id)
        if current_thesis is None:
            return None

        current = getattr(current_thesis, field, [])

        # Apply action
        if action == "replace":
            new_value = value if isinstance(value, list) else [value]
        elif action == "add":
            new_value = current + ([value] if not isinstance(value, list) else value)
        elif action == "remove":
            new_value = [x for x in current if x != value]
        else:
            new_value = value if isinstance(value, list) else [value]

        query = text(f"""
            UPDATE thesis
            SET {field} = :value
            WHERE id = :thesis_id
            RETURNING *
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {
                "thesis_id": thesis_id,
                "value": json.dumps(new_value)
            })
            conn.commit()
            row = result.mappings().fetchone()

        return self._row_to_thesis(row) if row else None

    def update_expression(self, thesis_id: str, expression: list) -> Optional[Thesis]:
        """Update thesis expression."""
        engine = self.engine

        # Convert expression legs to JSON format
        expr_payload = []
        for leg in expression:
            if hasattr(leg, 'asset'):
                # Pydantic model
                expr_payload.append({
                    "asset": leg.asset,
                    "direction": leg.direction.value if hasattr(leg.direction, 'value') else str(leg.direction),
                    "size_pct": leg.size_pct,
                })
            elif isinstance(leg, dict):
                # Already a dict
                expr_payload.append(leg)
            else:
                raise ValueError(f"Invalid expression leg format: {leg}")

        query = text("""
            UPDATE thesis
            SET expression = :expression
            WHERE id = :thesis_id
            RETURNING *
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {
                "thesis_id": thesis_id,
                "expression": json.dumps(expr_payload)
            })
            conn.commit()
            row = result.mappings().fetchone()

        return self._row_to_thesis(row) if row else None
