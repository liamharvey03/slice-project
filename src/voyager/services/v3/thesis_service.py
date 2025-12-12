"""
Thesis Service for V3.

Orchestrates the full thesis lifecycle:
- Create draft
- Update fields
- Manage status transitions
- Snapshots
- Activation
"""
from datetime import datetime, UTC
from typing import Optional, List
import uuid

from voyager.models.thesis import Thesis, ThesisSnapshot, RiskRails, ThesisExpressionLeg
from voyager.models.common import ThesisStatus, Direction
from voyager.models.v3 import ThesisDraftInput
from voyager.repositories.thesis_repo import ThesisRepository
from voyager.repositories.thesis_snapshot_repository import ThesisSnapshotRepository


# Valid status transitions
VALID_TRANSITIONS = {
    "WATCHLIST": ["VALIDATED", "CLOSED"],
    "VALIDATED": ["CRITIQUED", "WATCHLIST", "CLOSED"],
    "CRITIQUED": ["BACKTESTED", "VALIDATED", "CLOSED"],
    "BACKTESTED": ["ACTIVE", "CRITIQUED", "CLOSED"],
    "ACTIVE": ["CLOSED"],
    "CLOSED": []
}


class ThesisService:
    """
    Manages thesis lifecycle for V3.

    Status flow:
        WATCHLIST -> VALIDATED -> CRITIQUED -> BACKTESTED -> ACTIVE -> CLOSED

    Each transition has validation rules and may create snapshots.

    Usage:
        # Create
        thesis = service.create_draft(draft_input)

        # Update during editing
        thesis = service.update(thesis_id, {"hypothesis": "..."})

        # Transition status (done by other services)
        thesis = service.transition_status(thesis_id, "VALIDATED")

        # Activate
        thesis = service.activate(thesis_id, final_size=0.10, rails=...)
    """

    def __init__(
        self,
        thesis_repo: ThesisRepository,
        snapshot_repo: ThesisSnapshotRepository
    ):
        self._thesis_repo = thesis_repo
        self._snapshot_repo = snapshot_repo

    # -------------------------------------------
    # CRUD Operations
    # -------------------------------------------

    def create_draft(self, draft_input: ThesisDraftInput) -> Thesis:
        """
        Create a new thesis in WATCHLIST status.
        """
        thesis_id = f"thesis_{uuid.uuid4().hex[:12]}"

        # Convert expression to proper format
        expression = []
        for leg in draft_input.expression:
            direction_str = leg.get("direction", "LONG")
            # Handle both string and enum
            if isinstance(direction_str, str):
                direction = Direction(direction_str)
            else:
                direction = direction_str
            expression.append(
                ThesisExpressionLeg(
                    asset=leg.get("asset"),
                    direction=direction,
                    size_pct=leg.get("size_pct", 0)
                )
            )

        thesis = Thesis(
            id=thesis_id,
            title=draft_input.title,
            hypothesis=draft_input.hypothesis,
            drivers=draft_input.drivers,
            disconfirmers=draft_input.disconfirmers,
            expression=expression,
            start_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            review_date=None,
            status=ThesisStatus.WATCHLIST,
            tags=[],
            monitor_indices=[],
            notes=None,
            risk_rails=None,
            final_size=None
        )

        # Persist
        self._thesis_repo.insert(thesis)

        return thesis

    def get(self, thesis_id: str) -> Optional[Thesis]:
        """Get thesis by ID"""
        return self._thesis_repo.get_by_id(thesis_id)

    def update(self, thesis_id: str, updates: dict) -> Thesis:
        """
        Update thesis fields.

        Only allowed in WATCHLIST, VALIDATED, or CRITIQUED status.
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")

        # Check status allows editing
        editable_statuses = [ThesisStatus.WATCHLIST, ThesisStatus.VALIDATED, ThesisStatus.CRITIQUED]
        if thesis.status not in editable_statuses:
            raise ValueError(f"Cannot edit thesis in {thesis.status.value} status")

        # Apply updates via existing repository methods
        if "hypothesis" in updates:
            self._thesis_repo.update_hypothesis(thesis_id, updates["hypothesis"])
        if "drivers" in updates:
            self._thesis_repo.update_list_field(thesis_id, "drivers", updates["drivers"], "replace")
        if "disconfirmers" in updates:
            self._thesis_repo.update_list_field(thesis_id, "disconfirmers", updates["disconfirmers"], "replace")
        if "expression" in updates:
            self._thesis_repo.update_expression(thesis_id, updates["expression"])
        if "notes" in updates:
            # Notes update requires full thesis update
            thesis.notes = updates["notes"]
            self._thesis_repo.update(thesis)
        if "tags" in updates:
            # Tags update requires full thesis update
            thesis.tags = updates["tags"]
            self._thesis_repo.update(thesis)

        return self._thesis_repo.get_by_id(thesis_id)

    def list_by_status(self, status: str) -> List[Thesis]:
        """List all theses with a given status"""
        return self._thesis_repo.list_by_status(status)

    def list_active(self) -> List[Thesis]:
        """List all active theses"""
        return self._thesis_repo.list_by_status("ACTIVE")

    # -------------------------------------------
    # Status Transitions
    # -------------------------------------------

    def transition_status(self, thesis_id: str, new_status: str) -> Thesis:
        """
        Transition thesis to new status.

        Validates that transition is allowed.
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")

        current_status = thesis.status.value if hasattr(thesis.status, 'value') else str(thesis.status)

        # Check valid transition
        allowed = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {current_status} to {new_status}. "
                f"Allowed: {allowed}"
            )

        return self._thesis_repo.update_status(thesis_id, new_status)

    # -------------------------------------------
    # Activation
    # -------------------------------------------

    def activate(
        self,
        thesis_id: str,
        final_size: float,
        rails: RiskRails
    ) -> Thesis:
        """
        Activate a thesis.

        Requirements:
        - Thesis must be in BACKTESTED status
        - final_size must be positive and <= position_cap
        - Creates activation snapshot

        Args:
            thesis_id: Thesis to activate
            final_size: Final position size (after PM adjustment)
            rails: Risk rails for monitoring
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")

        # Validate status
        current_status = thesis.status.value if hasattr(thesis.status, 'value') else str(thesis.status)
        if current_status != "BACKTESTED":
            raise ValueError(f"Cannot activate thesis in {current_status} status. Must be BACKTESTED.")

        # Validate size
        if final_size <= 0:
            raise ValueError("Final size must be positive")
        if final_size > rails.position_cap:
            raise ValueError(f"Final size {final_size} exceeds position cap {rails.position_cap}")

        # Create activation snapshot
        self._create_snapshot(thesis, "activation")

        # Update thesis
        self._thesis_repo.update_risk_rails(thesis_id, rails.model_dump() if hasattr(rails, 'model_dump') else rails.dict())
        self._thesis_repo.update_final_size(thesis_id, final_size)
        self._thesis_repo.update_status(thesis_id, "ACTIVE")

        return self._thesis_repo.get_by_id(thesis_id)

    # -------------------------------------------
    # Snapshots
    # -------------------------------------------

    def _create_snapshot(self, thesis: Thesis, snapshot_type: str) -> ThesisSnapshot:
        """Create a snapshot of current thesis state."""
        # Convert thesis to dict for snapshot content
        if hasattr(thesis, 'model_dump'):
            content = thesis.model_dump()
        elif hasattr(thesis, 'dict'):
            content = thesis.dict()
        else:
            # Build content dict manually
            expression_list = []
            for leg in thesis.expression:
                if hasattr(leg, 'model_dump'):
                    expression_list.append(leg.model_dump())
                elif hasattr(leg, 'dict'):
                    expression_list.append(leg.dict())
                else:
                    expression_list.append(leg)

            risk_rails_dict = None
            if thesis.risk_rails:
                if hasattr(thesis.risk_rails, 'model_dump'):
                    risk_rails_dict = thesis.risk_rails.model_dump()
                elif hasattr(thesis.risk_rails, 'dict'):
                    risk_rails_dict = thesis.risk_rails.dict()
                else:
                    risk_rails_dict = thesis.risk_rails

            status_str = (
                thesis.status.value
                if hasattr(thesis.status, 'value')
                else str(thesis.status)
            )

            content = {
                "id": thesis.id,
                "title": thesis.title,
                "hypothesis": thesis.hypothesis,
                "drivers": thesis.drivers,
                "disconfirmers": thesis.disconfirmers,
                "expression": expression_list,
                "status": status_str,
                "risk_rails": risk_rails_dict,
                "final_size": thesis.final_size
            }

        snapshot = ThesisSnapshot(
            id=f"snap_{uuid.uuid4().hex[:12]}",
            thesis_id=thesis.id,
            snapshot_type=snapshot_type,
            content=content,
            created_at=datetime.now(UTC).isoformat()
        )

        return self._snapshot_repo.insert(snapshot)

    def get_snapshots(self, thesis_id: str) -> List[ThesisSnapshot]:
        """Get all snapshots for a thesis"""
        return self._snapshot_repo.list_by_thesis(thesis_id)

    def get_snapshot(self, thesis_id: str, snapshot_type: str) -> Optional[ThesisSnapshot]:
        """Get most recent snapshot of a specific type"""
        return self._snapshot_repo.get_latest_by_type(thesis_id, snapshot_type)
