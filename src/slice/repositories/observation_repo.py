import json
from typing import List, Optional, Any, Mapping

from sqlalchemy import text

from slice.db import get_engine
from slice.models.observation import Observation
from slice.models.common import Sentiment


class ObservationRepository:
    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def insert(self, obs: Observation, embedding_vector: Optional[List[float]] = None) -> Observation:
        engine = self.engine

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

        return obs

    def _row_to_observation(self, row: Mapping[str, Any]) -> Observation:
        data = dict(row)

        for field in ("categories", "thesis_ref"):
            if isinstance(data.get(field), str):
                try:
                    data[field] = json.loads(data[field])
                except Exception:
                    pass

        if isinstance(data.get("sentiment"), str):
            try:
                data["sentiment"] = Sentiment(data["sentiment"])
            except Exception:
                pass

        return Observation(**data)

    def get_by_id(self, obs_id: str) -> Optional[Observation]:
        engine = self.engine
        sql = text("SELECT * FROM observation WHERE id = :oid")

        with engine.connect() as conn:
            row = conn.execute(sql, {"oid": obs_id}).mappings().fetchone()

        if row is None:
            return None

        return self._row_to_observation(row)

    def get(self, obs_id: str) -> Optional[Observation]:
        return self.get_by_id(obs_id)

    def list_for_thesis(self, thesis_id: str) -> List[Observation]:
        engine = self.engine
        sql = text("""
            SELECT * FROM observation
            WHERE thesis_ref @> :thesis_ref
            ORDER BY timestamp DESC
        """)

        thesis_ref = [thesis_id]

        with engine.connect() as conn:
            rows = conn.execute(sql, {"thesis_ref": thesis_ref}).mappings().fetchall()

        return [self._row_to_observation(r) for r in rows]

    def list_recent(self, limit: int) -> List[Observation]:
        engine = self.engine
        sql = text("""
            SELECT * FROM observation
            ORDER BY timestamp DESC
            LIMIT :lim
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql, {"lim": limit}).mappings().fetchall()

        return [self._row_to_observation(r) for r in rows]
