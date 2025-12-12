import json
from datetime import datetime
from typing import Optional, Tuple, Any, Mapping
from sqlalchemy import text

from voyager.db import get_engine
from voyager.models.evaluation import ThesisEvaluationResult
from voyager.models.llm_outputs import ThesisReview


class EvaluationRepository:
    """
    Repository for persisting thesis evaluation results and reviews.
    
    Stores one row per thesis (latest evaluation only, overwrites on upsert).
    """

    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def upsert_thesis_evaluation(
        self,
        thesis_id: str,
        evaluation: ThesisEvaluationResult,
        review: ThesisReview,
        evaluated_at: datetime,
    ) -> None:
        """
        Insert or update the latest evaluation for a thesis.
        
        Args:
            thesis_id: Thesis identifier
            evaluation: E2 evaluation result
            review: E3 LLM review
            evaluated_at: Timestamp of evaluation
        """
        engine = self.engine
        
        # Serialize to JSONB
        evaluation_json = json.dumps(evaluation.dict(), default=str)
        review_json = json.dumps(review.dict(), default=str)
        
        sql = text("""
            INSERT INTO thesis_evaluation (
                thesis_id, evaluation, review, evaluated_at
            )
            VALUES (
                :thesis_id, :evaluation, :review, :evaluated_at
            )
            ON CONFLICT (thesis_id) DO UPDATE SET
                evaluation = EXCLUDED.evaluation,
                review = EXCLUDED.review,
                evaluated_at = EXCLUDED.evaluated_at
        """)
        
        params = {
            "thesis_id": thesis_id,
            "evaluation": evaluation_json,
            "review": review_json,
            "evaluated_at": evaluated_at,
        }
        
        with engine.begin() as conn:
            conn.execute(sql, params)

    def get_latest_evaluation(
        self, thesis_id: str
    ) -> Optional[Tuple[ThesisEvaluationResult, ThesisReview]]:
        """
        Retrieve the latest evaluation and review for a thesis.
        
        Returns:
            Tuple of (evaluation, review) if found, None otherwise
        """
        engine = self.engine
        
        sql = text("""
            SELECT evaluation, review
            FROM thesis_evaluation
            WHERE thesis_id = :thesis_id
        """)
        
        with engine.connect() as conn:
            row = conn.execute(sql, {"thesis_id": thesis_id}).mappings().fetchone()
        
        if row is None:
            return None
        
        # Deserialize JSONB - psycopg may return dict directly or string
        raw_eval = row["evaluation"]
        raw_review = row["review"]
        
        if isinstance(raw_eval, str):
            evaluation_dict = json.loads(raw_eval)
        else:
            evaluation_dict = raw_eval  # already a dict from psycopg
        
        if isinstance(raw_review, str):
            review_dict = json.loads(raw_review)
        else:
            review_dict = raw_review  # already a dict from psycopg
        
        evaluation = ThesisEvaluationResult(**evaluation_dict)
        review = ThesisReview(**review_dict)
        
        return (evaluation, review)

