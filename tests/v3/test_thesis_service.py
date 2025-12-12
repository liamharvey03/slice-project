"""
Tests for ThesisService.
"""
import pytest
from unittest.mock import MagicMock
from voyager.services.v3.thesis_service import ThesisService, VALID_TRANSITIONS
from voyager.models.thesis import Thesis, ThesisSnapshot, RiskRails, ThesisExpressionLeg
from voyager.models.common import ThesisStatus, Direction
from voyager.models.v3 import ThesisDraftInput


@pytest.fixture
def mock_thesis_repo():
    return MagicMock()


@pytest.fixture
def mock_snapshot_repo():
    return MagicMock()


@pytest.fixture
def thesis_service(mock_thesis_repo, mock_snapshot_repo):
    return ThesisService(mock_thesis_repo, mock_snapshot_repo)


@pytest.fixture
def sample_thesis():
    return Thesis(
        id="test_thesis",
        title="Test Thesis",
        hypothesis="Test hypothesis",
        drivers=["driver1"],
        disconfirmers=["disconfirmer1"],
        expression=[ThesisExpressionLeg(asset="GLD", direction=Direction.LONG, size_pct=100.0)],
        start_date="2024-01-01",
        review_date=None,
        status=ThesisStatus.WATCHLIST,
        tags=[],
        monitor_indices=[],
        notes=None,
        risk_rails=None,
        final_size=None
    )


@pytest.fixture
def sample_draft_input():
    return ThesisDraftInput(
        title="New Thesis",
        hypothesis="New hypothesis",
        drivers=["driver1", "driver2"],
        disconfirmers=["disconfirmer1"],
        expression=[{"asset": "GLD", "direction": "LONG", "size_pct": 100.0}]
    )


class TestThesisServiceCRUD:

    def test_create_draft(self, thesis_service, mock_thesis_repo, sample_draft_input):
        """Test creating a draft thesis"""
        mock_thesis_repo.insert.return_value = MagicMock()

        thesis = thesis_service.create_draft(sample_draft_input)

        assert thesis is not None
        mock_thesis_repo.insert.assert_called_once()
        inserted_thesis = mock_thesis_repo.insert.call_args[0][0]
        assert inserted_thesis.status == ThesisStatus.WATCHLIST
        assert inserted_thesis.title == "New Thesis"

    def test_get_thesis(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test retrieving thesis by ID"""
        mock_thesis_repo.get_by_id.return_value = sample_thesis

        result = thesis_service.get("test_thesis")

        assert result == sample_thesis
        mock_thesis_repo.get_by_id.assert_called_once_with("test_thesis")

    def test_get_thesis_not_found(self, thesis_service, mock_thesis_repo):
        """Test retrieving non-existent thesis"""
        mock_thesis_repo.get_by_id.return_value = None

        result = thesis_service.get("nonexistent")

        assert result is None

    def test_update_in_draft(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test updating thesis in editable status"""
        mock_thesis_repo.get_by_id.return_value = sample_thesis
        updated_thesis = Thesis(**{**sample_thesis.model_dump(), "hypothesis": "Updated"})
        mock_thesis_repo.get_by_id.side_effect = [sample_thesis, updated_thesis]

        result = thesis_service.update("test_thesis", {"hypothesis": "Updated"})

        assert result.hypothesis == "Updated"
        mock_thesis_repo.update_hypothesis.assert_called_once_with("test_thesis", "Updated")

    def test_update_in_active_raises(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test that updating active thesis raises ValueError"""
        active_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.ACTIVE})
        mock_thesis_repo.get_by_id.return_value = active_thesis

        with pytest.raises(ValueError, match="Cannot edit thesis in ACTIVE status"):
            thesis_service.update("test_thesis", {"hypothesis": "Updated"})

    def test_update_thesis_not_found(self, thesis_service, mock_thesis_repo):
        """Test updating non-existent thesis raises ValueError"""
        mock_thesis_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Thesis not found"):
            thesis_service.update("nonexistent", {"hypothesis": "Updated"})

    def test_list_by_status(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test listing theses by status"""
        mock_thesis_repo.list_by_status.return_value = [sample_thesis]

        result = thesis_service.list_by_status("WATCHLIST")

        assert len(result) == 1
        assert result[0] == sample_thesis
        mock_thesis_repo.list_by_status.assert_called_once_with("WATCHLIST")

    def test_list_active(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test listing active theses"""
        active_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.ACTIVE})
        mock_thesis_repo.list_by_status.return_value = [active_thesis]

        result = thesis_service.list_active()

        assert len(result) == 1
        mock_thesis_repo.list_by_status.assert_called_once_with("ACTIVE")


class TestThesisServiceStatusTransitions:

    def test_valid_status_transition(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test valid status transition"""
        validated_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.VALIDATED})
        mock_thesis_repo.get_by_id.return_value = sample_thesis
        mock_thesis_repo.update_status.return_value = validated_thesis

        result = thesis_service.transition_status("test_thesis", "VALIDATED")

        assert result.status == ThesisStatus.VALIDATED
        mock_thesis_repo.update_status.assert_called_once_with("test_thesis", "VALIDATED")

    def test_invalid_status_transition(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test invalid status transition raises ValueError"""
        mock_thesis_repo.get_by_id.return_value = sample_thesis

        with pytest.raises(ValueError, match="Cannot transition from WATCHLIST to ACTIVE"):
            thesis_service.transition_status("test_thesis", "ACTIVE")

    def test_transition_to_closed(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test transitioning to CLOSED from any state"""
        closed_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.CLOSED})
        mock_thesis_repo.get_by_id.return_value = sample_thesis
        mock_thesis_repo.update_status.return_value = closed_thesis

        result = thesis_service.transition_status("test_thesis", "CLOSED")

        assert result.status == ThesisStatus.CLOSED

    def test_transition_thesis_not_found(self, thesis_service, mock_thesis_repo):
        """Test transitioning non-existent thesis raises ValueError"""
        mock_thesis_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Thesis not found"):
            thesis_service.transition_status("nonexistent", "VALIDATED")


class TestThesisServiceActivation:

    def test_activate_requires_backtested(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test that activation requires BACKTESTED status"""
        mock_thesis_repo.get_by_id.return_value = sample_thesis  # WATCHLIST status
        rails = RiskRails(max_dd_tolerance=0.08, position_cap=0.10)

        with pytest.raises(ValueError, match="Cannot activate thesis in WATCHLIST status"):
            thesis_service.activate("test_thesis", final_size=0.10, rails=rails)

    def test_activate_creates_snapshot(self, thesis_service, mock_thesis_repo, mock_snapshot_repo, sample_thesis):
        """Test that activation creates snapshot"""
        backtested_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.BACKTESTED})
        active_thesis = Thesis(**{**backtested_thesis.model_dump(), "status": ThesisStatus.ACTIVE})
        mock_thesis_repo.get_by_id.side_effect = [backtested_thesis, active_thesis]
        mock_thesis_repo.update_status.return_value = active_thesis
        mock_snapshot_repo.insert.return_value = MagicMock()

        rails = RiskRails(max_dd_tolerance=0.08, position_cap=0.10)
        thesis_service.activate("test_thesis", final_size=0.10, rails=rails)

        mock_snapshot_repo.insert.assert_called_once()
        snapshot = mock_snapshot_repo.insert.call_args[0][0]
        assert snapshot.snapshot_type == "activation"

    def test_activate_size_validation(self, thesis_service, mock_thesis_repo, sample_thesis):
        """Test size validation during activation"""
        backtested_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.BACKTESTED})
        mock_thesis_repo.get_by_id.return_value = backtested_thesis
        rails = RiskRails(max_dd_tolerance=0.08, position_cap=0.10)

        # Negative size
        with pytest.raises(ValueError, match="Final size must be positive"):
            thesis_service.activate("test_thesis", final_size=-0.05, rails=rails)

        # Size exceeds cap
        with pytest.raises(ValueError, match="exceeds position cap"):
            thesis_service.activate("test_thesis", final_size=0.15, rails=rails)

    def test_activate_success(self, thesis_service, mock_thesis_repo, mock_snapshot_repo, sample_thesis):
        """Test successful activation"""
        backtested_thesis = Thesis(**{**sample_thesis.model_dump(), "status": ThesisStatus.BACKTESTED})
        active_thesis = Thesis(**{
            **backtested_thesis.model_dump(),
            "status": ThesisStatus.ACTIVE,
            "risk_rails": RiskRails(max_dd_tolerance=0.08, position_cap=0.10),
            "final_size": 0.10
        })
        mock_thesis_repo.get_by_id.side_effect = [backtested_thesis, active_thesis]
        mock_thesis_repo.update_status.return_value = active_thesis
        mock_snapshot_repo.insert.return_value = MagicMock()

        rails = RiskRails(max_dd_tolerance=0.08, position_cap=0.10)
        result = thesis_service.activate("test_thesis", final_size=0.10, rails=rails)

        assert result.status == ThesisStatus.ACTIVE
        mock_thesis_repo.update_risk_rails.assert_called_once()
        mock_thesis_repo.update_final_size.assert_called_once_with("test_thesis", 0.10)
        mock_thesis_repo.update_status.assert_called_once_with("test_thesis", "ACTIVE")


class TestThesisServiceSnapshots:

    def test_get_snapshots(self, thesis_service, mock_snapshot_repo):
        """Test retrieving all snapshots"""
        snapshots = [MagicMock(), MagicMock()]
        mock_snapshot_repo.list_by_thesis.return_value = snapshots

        result = thesis_service.get_snapshots("test_thesis")

        assert len(result) == 2
        mock_snapshot_repo.list_by_thesis.assert_called_once_with("test_thesis")

    def test_get_snapshot(self, thesis_service, mock_snapshot_repo):
        """Test retrieving snapshot by type"""
        snapshot = MagicMock()
        mock_snapshot_repo.get_latest_by_type.return_value = snapshot

        result = thesis_service.get_snapshot("test_thesis", "activation")

        assert result == snapshot
        mock_snapshot_repo.get_latest_by_type.assert_called_once_with("test_thesis", "activation")
