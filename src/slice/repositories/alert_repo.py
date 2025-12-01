import uuid
from datetime import date, datetime
from typing import List, Any, Mapping
from sqlalchemy import text

from slice.db import get_engine
from slice.models.llm_inputs import Alert


class AlertRepository:
    """
    Repository for persisting alerts/notifications.
    """

    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def insert_many(self, alerts: List[Alert]) -> None:
        """
        Insert multiple alerts in a single transaction.
        
        Args:
            alerts: List of Alert objects to persist
        """
        if not alerts:
            return
        
        engine = self.engine
        
        sql = text("""
            INSERT INTO alert (
                id, thesis_id, thesis_title, message, observation_id,
                timestamp, date
            )
            VALUES (
                :id, :thesis_id, :thesis_title, :message, :observation_id,
                :timestamp, :date
            )
        """)
        
        params_list = []
        for alert in alerts:
            # Generate ID if not present
            alert_id = getattr(alert, "id", None) or str(uuid.uuid4())
            
            # Extract date from timestamp if date not explicitly set
            alert_date = getattr(alert, "date", None)
            if alert_date is None:
                alert_date = alert.timestamp.date() if isinstance(alert.timestamp, datetime) else date.today()
            
            params_list.append({
                "id": alert_id,
                "thesis_id": alert.thesis_id,
                "thesis_title": alert.thesis_title,
                "message": alert.message,
                "observation_id": alert.observation_id,
                "timestamp": alert.timestamp,
                "date": alert_date,
            })
        
        with engine.begin() as conn:
            conn.execute(sql, params_list)

    def list_for_date(self, target_date: date) -> List[Alert]:
        """
        Retrieve all alerts for a specific date.
        
        Args:
            target_date: Date to query alerts for
            
        Returns:
            List of Alert objects
        """
        engine = self.engine
        
        sql = text("""
            SELECT id, thesis_id, thesis_title, message, observation_id,
                   timestamp, date
            FROM alert
            WHERE date = :target_date
            ORDER BY timestamp DESC
        """)
        
        with engine.connect() as conn:
            rows = conn.execute(sql, {"target_date": target_date}).mappings().fetchall()
        
        alerts = []
        for row in rows:
            # Convert row to Alert
            alert_dict = dict(row)
            # Remove 'date' field if Alert model doesn't expect it
            if "date" in alert_dict:
                del alert_dict["date"]
            alerts.append(Alert(**alert_dict))
        
        return alerts

