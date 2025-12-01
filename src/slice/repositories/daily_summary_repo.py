import json
from datetime import date
from typing import Optional, Any, Mapping
from sqlalchemy import text

from slice.db import get_engine
from slice.models.llm_outputs import DailySummary


class DailySummaryRepository:
    """
    Repository for persisting daily summary LLM outputs.
    """

    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def upsert_summary(self, target_date: date, summary: DailySummary) -> None:
        """
        Insert or update the daily summary for a specific date.
        
        Args:
            target_date: Date for the summary
            summary: DailySummary DTO to persist
        """
        engine = self.engine
        
        # Serialize to JSONB
        summary_json = json.dumps(summary.dict(), default=str)
        
        sql = text("""
            INSERT INTO daily_summary (date, summary)
            VALUES (:date, :summary)
            ON CONFLICT (date) DO UPDATE SET
                summary = EXCLUDED.summary
        """)
        
        params = {
            "date": target_date,
            "summary": summary_json,
        }
        
        with engine.begin() as conn:
            conn.execute(sql, params)

    def get_summary(self, target_date: date) -> Optional[DailySummary]:
        """
        Retrieve the daily summary for a specific date.
        
        Args:
            target_date: Date to query
            
        Returns:
            DailySummary if found, None otherwise
        """
        engine = self.engine
        
        sql = text("""
            SELECT summary
            FROM daily_summary
            WHERE date = :date
        """)
        
        with engine.connect() as conn:
            row = conn.execute(sql, {"date": target_date}).mappings().fetchone()
        
        if row is None:
            return None
        
        # Deserialize JSONB - psycopg may return dict directly or string
        raw = row["summary"]
        if isinstance(raw, str):
            summary_dict = json.loads(raw)
        else:
            summary_dict = raw  # already a dict from psycopg
        
        return DailySummary(**summary_dict)

