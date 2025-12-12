"""
E4: Session result DTOs for end-to-end session workflows.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from voyager.models.evaluation import ThesisEvaluationResult
from voyager.models.llm_outputs import ThesisReview, CrossThesisReport, DailySummary
from voyager.models.llm_inputs import Alert
from voyager.models.portfolio import PortfolioSnapshot, PortfolioDepthSnapshot


class ThesisEvaluationSessionResult(BaseModel):
    """
    Result from a complete thesis evaluation session (E2 + E3).
    """
    thesis_id: str
    evaluation: ThesisEvaluationResult
    review: ThesisReview
    trade_plan: Optional[dict] = None  # Optional E5 hook, not required for E4
    evaluated_at: datetime


class DailyUpdateSessionResult(BaseModel):
    """
    Result from a daily update session.
    """
    date: date
    portfolio_snapshot: PortfolioSnapshot
    portfolio_depth: PortfolioDepthSnapshot  # Include depth for risk context
    alerts: list[Alert]
    summary: DailySummary


class CrossThesisSessionResult(BaseModel):
    """
    Result from a cross-thesis analysis session.
    """
    thesis_ids: list[str]
    report: CrossThesisReport

