"""
E4: Tests for DailySummaryRepository.
"""
import pytest
from datetime import date, timedelta

from voyager.repositories.daily_summary_repo import DailySummaryRepository
from voyager.models.llm_outputs import DailySummary


def test_upsert_summary(daily_summary_repo, sample_daily_summary):
    """Test inserting a new daily summary."""
    target_date = date.today()
    
    daily_summary_repo.upsert_summary(target_date, sample_daily_summary)
    
    # Verify it can be retrieved
    result = daily_summary_repo.get_summary(target_date)
    assert result is not None
    assert result.key_narratives == ["Market volatility increased"]
    assert result.thesis_references == ["T1"]


def test_upsert_overwrites_existing(daily_summary_repo, sample_daily_summary):
    """Test that upsert overwrites existing summary."""
    target_date = date.today()
    
    # Insert first summary
    daily_summary_repo.upsert_summary(target_date, sample_daily_summary)
    
    # Create updated summary
    updated_summary = DailySummary(
        key_narratives=["Updated narrative"],
        risk_highlights=["Updated risk"],
        thesis_references=["T2"],
        insufficient_context=True,
    )
    
    # Upsert should overwrite
    daily_summary_repo.upsert_summary(target_date, updated_summary)
    
    # Verify latest is the updated one
    result = daily_summary_repo.get_summary(target_date)
    assert result is not None
    assert result.key_narratives == ["Updated narrative"]
    assert result.thesis_references == ["T2"]
    assert result.insufficient_context is True


def test_get_summary_not_found(daily_summary_repo):
    """Test that get_summary returns None for non-existent date."""
    future_date = date.today() + timedelta(days=365)
    result = daily_summary_repo.get_summary(future_date)
    assert result is None

