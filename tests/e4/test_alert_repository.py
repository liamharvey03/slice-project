"""
E4: Tests for AlertRepository.
"""
import pytest
from datetime import date, datetime, timedelta, timezone

from slice.repositories.alert_repo import AlertRepository
from slice.models.llm_inputs import Alert


def test_insert_many(alert_repo, sample_alert):
    """Test inserting multiple alerts."""
    alerts = [
        sample_alert,
        Alert(
            thesis_id="T2",
            thesis_title="Another Thesis",
            message="Another alert",
            observation_id=None,
            timestamp=datetime.now(timezone.utc),
        ),
    ]
    
    alert_repo.insert_many(alerts)
    
    # Verify alerts can be retrieved
    today = date.today()
    retrieved = alert_repo.list_for_date(today)
    
    assert len(retrieved) == 2
    assert retrieved[0].thesis_id in ["T1", "T2"]
    assert retrieved[1].thesis_id in ["T1", "T2"]


def test_list_for_date(alert_repo, sample_alert):
    """Test retrieving alerts for a specific date."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # Insert alerts for different dates
    alert_today = Alert(
        thesis_id="T1",
        thesis_title="Test",
        message="Today's alert",
        observation_id=None,
        timestamp=datetime.combine(today, datetime.min.time()),
    )
    
    alert_yesterday = Alert(
        thesis_id="T2",
        thesis_title="Test 2",
        message="Yesterday's alert",
        observation_id=None,
        timestamp=datetime.combine(yesterday, datetime.min.time()),
    )
    
    alert_repo.insert_many([alert_today, alert_yesterday])
    
    # Verify date filtering
    today_alerts = alert_repo.list_for_date(today)
    assert len(today_alerts) == 1
    assert today_alerts[0].message == "Today's alert"
    
    yesterday_alerts = alert_repo.list_for_date(yesterday)
    assert len(yesterday_alerts) == 1
    assert yesterday_alerts[0].message == "Yesterday's alert"


def test_insert_many_empty_list(alert_repo):
    """Test that inserting empty list does nothing."""
    alert_repo.insert_many([])
    # Should not raise


def test_list_for_date_no_alerts(alert_repo):
    """Test that listing for date with no alerts returns empty list."""
    future_date = date.today() + timedelta(days=365)
    alerts = alert_repo.list_for_date(future_date)
    assert alerts == []

