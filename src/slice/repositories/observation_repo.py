import json
from typing import List, Optional

from sqlalchemy import text

from slice.db import get_engine
from slice.models.observation import Observation


class ObservationRepository:
    @staticmethod
    def insert(obs: Observation, embedding_vector: Optional[List[float]] = None) -> None:
        engine = get_engine()

        # --- Convert Pydantic model to params dict ---
        params = obs.dict()

        # categories field → JSONB
        # obs.categories arrives as either list[str] or comma-separated string
        if isinstance(params["categories"], str):
            # allow "fed, inflation" → ["fed", "inflation"]
            cats = [c.strip() for c in params["categories"].split(",") if c.strip()]
        else:
            cats = params["categories"]
        params["categories"] = json.dumps(cats)

        # embedding vector → string "[0.1,0.2,...]" cast to ::vector
        if embedding_vector is not None:
            params["embedding"] = "[" + ",".join(f"{x:.8f}" for x in embedding_vector) + "]"
        else:
            params["embedding"] = None

        # Build SQL — embedding::vector is key
        sql = text("""
            INSERT INTO observation (
                id,
                timestamp,
                text,
                thesis_ref,
                categories,
                sentiment,
                actionable,
                embedding
            )
            VALUES (
                :id,
                :timestamp,
                :text,
                :thesis_ref,
                :categories,
                :sentiment,
                :actionable,
                CAST(:embedding AS vector)
            )
            ON CONFLICT (id) DO UPDATE SET
                timestamp  = EXCLUDED.timestamp,
                text       = EXCLUDED.text,
                thesis_ref = EXCLUDED.thesis_ref,
                categories = EXCLUDED.categories,
                sentiment  = EXCLUDED.sentiment,
                actionable = EXCLUDED.actionable,
                embedding  = EXCLUDED.embedding;
        """)

        with engine.begin() as conn:
            conn.execute(sql, params)

    @staticmethod
    def get(obs_id: str) -> Optional[Observation]:
        engine = get_engine()
        sql = text("SELECT * FROM observation WHERE id = :oid")

        with engine.connect() as conn:
            row = conn.execute(sql, {"oid": obs_id}).mappings().fetchone()

        if row is None:
            return None

        row = dict(row)

        # categories JSONB → Python list
        if isinstance(row.get("categories"), str):
            try:
                row["categories"] = json.loads(row["categories"])
            except:
                pass

        # embedding we leave as-is (vector type or None)
        return Observation(**row)