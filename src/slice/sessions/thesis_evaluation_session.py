"""
E4: ThesisEvaluationSession - End-to-end thesis evaluation workflow.
"""
from datetime import datetime, timezone
from typing import Optional

from slice.intelligence.context.data_access import DataAccess
from slice.evaluation.thesis_evaluation import ThesisEvaluationService
from slice.llm.llm_tools import LLMTools
from slice.sessions.exceptions import ThesisNotFoundError
from slice.models.session_results import ThesisEvaluationSessionResult
from slice.models.thesis import Thesis


class ThesisEvaluationSession:
    """
    Orchestrates a complete thesis evaluation: E2 (quant) + E3 (LLM review).
    
    Atomic persistence: only writes to DB after both E2 and E3 succeed.
    If either fails, no evaluation record is created.
    """

    def __init__(
        self,
        data_access: DataAccess,
        eval_service: ThesisEvaluationService,
        llm_tools: LLMTools,
        exec_adapter: Optional[object] = None,
    ) -> None:
        """
        Initialize the session with required dependencies.
        
        Args:
            data_access: Data access layer for thesis loading and persistence
            eval_service: E2 quant evaluation service
            llm_tools: E3 LLM tools wrapper
            exec_adapter: Optional E5 execution adapter for trade plan generation
        """
        self.data = data_access
        self.eval_service = eval_service
        self.llm = llm_tools
        self.exec_adapter = exec_adapter

    async def run(self, thesis_id: str) -> ThesisEvaluationSessionResult:
        """
        Run the complete evaluation workflow for a thesis.
        
        Steps:
        1. Load thesis by ID
        2. Run E2 quant evaluation
        3. Run E3 LLM review
        4. (Optional) Generate trade plan via E5 adapter
        5. Persist evaluation atomically (only if steps 2-3 succeed)
        6. Return structured result
        
        Args:
            thesis_id: Thesis identifier
            
        Returns:
            ThesisEvaluationSessionResult with evaluation, review, and optional trade plan
            
        Raises:
            ThesisNotFoundError: If thesis not found
            Exception: If E2 or E3 fails (no DB writes)
        """
        # 1. Load thesis
        thesis = self.data.get_thesis(thesis_id)
        if thesis is None:
            raise ThesisNotFoundError(thesis_id)

        # 2. Run E2 quant evaluation
        eval_result = self.eval_service.evaluate_thesis(thesis)

        # 3. Run E3 LLM review (hard requirement - if this fails, no DB write)
        review = await self.llm.review_thesis(thesis, eval_result)

        # 4. Optional trade plan generation (non-fatal if it fails)
        trade_plan: Optional[dict] = None
        if self.exec_adapter is not None:
            try:
                # For evaluation phase, use a fixed notional or configuration value
                # E5: Default notional for illustrative plan in evaluation
                DEFAULT_EVAL_NOTIONAL = 100_000.0
                if hasattr(self.exec_adapter, "create_plan_from_thesis"):
                    plan = self.exec_adapter.create_plan_from_thesis(
                        thesis=thesis,
                        total_notional=DEFAULT_EVAL_NOTIONAL,
                    )
                    trade_plan = plan.dict() if hasattr(plan, "dict") else plan
            except Exception:
                # Log and move on - evaluation does not depend on plan success
                trade_plan = None

        # 5. Atomic persistence (only reached if E2 and E3 both succeeded)
        evaluated_at = datetime.now(timezone.utc)
        self.data.save_thesis_evaluation(
            thesis_id=thesis_id,
            evaluation=eval_result,
            review=review,
            evaluated_at=evaluated_at,
        )

        # 6. Assemble result DTO
        return ThesisEvaluationSessionResult(
            thesis_id=thesis_id,
            evaluation=eval_result,
            review=review,
            trade_plan=trade_plan,
            evaluated_at=evaluated_at,
        )

