"""
E3: LLM input context DTOs for tool arguments.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from slice.models.observation import Observation
from slice.models.portfolio import PortfolioSnapshot
from slice.models.thesis import Thesis


class Alert(BaseModel):
    """
    Alert/notification for daily context.

    Fields:
        thesis_id: str - Associated thesis ID
        thesis_title: str - Thesis title (to avoid extra DB lookups)
        message: str - Human-readable alert text for UI/LLM
        observation_id: Optional[str] - Related observation ID if applicable
        timestamp: datetime - When the alert was generated
    """

    thesis_id: str
    thesis_title: str
    message: str
    observation_id: Optional[str] = None
    timestamp: datetime


class DailyContext(BaseModel):
    """
    Daily context snapshot for LLM daily summary tool.

    Fields:
        date: date - The date this context represents
        portfolio_snapshot: PortfolioSnapshot - Current portfolio state
        alerts: list[Alert] - Daily alerts/notifications
        observations: list[Observation] - Top observations for the day
        active_theses: list[Thesis] - Active theses with IDs
    """

    date: date
    portfolio_snapshot: PortfolioSnapshot
    alerts: list[Alert]
    observations: list[Observation]
    active_theses: list[Thesis]

