"""
V3 API Routes for thesis creation workflow.

Endpoints:
    POST   /api/v3/thesis                    - Create draft
    GET    /api/v3/thesis/{id}               - Get thesis
    PATCH  /api/v3/thesis/{id}               - Update draft
    GET    /api/v3/thesis/{id}/snapshots     - List snapshots

    POST   /api/v3/thesis/{id}/validate      - Run logic validation
    POST   /api/v3/thesis/{id}/validate/clarify - Submit clarifications
    GET    /api/v3/thesis/{id}/validation    - Get latest validation

    POST   /api/v3/thesis/{id}/critique/start    - Start critique
    POST   /api/v3/thesis/{id}/critique/message  - Continue conversation
    POST   /api/v3/thesis/{id}/critique/complete - Complete critique
    POST   /api/v3/thesis/{id}/critique/apply-edit - Apply suggested edit

    POST   /api/v3/thesis/{id}/backtest      - Run backtest
    GET    /api/v3/thesis/{id}/backtest/latest - Get latest backtest
    GET    /api/v3/thesis/{id}/backtest/history - List all backtests

    POST   /api/v3/thesis/{id}/sizing        - Compute sizing
    POST   /api/v3/thesis/{id}/activate-with-rails - Activate thesis
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from voyager.models.thesis import Thesis, RiskRails
from voyager.models.v3 import (
    ClarificationInput,
    CritiqueMessageInput,
    SizingInput,
    ThesisDraftInput,
)
from voyager.services.v3.thesis_service import ThesisService
from voyager.services.v3.validation_service import ValidationService
from voyager.services.v3.critique_service import CritiqueService
from voyager.services.v3.backtest_service import BacktestService
from voyager.services.v3.sizing_service import SizingService
from voyager.api.deps import (
    get_thesis_service_instance,
    get_validation_service_instance,
    get_critique_service_instance,
    get_backtest_service_instance,
    get_sizing_service_instance,
)


router = APIRouter(prefix="/api/v3/thesis", tags=["v3-thesis"])


# ===========================================
# Helper Functions
# ===========================================

def get_thesis_or_404(
    thesis_id: str,
    service: ThesisService
) -> Thesis:
    """Get thesis by ID or raise 404."""
    thesis = service.get(thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail=f"Thesis not found: {thesis_id}")
    return thesis


def serialize_thesis(thesis: Thesis) -> dict:
    """Serialize thesis to dict, handling both Pydantic v1 and v2."""
    if hasattr(thesis, 'model_dump'):
        return thesis.model_dump()
    if hasattr(thesis, 'dict'):
        return thesis.dict()
    return thesis.__dict__


# ===========================================
# Response Models
# ===========================================

class ThesisResponse(BaseModel):
    """Thesis response wrapper"""
    thesis: dict
    status: str


class ValidationResponse(BaseModel):
    """Validation response"""
    status: str  # "complete" | "needs_clarification" | "parse_failed"
    links: Optional[List[dict]] = None
    ambiguities: Optional[List[dict]] = None
    error_message: Optional[str] = None


class CritiqueSummaryResponse(BaseModel):
    """Critique summary response"""
    concerns: List[dict]
    opening_message: str


class CritiqueMessageResponse(BaseModel):
    """Critique conversation response"""
    message: str
    thesis_edit_suggestion: Optional[dict] = None


class BacktestResponse(BaseModel):
    """Backtest response"""
    id: str
    thesis_id: str
    expression: dict
    period_start: str
    period_end: str
    metrics: dict
    equity_curve: List[dict]
    factor_exposure: Optional[dict] = None
    iteration_count: int


class SizingResponse(BaseModel):
    """Sizing response"""
    historical_max_dd: float
    tolerance: float
    implied_size: float
    position_cap: float
    suggested_size: float
    portfolio_impact: Optional[dict] = None


class ActivateWithRailsInput(BaseModel):
    """Combined activation input with risk rails"""
    final_size: float = Field(ge=0, le=1)
    max_dd_tolerance: float = Field(ge=0, le=1)
    position_cap: float = Field(ge=0, le=1)
    stop_loss: Optional[float] = Field(default=None, ge=0, le=1)
    time_horizon: Optional[str] = None


# ===========================================
# Thesis CRUD Endpoints
# ===========================================

@router.post("", response_model=ThesisResponse)
async def create_thesis(
    draft_input: ThesisDraftInput,
    service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Create a new thesis in DRAFT status.

    This is the entry point for Screen 1.
    """
    try:
        thesis = service.create_draft(draft_input)
        return ThesisResponse(
            thesis=serialize_thesis(thesis),
            status="created"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{thesis_id}", response_model=ThesisResponse)
async def get_thesis(
    thesis_id: str,
    service: ThesisService = Depends(get_thesis_service_instance)
):
    """Get thesis by ID"""
    thesis = get_thesis_or_404(thesis_id, service)
    return ThesisResponse(
        thesis=serialize_thesis(thesis),
        status="ok"
    )


@router.patch("/{thesis_id}", response_model=ThesisResponse)
async def update_thesis(
    thesis_id: str,
    updates: dict,
    service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Update thesis fields.
    
    Only allowed in DRAFT, VALIDATED, or CRITIQUED status.
    Allowed fields: title, hypothesis, drivers, disconfirmers, expression, notes, tags
    """
    try:
        thesis = service.update(thesis_id, updates)
        return ThesisResponse(
            thesis=serialize_thesis(thesis),
            status="updated"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{thesis_id}/snapshots", response_model=List[dict])
async def list_snapshots(
    thesis_id: str,
    service: ThesisService = Depends(get_thesis_service_instance)
):
    """List all snapshots for a thesis"""
    get_thesis_or_404(thesis_id, service)
    snapshots = service.get_snapshots(thesis_id)
    return [
        (s.model_dump() if hasattr(s, 'model_dump')
         else (s.dict() if hasattr(s, 'dict') else s.__dict__))
        for s in snapshots
    ]


# ===========================================
# Validation Endpoints (Screen 1)
# ===========================================

@router.post("/{thesis_id}/validate", response_model=ValidationResponse)
async def validate_thesis(
    thesis_id: str,
    service: ValidationService = Depends(get_validation_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Run logic validation on thesis.
    
    Extracts causal links from thesis, resolves to data series,
    and runs quantitative validation.
    
    Returns:
        - status="complete" with links if validation succeeded
        - status="needs_clarification" with ambiguities if concepts couldn't be resolved
        - status="parse_failed" with error_message if thesis couldn't be parsed
    """
    thesis = get_thesis_or_404(thesis_id, thesis_service)

    try:
        result = await service.validate(thesis)
        return ValidationResponse(
            status=result.status,
            links=[
                (link.model_dump() if hasattr(link, 'model_dump')
                 else (link.dict() if hasattr(link, 'dict') else link.__dict__))
                for link in result.links
            ] if result.links else None,
            ambiguities=[
                (a.model_dump() if hasattr(a, 'model_dump')
                 else (a.dict() if hasattr(a, 'dict') else a.__dict__))
                for a in result.ambiguities
            ] if result.ambiguities else None,
            error_message=result.error_message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{thesis_id}/validate/clarify", response_model=ValidationResponse)
async def clarify_validation(
    thesis_id: str,
    clarify_input: ClarificationInput,
    service: ValidationService = Depends(get_validation_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Submit PM clarifications for ambiguous concepts.

    Request body:
        {"resolutions": {"concept_name": "series_id", ...}}
    """
    thesis = get_thesis_or_404(thesis_id, thesis_service)

    try:
        result = await service.validate_with_clarifications(
            thesis, clarify_input.resolutions
        )
        return ValidationResponse(
            status=result.status,
            links=[
                (link.model_dump() if hasattr(link, 'model_dump')
                 else (link.dict() if hasattr(link, 'dict') else link.__dict__))
                for link in result.links
            ] if result.links else None,
            ambiguities=[
                (a.model_dump() if hasattr(a, 'model_dump')
                 else (a.dict() if hasattr(a, 'dict') else a.__dict__))
                for a in result.ambiguities
            ] if result.ambiguities else None,
            error_message=result.error_message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{thesis_id}/validation", response_model=Optional[dict])
async def get_latest_validation(
    thesis_id: str,
    service: ValidationService = Depends(get_validation_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """Get most recent validation for a thesis"""
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists
    validation = service.get_latest_validation(thesis_id)
    if validation is None:
        return None
    return (
        validation.model_dump() if hasattr(validation, 'model_dump')
        else (validation.dict() if hasattr(validation, 'dict') else validation.__dict__)
    )


# ===========================================
# Critique Endpoints (Screen 2)
# ===========================================

@router.post("/{thesis_id}/critique/start", response_model=CritiqueSummaryResponse)
async def start_critique(
    thesis_id: str,
    service: CritiqueService = Depends(get_critique_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Start critique session.

    Creates pre-critique snapshot and generates initial critique summary.
    Returns concerns across 6 dimensions with opening message.
    """
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists

    try:
        summary = await service.start(thesis_id)
        return CritiqueSummaryResponse(
            concerns=[
                (c.model_dump() if hasattr(c, 'model_dump')
                 else (c.dict() if hasattr(c, 'dict') else c.__dict__))
                for c in summary.concerns
            ],
            opening_message=summary.opening_message
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{thesis_id}/critique/message", response_model=CritiqueMessageResponse)
async def critique_message(
    thesis_id: str,
    message_input: CritiqueMessageInput,
    service: CritiqueService = Depends(get_critique_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Continue critique conversation on a specific dimension.

    Request body:
        {"dimension": "empirical_grounding", "message": "I think..."}
    """
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists

    try:
        response = await service.continue_conversation(
            thesis_id=thesis_id,
            dimension=message_input.dimension,
            user_message=message_input.message
        )
        return CritiqueMessageResponse(
            message=response.message,
            thesis_edit_suggestion=response.thesis_edit_suggestion
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{thesis_id}/critique/complete", response_model=ThesisResponse)
async def complete_critique(
    thesis_id: str,
    service: CritiqueService = Depends(get_critique_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Complete critique session.

    Creates post-critique snapshot and transitions status to CRITIQUED.
    """
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists

    try:
        thesis = await service.complete(thesis_id)
        return ThesisResponse(
            thesis=serialize_thesis(thesis),
            status="critique_completed"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{thesis_id}/critique/apply-edit", response_model=ThesisResponse)
async def apply_critique_edit(
    thesis_id: str,
    suggestion: dict,
    service: CritiqueService = Depends(get_critique_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Apply a suggested edit from critique.

    Request body:
        {"field": "hypothesis", "action": "replace", "value": "..."}
    """
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists

    try:
        thesis = service.apply_edit_suggestion(thesis_id, suggestion)
        return ThesisResponse(
            thesis=serialize_thesis(thesis),
            status="edit_applied"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ===========================================
# Backtest Endpoints (Screen 3)
# ===========================================

@router.post("/{thesis_id}/backtest", response_model=BacktestResponse)
async def run_backtest(
    thesis_id: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: BacktestService = Depends(get_backtest_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Run backtest on thesis expression.

    Query params:
        start_date: Optional start date (default: 5 years ago)
        end_date: Optional end date (default: today)
    """
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists

    try:
        result = service.run(
            thesis_id=thesis_id,
            start_date=start_date,
            end_date=end_date,
            include_factor_exposure=True
        )
        return BacktestResponse(
            id=result.id or "",
            thesis_id=result.thesis_id,
            expression=result.expression,
            period_start=result.period_start,
            period_end=result.period_end,
            metrics=(result.metrics.model_dump() if hasattr(result.metrics, 'model_dump')
                     else result.metrics.dict()),
            equity_curve=[
                ep.model_dump() if hasattr(ep, 'model_dump') else ep.dict()
                for ep in result.equity_curve
            ],
            factor_exposure=(
                result.factor_exposure.model_dump() if hasattr(result.factor_exposure, 'model_dump')
                else result.factor_exposure.dict()
            ) if result.factor_exposure else None,
            iteration_count=result.iteration_count
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{thesis_id}/backtest/latest", response_model=Optional[BacktestResponse])
async def get_latest_backtest(
    thesis_id: str,
    service: BacktestService = Depends(get_backtest_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """Get most recent backtest result"""
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists
    result = service.get_latest(thesis_id)
    if result is None:
        return None

    return BacktestResponse(
        id=result.id or "",
        thesis_id=result.thesis_id,
        expression=result.expression,
        period_start=result.period_start,
        period_end=result.period_end,
        metrics=(result.metrics.model_dump() if hasattr(result.metrics, 'model_dump')
                 else result.metrics.dict()),
        equity_curve=[
            ep.model_dump() if hasattr(ep, 'model_dump') else ep.dict()
            for ep in result.equity_curve
        ],
        factor_exposure=(
            result.factor_exposure.model_dump() if hasattr(result.factor_exposure, 'model_dump')
            else result.factor_exposure.dict()
        ) if result.factor_exposure else None,
        iteration_count=result.iteration_count
    )


@router.get("/{thesis_id}/backtest/history", response_model=List[BacktestResponse])
async def list_backtests(
    thesis_id: str,
    service: BacktestService = Depends(get_backtest_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance)
):
    """List all backtests for a thesis"""
    get_thesis_or_404(thesis_id, thesis_service)  # Verify thesis exists

    results = service.list_history(thesis_id)
    if not results:
        return []

    return [
        BacktestResponse(
            id=r.id or "",
            thesis_id=r.thesis_id,
            expression=r.expression,
            period_start=r.period_start,
            period_end=r.period_end,
            metrics=(r.metrics.model_dump() if hasattr(r.metrics, 'model_dump')
                     else r.metrics.dict()),
            equity_curve=[
                ep.model_dump() if hasattr(ep, 'model_dump') else ep.dict()
                for ep in r.equity_curve
            ],
            factor_exposure=(
                r.factor_exposure.model_dump() if hasattr(r.factor_exposure, 'model_dump')
                else r.factor_exposure.dict()
            ) if r.factor_exposure else None,
            iteration_count=r.iteration_count
        )
        for r in results
    ]


# ===========================================
# Sizing Endpoints (Screen 4)
# ===========================================

@router.post("/{thesis_id}/sizing", response_model=SizingResponse)
async def compute_sizing(
    thesis_id: str,
    sizing_input: SizingInput,
    service: SizingService = Depends(get_sizing_service_instance),
    thesis_service: ThesisService = Depends(get_thesis_service_instance),
    backtest_service: BacktestService = Depends(get_backtest_service_instance)
):
    """
    Compute sizing based on constraints.

    Request body:
        {
            "max_dd_tolerance": 0.08,
            "position_cap": 0.10,
            "stop_loss": null,
            "time_horizon": null
        }
    """
    thesis = get_thesis_or_404(thesis_id, thesis_service)

    backtest = backtest_service.get_latest(thesis_id)
    if backtest is None:
        raise HTTPException(status_code=400, detail="No backtest found. Run backtest first.")

    rails = RiskRails(
        max_dd_tolerance=sizing_input.max_dd_tolerance,
        position_cap=sizing_input.position_cap,
        stop_loss=sizing_input.stop_loss,
        time_horizon=sizing_input.time_horizon
    )

    try:
        result = service.compute(
            thesis=thesis,
            rails=rails,
            backtest=backtest,
            include_portfolio_impact=True
        )
        return SizingResponse(
            historical_max_dd=result.historical_max_dd,
            tolerance=result.tolerance,
            implied_size=result.implied_size,
            position_cap=result.position_cap,
            suggested_size=result.suggested_size,
            portfolio_impact=(
                (result.portfolio_impact.model_dump()
                 if hasattr(result.portfolio_impact, 'model_dump')
                 else result.portfolio_impact.dict())
                if result.portfolio_impact else None
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{thesis_id}/activate-with-rails", response_model=ThesisResponse)
async def activate_thesis_with_rails(
    thesis_id: str,
    activate_input: ActivateWithRailsInput,
    service: ThesisService = Depends(get_thesis_service_instance)
):
    """
    Activate thesis with final size and risk rails.

    Preferred endpoint for activation - includes all necessary data.

    Request body:
        {
            "final_size": 0.10,
            "max_dd_tolerance": 0.08,
            "position_cap": 0.10,
            "stop_loss": null,
            "time_horizon": null
        }
    """
    get_thesis_or_404(thesis_id, service)  # Verify thesis exists

    rails = RiskRails(
        max_dd_tolerance=activate_input.max_dd_tolerance,
        position_cap=activate_input.position_cap,
        stop_loss=activate_input.stop_loss,
        time_horizon=activate_input.time_horizon
    )

    try:
        thesis = service.activate(
            thesis_id=thesis_id,
            final_size=activate_input.final_size,
            rails=rails
        )
        return ThesisResponse(
            thesis=serialize_thesis(thesis),
            status="activated"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
