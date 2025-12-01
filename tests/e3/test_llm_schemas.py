"""
E3: Tests for LLM output/input DTO schema validation.

Verifies:
- Missing required fields raise ValidationError
- Empty lists are valid and accepted
- All fields required (no implicit None)
"""
import pytest
from pydantic import ValidationError

from slice.models.llm_outputs import (
    ThesisReview,
    CrossThesisReport,
    IntuitionAnswer,
    DailySummary,
)
from slice.models.llm_inputs import Alert, DailyContext
from slice.models.observation import Observation
from slice.models.portfolio import PortfolioSnapshot, PortfolioTotals, Position
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.common import Sentiment, ThesisStatus, Direction
from datetime import date, datetime


def test_thesis_review_all_fields_required():
    """ThesisReview requires all fields; missing fields raise ValidationError."""
    # Valid minimal case
    valid = ThesisReview(
        critique="Test critique",
        questions=[],
        risk_flags=[],
        insufficient_context=False,
    )
    assert valid.critique == "Test critique"
    assert valid.questions == []
    assert valid.risk_flags == []
    assert valid.insufficient_context is False

    # Missing critique
    with pytest.raises(ValidationError):
        ThesisReview(
            questions=[],
            risk_flags=[],
            insufficient_context=False,
        )

    # Missing questions
    with pytest.raises(ValidationError):
        ThesisReview(
            critique="test",
            risk_flags=[],
            insufficient_context=False,
        )

    # Missing risk_flags
    with pytest.raises(ValidationError):
        ThesisReview(
            critique="test",
            questions=[],
            insufficient_context=False,
        )

    # Missing insufficient_context
    with pytest.raises(ValidationError):
        ThesisReview(
            critique="test",
            questions=[],
            risk_flags=[],
        )


def test_thesis_review_empty_lists_valid():
    """Empty lists are valid values."""
    review = ThesisReview(
        critique="",
        questions=[],
        risk_flags=[],
        insufficient_context=True,
    )
    assert review.critique == ""
    assert review.questions == []
    assert review.risk_flags == []


def test_cross_thesis_report_all_fields_required():
    """CrossThesisReport requires all fields."""
    valid = CrossThesisReport(
        overlaps=[],
        contradictions=[],
        gaps=[],
        insufficient_context=False,
    )
    assert valid.overlaps == []

    with pytest.raises(ValidationError):
        CrossThesisReport(
            contradictions=[],
            gaps=[],
            insufficient_context=False,
        )


def test_intuition_answer_all_fields_required():
    """IntuitionAnswer requires all fields."""
    valid = IntuitionAnswer(
        answer="test answer",
        references=[],
        insufficient_context=False,
    )
    assert valid.answer == "test answer"
    assert valid.references == []

    with pytest.raises(ValidationError):
        IntuitionAnswer(
            references=[],
            insufficient_context=False,
        )


def test_intuition_answer_references_empty_list_valid():
    """Empty references list is valid."""
    answer = IntuitionAnswer(
        answer="answer",
        references=[],
        insufficient_context=True,
    )
    assert answer.references == []


def test_daily_summary_all_fields_required():
    """DailySummary requires all fields."""
    valid = DailySummary(
        key_narratives=[],
        risk_highlights=[],
        thesis_references=[],
        insufficient_context=False,
    )
    assert valid.key_narratives == []
    assert valid.thesis_references == []

    with pytest.raises(ValidationError):
        DailySummary(
            risk_highlights=[],
            thesis_references=[],
            insufficient_context=False,
        )


def test_daily_summary_empty_lists_valid():
    """Empty lists are valid for DailySummary."""
    summary = DailySummary(
        key_narratives=[],
        risk_highlights=[],
        thesis_references=[],
        insufficient_context=True,
    )
    assert summary.key_narratives == []
    assert summary.thesis_references == []


def test_alert_schema():
    """Alert schema validation."""
    alert = Alert(type="disconfirmer", message="test", thesis_id="T1")
    assert alert.type == "disconfirmer"
    assert alert.thesis_id == "T1"

    alert_no_thesis = Alert(type="trigger", message="test")
    assert alert_no_thesis.thesis_id is None


def test_daily_context_schema():
    """DailyContext schema validation."""
    portfolio = PortfolioSnapshot(
        positions=[],
        totals=PortfolioTotals(
            portfolio_value=1000.0,
            gross_exposure=0.0,
            net_exposure=0.0,
        ),
    )

    thesis = Thesis(
        id="T1",
        title="Test",
        hypothesis="test",
        drivers=["d1"],
        disconfirmers=["dc1"],
        expression=[
            ThesisExpressionLeg(
                asset="A",
                direction=Direction.LONG,
                size_pct=100.0,
            )
        ],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.ACTIVE,
        tags=[],
        monitor_indices=["SPX"],
    )

    obs = Observation(
        id="obs1",
        timestamp=datetime.now(),
        text="test observation",
        thesis_ref=[],
        sentiment=Sentiment.NEUTRAL,
        categories=[],
        actionable="NO",
    )

    context = DailyContext(
        date=date.today(),
        portfolio_snapshot=portfolio,
        alerts=[],
        observations=[obs],
        active_theses=[thesis],
    )

    assert context.date == date.today()
    assert len(context.observations) == 1
    assert len(context.active_theses) == 1

