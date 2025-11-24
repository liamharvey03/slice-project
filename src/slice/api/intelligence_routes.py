from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from slice.session.models import SessionResponse

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