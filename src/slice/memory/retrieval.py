import json
from typing import Any, Dict, List, Tuple, Optional

from sqlalchemy import text

from slice.db import get_engine
from slice.embeddings import embed_observation_text
from slice.models.observation import Observation


def _format_vector(v: List[float]) -> str:
    """
    Convert a list[float] to a pgvector literal: "[0.1,0.2,...]".
    """
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"


def search_similar_observations(
    query_text: str,
    k: int = 5,
    since: Optional[str] = None,        # ISO date string; optional
    until: Optional[str] = None,        # ISO date string; optional
    categories: Optional[List[str]] = None,
    sentiment: Optional[str] = None,    # "bullish" | "bearish" | "neutral"
) -> List[Tuple[Observation, float]]:
    """
    Semantic K-NN over observations using pgvector.

    Optional filters:
      - since / until: ISO timestamps
      - categories: list of category strings (jsonb containment)
      - sentiment: 'bullish' | 'bearish' | 'neutral' (case-insensitive)

    Returns a list of (Observation, distance) sorted by increasing distance.
    """
    engine = get_engine()

    # 1) Embed the query
    embedding = embed_observation_text(query_text)
    embedding_str = _format_vector(embedding)

    # 2) Build WHERE clauses and params
    where_clauses = ["embedding IS NOT NULL"]
    params: Dict[str, Any] = {"embedding": embedding_str, "k": k}

    if since:
        where_clauses.append("timestamp >= :since")
        params["since"] = since

    if until:
        where_clauses.append("timestamp <= :until")
        params["until"] = until

    if sentiment:
        # DB stores sentiment as upper-case enum-like text (BEARISH / BULLISH / NEUTRAL)
        where_clauses.append("sentiment = :sentiment")
        params["sentiment"] = sentiment.upper()

    if categories:
        # categories is jsonb → use containment operator
        # e.g. categories @> '["fed","inflation"]'
        where_clauses.append("categories @> :cats")
        params["cats"] = json.dumps(categories)

    where_sql = " AND ".join(where_clauses)

    sql = text(f"""
        SELECT
            id,
            timestamp,
            text,
            thesis_ref,
            categories,
            sentiment,
            actionable,
            embedding <-> CAST(:embedding AS vector) AS distance
        FROM observation
        WHERE {where_sql}
        ORDER BY embedding <-> CAST(:embedding AS vector)
        LIMIT :k;
    """)

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    results: List[Tuple[Observation, float]] = []

    for row in rows:
        r: Dict[str, Any] = dict(row)
        dist = float(r.pop("distance"))

        # categories is jsonb → Python object (str or already decoded)
        if isinstance(r.get("categories"), str):
            try:
                r["categories"] = json.loads(r["categories"])
            except Exception:
                # if decode fails, leave raw
                pass

        obs = Observation(**r)
        results.append((obs, dist))

    return results