"""
E3: LLM input context DTOs for tool arguments.
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel

from slice.models.observation import Observation
from slice.models.portfolio import PortfolioSnapshot
from slice.models.thesis import Thesis


class Alert(BaseModel):
    """
    Alert/notification for daily context.

    Fields:
        type: str - Alert type (e.g., "disconfirmer", "trigger")
        message: str - Alert message text
        thesis_id: Optional[str] - Associated thesis ID if applicable
    """

    type: str
    message: str
    thesis_id: Optional[str] = None


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

