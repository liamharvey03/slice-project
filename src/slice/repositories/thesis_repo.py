import json
from typing import Optional, List
from sqlalchemy import text

from slice.db import get_engine
from slice.models.thesis import Thesis


class ThesisRepository:
    @staticmethod
    def insert(thesis: Thesis) -> None:
        engine = get_engine()

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