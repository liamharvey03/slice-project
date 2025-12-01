"""
E4: Tests for EvaluationRepository.
"""
import pytest
from datetime import datetime, timezone

from slice.repositories.evaluation_repo import EvaluationRepository
from slice.models.evaluation import ThesisEvaluationResult, EquityPoint, ScenarioImpact
from slice.models.llm_outputs import ThesisReview


def test_upsert_thesis_evaluation(evaluation_repo, sample_evaluation, sample_review):
    """Test inserting a new evaluation."""
    thesis_id = "T1"
    evaluated_at = datetime.now(timezone.utc)
    
    evaluation_repo.upsert_thesis_evaluation(
        thesis_id=thesis_id,
        evaluation=sample_evaluation,
        review=sample_review,
        evaluated_at=evaluated_at,
    )
    
    # Verify it can be retrieved
    result = evaluation_repo.get_latest_evaluation(thesis_id)
    assert result is not None
    eval_result, review_result = result
    
    assert eval_result.performance["total_return"] == 10.0
    assert review_result.critique == "Plausible but over-concentrated."


def test_upsert_overwrites_existing(evaluation_repo, sample_evaluation, sample_review):
    """Test that upsert overwrites existing evaluation."""
    thesis_id = "T1"
    evaluated_at1 = datetime.now(timezone.utc)
    
    # Insert first evaluation
    evaluation_repo.upsert_thesis_evaluation(
        thesis_id=thesis_id,
        evaluation=sample_evaluation,
        review=sample_review,
        evaluated_at=evaluated_at1,
    )
    
    # Create updated evaluation
    updated_eval = ThesisEvaluationResult(
        performance={"total_return": 20.0, "cagr": 10.0, "volatility": 20.0, "sharpe": 1.0, "max_drawdown": 10.0},
        timeseries=[EquityPoint(date=datetime.now(timezone.utc), value=1.2)],
        risk_metrics={"max_weight_pct": 100.0, "VaR_95": 3.0, "max_drawdown_pct": 10.0},
        scenarios=[],
    )
    updated_review = ThesisReview(
        critique="Updated critique",
        questions=[],
        risk_flags=[],
        insufficient_context=False,
    )
    evaluated_at2 = datetime.now(timezone.utc)
    
    # Upsert should overwrite
    evaluation_repo.upsert_thesis_evaluation(
        thesis_id=thesis_id,
        evaluation=updated_eval,
        review=updated_review,
        evaluated_at=evaluated_at2,
    )
    
    # Verify latest is the updated one
    result = evaluation_repo.get_latest_evaluation(thesis_id)
    assert result is not None
    eval_result, review_result = result
    
    assert eval_result.performance["total_return"] == 20.0
    assert review_result.critique == "Updated critique"


def test_get_latest_evaluation_not_found(evaluation_repo):
    """Test that get_latest returns None for non-existent thesis."""
    result = evaluation_repo.get_latest_evaluation("NONEXISTENT")
    assert result is None

