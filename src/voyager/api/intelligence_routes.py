from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from voyager.session.models import SessionResponse
from voyager.intelligence.context.data_access import DataAccess
from voyager.intelligence.orchestrator_client import OrchestratorClient
from voyager.intelligence.long_horizon import run_long_horizon_analysis
from voyager.intelligence.strategy import run_strategy_recommendation
from voyager.intelligence.portfolio_diagnostics import run_portfolio_diagnostics
from voyager.intelligence.narrative import run_narrative_coherence


router = APIRouter(prefix="/api/v1/intel", tags=["intelligence"])


# ----------------------------
# Dependency providers (duck-typed)
# ----------------------------

def get_thesis_reviewer() -> Any:
    """
    Dependency placeholder for a ThesisReviewer instance.

    In production wiring, this should return a real ThesisReviewer.
    In tests, this function is monkeypatched to return a fake.
    """
    raise RuntimeError("ThesisReviewer dependency not wired")


def get_consistency_checker() -> Any:
    """
    Dependency placeholder for a ThesisConsistencyChecker instance.
    """
    raise RuntimeError("ThesisConsistencyChecker dependency not wired")


def get_intuition_engine() -> Any:
    """
    Dependency placeholder for an IntuitionQAEngine instance.
    """
    raise RuntimeError("IntuitionQAEngine dependency not wired")


def get_commentary_engine() -> Any:
    """
    Dependency placeholder for a CommentaryEngine instance.
    """
    raise RuntimeError("CommentaryEngine dependency not wired")


# ----------------------------
# Request models
# ----------------------------

class ReviewThesisRequest(BaseModel):
    thesis_id: int
    include_memory: bool = True
    include_risk: bool = True
    extra_instructions: Optional[str] = None


class ConsistencyRequest(BaseModel):
    include_memory: bool = True
    include_risk: bool = False
    extra_instructions: Optional[str] = None


class IntuitionQARequest(BaseModel):
    question: str
    k: int = 5
    include_memory: bool = False
    include_risk: bool = False
    extra_instructions: Optional[str] = None


class DailyCommentaryRequest(BaseModel):
    include_memory: bool = False
    include_risk: bool = True
    extra_instructions: Optional[str] = None


class WeeklyCommentaryRequest(BaseModel):
    week_label: Optional[str] = None
    include_memory: bool = False
    include_risk: bool = True
    extra_instructions: Optional[str] = None


# ----------------------------
# Phase 7 Request Models
# ----------------------------

class LongHorizonRequest(BaseModel):
    thesis_id: int
    horizon_months: Optional[int] = 12


class StrategyRequest(BaseModel):
    extra_instructions: Optional[str] = None


class DiagnosticsRequest(BaseModel):
    extra_instructions: Optional[str] = None


class NarrativeRequest(BaseModel):
    window_label: Optional[str] = None
    extra_instructions: Optional[str] = None


# ----------------------------
# Routes
# ----------------------------

@router.post("/thesis/review", response_model=SessionResponse)
async def review_thesis_endpoint(
    req: ReviewThesisRequest,
    reviewer: Any = Depends(get_thesis_reviewer),
) -> SessionResponse:
    return await reviewer.review_thesis(
        thesis_id=req.thesis_id,
        include_memory=req.include_memory,
        include_risk=req.include_risk,
        extra_instructions=req.extra_instructions,
    )


@router.post("/thesis/consistency", response_model=SessionResponse)
async def thesis_consistency_endpoint(
    req: ConsistencyRequest,
    checker: Any = Depends(get_consistency_checker),
) -> SessionResponse:
    return await checker.analyze(
        include_memory=req.include_memory,
        include_risk=req.include_risk,
        extra_instructions=req.extra_instructions,
    )


@router.post("/qa", response_model=SessionResponse)
async def intuition_qa_endpoint(
    req: IntuitionQARequest,
    engine: Any = Depends(get_intuition_engine),
) -> SessionResponse:
    return await engine.answer(
        question=req.question,
        k=req.k,
        include_memory=req.include_memory,
        include_risk=req.include_risk,
        extra_instructions=req.extra_instructions,
    )


@router.post("/commentary/daily", response_model=SessionResponse)
async def daily_commentary_endpoint(
    req: DailyCommentaryRequest,
    engine: Any = Depends(get_commentary_engine),
) -> SessionResponse:
    return await engine.generate_daily(
        include_memory=req.include_memory,
        include_risk=req.include_risk,
        extra_instructions=req.extra_instructions,
    )


@router.post("/commentary/weekly", response_model=SessionResponse)
async def weekly_commentary_endpoint(
    req: WeeklyCommentaryRequest,
    engine: Any = Depends(get_commentary_engine),
) -> SessionResponse:
    return await engine.generate_weekly(
        week_label=req.week_label,
        include_memory=req.include_memory,
        include_risk=req.include_risk,
        extra_instructions=req.extra_instructions,
    )


# ----------------------------
# Phase 7 Routes
# ----------------------------

@router.post("/horizon", response_model=SessionResponse)
async def long_horizon_endpoint(
    req: LongHorizonRequest,
    data_access: DataAccess = Depends(DataAccess.depends),
    orchestrator: OrchestratorClient = Depends(OrchestratorClient.depends),
) -> SessionResponse:
    """
    Phase 7: Long-horizon reasoning endpoint.
    Thin route that delegates entirely to the engine.
    """
    try:
        return await run_long_horizon_analysis(
            thesis_id=req.thesis_id,
            horizon_months=req.horizon_months or 12,
            data_access=data_access,
            orchestrator=orchestrator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/strategy", response_model=SessionResponse)
async def strategy_endpoint(
    req: StrategyRequest,
    data_access: DataAccess = Depends(DataAccess.depends),
    orchestrator: OrchestratorClient = Depends(OrchestratorClient.depends),
) -> SessionResponse:
    """
    Phase 7: Strategy recommendation endpoint.
    Thin route that delegates to the strategy engine.
    """
    return await run_strategy_recommendation(
        data_access=data_access,
        orchestrator=orchestrator,
        extra_instructions=req.extra_instructions,
    )


@router.post("/diagnostics", response_model=SessionResponse)
async def diagnostics_endpoint(
    req: DiagnosticsRequest,
    data_access: DataAccess = Depends(DataAccess.depends),
    orchestrator: OrchestratorClient = Depends(OrchestratorClient.depends),
) -> SessionResponse:
    """
    Phase 7: Portfolio diagnostics endpoint.
    Thin route that delegates to the diagnostics engine.
    """
    return await run_portfolio_diagnostics(
        data_access=data_access,
        orchestrator=orchestrator,
        extra_instructions=req.extra_instructions,
    )


@router.post("/narrative", response_model=SessionResponse)
async def narrative_endpoint(
    req: NarrativeRequest,
    data_access: DataAccess = Depends(DataAccess.depends),
    orchestrator: OrchestratorClient = Depends(OrchestratorClient.depends),
) -> SessionResponse:
    """
    Phase 7: Narrative coherence endpoint.
    Thin route that delegates to the narrative engine.
    """
    return await run_narrative_coherence(
        data_access=data_access,
        orchestrator=orchestrator,
        window_label=req.window_label,
        extra_instructions=req.extra_instructions,
    )
