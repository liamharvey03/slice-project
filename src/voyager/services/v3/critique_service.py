"""
Critique Service for V3 Screen 2.

Orchestrates the thesis critique flow:
1. Generate initial critique summary
2. Handle drill-down conversations
3. Track conversation history
4. Apply thesis edits
"""
from datetime import datetime, UTC
from typing import List
import uuid
import json
import logging

# Third-party
from sqlalchemy import text
from sqlalchemy.engine import Engine

# First-party
from voyager.llm.critique_engine import CritiqueEngine
from voyager.models.v3 import CritiqueSummary, CritiqueResponse
from voyager.models.thesis import Thesis, ThesisSnapshot
from voyager.repositories.thesis_repo import ThesisRepository
from voyager.repositories.thesis_snapshot_repository import ThesisSnapshotRepository
from voyager.repositories.logic_validation_repository import LogicValidationRepository
from voyager.repositories.backtest_result_repository import BacktestResultRepository

logger = logging.getLogger(__name__)


class CritiqueService:
    """
    Orchestrates thesis critique workflow.

    Usage:
        # Start critique
        summary = await service.start(thesis_id)

        # Drill down on a concern
        response = await service.continue_conversation(
            thesis_id,
            dimension="empirical_grounding",
            user_message="I think..."
        )

        # Complete critique
        thesis = await service.complete(thesis_id)
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        critique_engine: CritiqueEngine,
        thesis_repo: ThesisRepository,
        snapshot_repo: ThesisSnapshotRepository,
        validation_repo: LogicValidationRepository,
        backtest_repo: BacktestResultRepository,
        engine: Engine
    ):
        self._engine = critique_engine
        self._thesis_repo = thesis_repo
        self._snapshot_repo = snapshot_repo
        self._validation_repo = validation_repo
        self._backtest_repo = backtest_repo
        self._db_engine = engine

    async def start(self, thesis_id: str) -> CritiqueSummary:
        """
        Start critique session for a thesis.

        Creates pre-critique snapshot and generates initial critique summary.
        """
        # Load thesis
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")

        # Create pre-critique snapshot
        self._create_snapshot(thesis, "pre_critique")

        # Load validation and backtest if available
        validation = self._validation_repo.get_by_thesis(thesis_id)
        backtest = self._backtest_repo.get_latest_by_thesis(thesis_id)

        # Generate critique
        summary = await self._engine.critique(
            thesis=thesis,
            validation=validation,
            backtest=backtest
        )

        # Initialize conversation storage in database
        self._init_conversation(thesis_id)

        return summary

    async def continue_conversation(
        self,
        thesis_id: str,
        dimension: str,
        user_message: str
    ) -> CritiqueResponse:
        """
        Continue drill-down conversation on a specific dimension.
        """
        # Load thesis
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")

        # Load conversation history for this dimension
        history = self._load_conversation(thesis_id, dimension)

        # Load validation
        validation = self._validation_repo.get_by_thesis(thesis_id)

        # Get response
        response = await self._engine.drill_down(
            thesis=thesis,
            dimension=dimension,
            user_message=user_message,
            conversation_history=history,
            validation=validation
        )

        # Update history
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response.message})
        self._save_conversation(thesis_id, dimension, history)

        return response

    def apply_edit_suggestion(
        self,
        thesis_id: str,
        suggestion: dict
    ) -> Thesis:
        """
        Apply a suggested edit to the thesis.

        Args:
            thesis_id: Thesis to edit
            suggestion: {"field": "...", "action": "...", "value": "..."}
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")

        field = suggestion.get("field")
        action = suggestion.get("action", "replace")
        value = suggestion.get("value")

        if field not in ["hypothesis", "drivers", "disconfirmers", "expression"]:
            raise ValueError(f"Cannot edit field: {field}")

        # Apply edit based on field type
        if field == "hypothesis":
            thesis_updated = self._thesis_repo.update_hypothesis(thesis_id, value)
            return thesis_updated if thesis_updated else thesis

        if field in ["drivers", "disconfirmers"]:
            thesis_updated = self._thesis_repo.update_list_field(
                thesis_id, field, value, action
            )
            return thesis_updated if thesis_updated else thesis

        # expression - replace for now
        thesis_updated = self._thesis_repo.update_expression(thesis_id, value)
        return thesis_updated if thesis_updated else thesis

    async def complete(self, thesis_id: str) -> Thesis:
        """
        Complete critique session.

        Creates post-critique snapshot and transitions status.
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")

        # Create post-critique snapshot
        self._create_snapshot(thesis, "post_critique")

        # Update status
        self._thesis_repo.update_status(thesis_id, "CRITIQUED")

        # Mark conversation as completed
        self._complete_conversation(thesis_id)

        return self._thesis_repo.get_by_id(thesis_id)

    def _create_snapshot(self, thesis: Thesis, snapshot_type: str) -> ThesisSnapshot:
        """Create a snapshot of the current thesis state"""
        # Convert thesis to dict for storage
        if hasattr(thesis, 'model_dump'):
            content = thesis.model_dump()
        elif hasattr(thesis, 'dict'):
            content = thesis.dict()
        else:
            content = {
                "id": thesis.id,
                "title": thesis.title,
                "hypothesis": thesis.hypothesis,
                "drivers": thesis.drivers,
                "disconfirmers": thesis.disconfirmers,
                "expression": [leg.model_dump() if hasattr(leg, 'model_dump') else (leg.dict() if hasattr(leg, 'dict') else leg) for leg in thesis.expression],
                "status": str(thesis.status) if hasattr(thesis.status, '__str__') else thesis.status
            }

        snapshot = ThesisSnapshot(
            id=f"snap_{uuid.uuid4().hex[:12]}",
            thesis_id=thesis.id,
            snapshot_type=snapshot_type,
            content=content,
            created_at=datetime.now(UTC).isoformat()
        )

        return self._snapshot_repo.insert(snapshot)

    def _init_conversation(self, thesis_id: str):
        """Initialize conversation storage in database"""
        # Check if session already exists
        check_query = text("""
            SELECT id FROM critique_session
            WHERE thesis_id = :thesis_id AND status = 'active'
            LIMIT 1
        """)

        with self._db_engine.connect() as conn:
            result = conn.execute(check_query, {"thesis_id": thesis_id})
            existing = result.fetchone()

            if not existing:
                # Create new session
                session_id = f"cs_{uuid.uuid4().hex[:12]}"
                insert_query = text("""
                    INSERT INTO critique_session (id, thesis_id, conversation, status, created_at, updated_at)
                    VALUES (:id, :thesis_id, :conversation, 'active', NOW(), NOW())
                """)
                conn.execute(insert_query, {
                    "id": session_id,
                    "thesis_id": thesis_id,
                    "conversation": json.dumps({})  # Empty dict, keyed by dimension
                })
                conn.commit()

    def _load_conversation(self, thesis_id: str, dimension: str) -> List[dict]:
        """Load conversation history for a dimension from database"""
        query = text("""
            SELECT conversation
            FROM critique_session
            WHERE thesis_id = :thesis_id AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
        """)

        with self._db_engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            row = result.fetchone()

            if not row:
                return []

            conversation_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            return conversation_data.get(dimension, [])

    def _save_conversation(self, thesis_id: str, dimension: str, messages: List[dict]):
        """Save conversation history for a dimension to database"""
        # Load current conversation
        query_load = text("""
            SELECT conversation, id
            FROM critique_session
            WHERE thesis_id = :thesis_id AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
        """)

        with self._db_engine.connect() as conn:
            result = conn.execute(query_load, {"thesis_id": thesis_id})
            row = result.fetchone()

            if row:
                session_id = row[1]
                conversation_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            else:
                # Create new session
                session_id = f"cs_{uuid.uuid4().hex[:12]}"
                conversation_data = {}

            # Update this dimension's conversation
            conversation_data[dimension] = messages

            # Save back
            if row:
                query_save = text("""
                    UPDATE critique_session
                    SET conversation = :conversation, updated_at = NOW()
                    WHERE id = :id
                """)
                conn.execute(query_save, {
                    "id": session_id,
                    "conversation": json.dumps(conversation_data)
                })
            else:
                query_save = text("""
                    INSERT INTO critique_session (id, thesis_id, conversation, status, created_at, updated_at)
                    VALUES (:id, :thesis_id, :conversation, 'active', NOW(), NOW())
                """)
                conn.execute(query_save, {
                    "id": session_id,
                    "thesis_id": thesis_id,
                    "conversation": json.dumps(conversation_data)
                })
            conn.commit()

    def _complete_conversation(self, thesis_id: str):
        """Mark conversation as completed"""
        query = text("""
            UPDATE critique_session
            SET status = 'completed', updated_at = NOW()
            WHERE thesis_id = :thesis_id AND status = 'active'
        """)

        with self._db_engine.connect() as conn:
            conn.execute(query, {"thesis_id": thesis_id})
            conn.commit()

    def get_conversation_history(self, thesis_id: str, dimension: str) -> List[dict]:
        """Get conversation history for a dimension"""
        return self._load_conversation(thesis_id, dimension)
