"""
E4: API endpoints for thesis evaluation and daily update sessions.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from slice.intelligence.context.data_access import DataAccess
from slice.intelligence.orchestrator_client import OrchestratorClient
from slice.evaluation.thesis_evaluation import ThesisEvaluationService
from slice.quant.price_source import PriceSource
from slice.llm.llm_tools import LLMTools
from slice.sessions.thesis_evaluation_session import ThesisEvaluationSession
from slice.sessions.daily_update_session import DailyUpdateSession
from slice.sessions.cross_thesis_session import CrossThesisSession
from slice.sessions.exceptions import ThesisNotFoundError
from slice.models.session_results import (
    ThesisEvaluationSessionResult,
    DailyUpdateSessionResult,
    CrossThesisSessionResult,
)
from slice.execution.paper import PaperExecutionAdapter
from slice.models.common import ThesisStatus
from slice.api.deps import get_price_source_instance


router = APIRouter(prefix="/api/v1", tags=["e4-sessions"])


# ----------------------------
# Dependency providers
# ----------------------------

def get_eval_service(
    price_source: PriceSource = Depends(lambda: None),  # Will be overridden in tests
) -> ThesisEvaluationService:
    """
    Dependency provider for ThesisEvaluationService.
    
    In production, this should be wired with a real PriceSource.
    In tests, this is monkeypatched.
    """
    if price_source is None:
        raise RuntimeError("PriceSource dependency not wired")
    return ThesisEvaluationService(price_source=price_source)


def get_llm_tools(
    orchestrator: OrchestratorClient = Depends(OrchestratorClient.depends),
) -> LLMTools:
    """
    Dependency provider for LLMTools.
    
    Wraps OrchestratorClient to provide E3 LLM tool interface.
    Creates an adapter to bridge OrchestratorClient and OrchestratorProtocol.
    """
    from slice.llm.tools import OrchestratorProtocol
    from slice.session.models import SessionOptions, SessionResponse
    
    class OrchestratorAdapter(OrchestratorProtocol):
        """Adapter to make OrchestratorClient compatible with OrchestratorProtocol."""
        
        def __init__(self, client: OrchestratorClient):
            self._client = client
        
        async def run_session(self, text: str, options: SessionOptions) -> SessionResponse:
            """Adapt OrchestratorClient.run_session to OrchestratorProtocol interface."""
            # Map SessionOptions to OrchestratorClient parameters
            mode = options.mode
            include_memory = options.use_memory and not options.skip_memory
            include_risk = options.use_risk and not options.skip_risk
            skip_ingest = options.skip_ingest
            
            return await self._client.run_session(
                user_text=text,
                mode=mode,
                include_memory=include_memory,
                include_risk=include_risk,
                skip_ingest=skip_ingest,
            )
    
    adapter = OrchestratorAdapter(orchestrator)
    return LLMTools(adapter)


# ----------------------------
# Request models
# ----------------------------

class DailyUpdateRequest(BaseModel):
    """Request model for daily update endpoint."""
    as_of: Optional[str] = None  # ISO date string, optional


class CrossThesisRequest(BaseModel):
    """Request model for cross-thesis analysis."""
    thesis_ids: list[str]


class ApprovePlanRequest(BaseModel):
    """Request model for approve-plan endpoint."""
    total_notional: float | None = None


# ----------------------------
# Routes
# ----------------------------

@router.post(
    "/thesis/{thesis_id}/evaluate",
    response_model=ThesisEvaluationSessionResult,
)
async def evaluate_thesis(
    thesis_id: str,
    data_access: DataAccess = Depends(DataAccess.depends),
    eval_service: ThesisEvaluationService = Depends(get_eval_service),
    llm_tools: LLMTools = Depends(get_llm_tools),
):
    """
    Evaluate a thesis end-to-end: E2 quant evaluation + E3 LLM review.
    
    Error semantics:
    - 404 if thesis not found
    - 500 if E2 or E3 fails (no DB writes)
    """
    session = ThesisEvaluationSession(
        data_access=data_access,
        eval_service=eval_service,
        llm_tools=llm_tools,
        exec_adapter=None,  # E5 hook, not implemented in E4
    )
    
    try:
        return await session.run(thesis_id)
    except ThesisNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # All other failures (E2/E3 errors) → 500, no DB writes
        raise HTTPException(
            status_code=500,
            detail=f"Thesis evaluation failed: {e}",
        )


@router.post(
    "/session/daily-update",
    response_model=DailyUpdateSessionResult,
)
async def daily_update(
    req: Optional[DailyUpdateRequest] = None,
    data_access: DataAccess = Depends(DataAccess.depends),
    llm_tools: LLMTools = Depends(get_llm_tools),
):
    """
    Run daily portfolio update: detect alerts, generate summary.
    
    Error semantics:
    - 500 if DB/data access fails
    - 200 even if LLM fails (alerts persisted, insufficient_context=True)
    """
    from datetime import date
    
    as_of: Optional[date] = None
    if req and req.as_of:
        as_of = date.fromisoformat(req.as_of)
    
    session = DailyUpdateSession(
        data_access=data_access,
        llm_tools=llm_tools,
    )
    
    try:
        return await session.run(as_of=as_of)
    except Exception as e:
        # DB/data failures → 500
        raise HTTPException(
            status_code=500,
            detail=f"Daily update failed: {e}",
        )


@router.post(
    "/thesis/compare",
    response_model=CrossThesisSessionResult,
)
async def compare_theses(
    req: CrossThesisRequest,
    data_access: DataAccess = Depends(DataAccess.depends),
    llm_tools: LLMTools = Depends(get_llm_tools),
):
    """
    Optional: Cross-thesis analysis endpoint.
    
    Analyzes relationships between multiple theses.
    """
    session = CrossThesisSession(
        data_access=data_access,
        llm_tools=llm_tools,
    )
    
    try:
        return await session.run(req.thesis_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cross-thesis analysis failed: {e}",
        )


@router.post("/thesis/{thesis_id}/approve-plan")
def approve_plan(
    thesis_id: str,
    body: ApprovePlanRequest | None = None,
    data_access: DataAccess = Depends(DataAccess.depends),
    price_source: PriceSource = Depends(get_price_source_instance),
):
    """
    E5: Approve and execute a trade plan for a thesis.
    
    Steps:
    1. Validates thesis exists and is not already ACTIVE
    2. Creates TradePlan from thesis + notional (using NaiveSizingEngine)
    3. Executes the plan as paper trades
    4. Marks thesis as ACTIVE
    
    Error semantics:
    - 404 if thesis not found
    - 400 if thesis already active or contains short legs
    - 500 if execution fails (e.g., invalid prices)
    """
    # 1. Load thesis
    thesis = data_access.get_thesis(thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    
    # 2. Prevent double-approval
    if thesis.status == ThesisStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Thesis already active")
    
    # 3. Create execution adapter
    adapter = PaperExecutionAdapter(
        trade_repo=data_access.trade_repo,
        price_source=price_source,
    )
    
    # 4. Determine notional (default 100k)
    notional = (
        body.total_notional
        if body is not None and body.total_notional is not None
        else 100_000.0
    )
    
    # 5. Create plan (400 if shorts/invalid)
    try:
        plan = adapter.create_plan_from_thesis(
            thesis,
            total_notional=notional,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # 6. Execute plan (500 if price error)
    try:
        trades = adapter.execute_plan(plan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")
    
    # 7. Mark thesis ACTIVE
    thesis.status = ThesisStatus.ACTIVE
    data_access.thesis_repo.update(thesis)
    
    return {
        "status": "success",
        "thesis_id": thesis_id,
        "total_notional": notional,
        "executed_trades": [t.dict() for t in trades],
    }

