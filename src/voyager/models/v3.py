"""
V3-specific models for thesis creation workflow.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

# ===========================================
# Query Translator Models
# ===========================================

class CausalLink(BaseModel):
    """A causal claim extracted from thesis text"""
    claim: str  # "Fed hikes lead to higher real yields"
    concept_a: str  # "Fed hikes"
    concept_b: str  # "real yields"
    direction: str  # "positive" | "negative"

class ResolvedLink(BaseModel):
    """A causal link with concepts resolved to concrete series"""
    claim: str
    series_a: str  # "FEDFUNDS"
    series_b: str  # "DFII10"
    query_type: str  # "correlation"
    direction: str  # "positive" | "negative"

class Ambiguity(BaseModel):
    """An unresolved concept with multiple possible series"""
    concept: str
    candidates: List[dict]  # [{id, name, source}, ...]

class QueryTranslatorOutput(BaseModel):
    """Output from the query translator"""
    links: List[CausalLink]
    resolved: List[ResolvedLink]
    ambiguities: List[Ambiguity]

# ===========================================
# Validation Models
# ===========================================

class ValidationResult(BaseModel):
    """Result of logic validation"""
    status: str  # "complete" | "needs_clarification" | "parse_failed"
    links: Optional[List["LogicLink"]] = None
    ambiguities: Optional[List[Ambiguity]] = None
    error_message: Optional[str] = None

# ===========================================
# Critique Models
# ===========================================

class Concern(BaseModel):
    """A concern raised during critique"""
    dimension: str  # "empirical_grounding", "causal_mechanism", etc.
    severity: str  # "high" | "medium" | "low"
    summary: str  # One sentence description

class CritiqueSummary(BaseModel):
    """Summary of critique across all dimensions"""
    concerns: List[Concern]
    opening_message: str  # Message to show PM

class CritiqueResponse(BaseModel):
    """Response during drill-down conversation"""
    message: str
    thesis_edit_suggestion: Optional[dict] = None  # {field, suggested_value}

# ===========================================
# Backtest Models
# ===========================================

class EquityPoint(BaseModel):
    """Single point on equity curve"""
    date: str  # ISO date
    value: float

class BacktestMetrics(BaseModel):
    """Performance metrics from backtest"""
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float

class FactorExposureResult(BaseModel):
    """Factor model output"""
    betas: dict  # {"rates_level": 0.3, "fx": -0.2, ...}
    r_squared: float
    residual_vol: float

class BacktestResult(BaseModel):
    """Complete backtest result"""
    id: Optional[str] = None
    thesis_id: str
    expression: dict  # {"GLD": 0.7, "TIP": 0.3}
    period_start: str  # ISO date
    period_end: str  # ISO date
    metrics: BacktestMetrics
    equity_curve: List[EquityPoint]
    factor_exposure: Optional[FactorExposureResult] = None
    iteration_count: int = 1
    created_at: Optional[str] = None

# ===========================================
# Sizing Models
# ===========================================

class PortfolioImpact(BaseModel):
    """Impact of adding thesis to existing portfolio"""
    correlation_to_book: float
    marginal_vol: float

class SizingResult(BaseModel):
    """Output from sizing calculation"""
    historical_max_dd: float
    tolerance: float
    implied_size: float
    position_cap: float
    suggested_size: float
    portfolio_impact: Optional[PortfolioImpact] = None

# ===========================================
# API Request/Response Models
# ===========================================

class ThesisDraftInput(BaseModel):
    """Input for creating a new thesis draft"""
    title: str
    hypothesis: str
    drivers: List[str]
    disconfirmers: List[str]
    expression: List[dict]  # [{asset, direction, size_pct}]

class ClarificationInput(BaseModel):
    """PM's clarification for ambiguous series"""
    resolutions: dict  # {concept: series_id}

class CritiqueMessageInput(BaseModel):
    """Message in critique conversation"""
    dimension: str
    message: str

class SizingInput(BaseModel):
    """Input for sizing calculation"""
    max_dd_tolerance: float = Field(ge=0, le=1)
    position_cap: float = Field(ge=0, le=1)
    stop_loss: Optional[float] = Field(default=None, ge=0, le=1)
    time_horizon: Optional[str] = None

class ActivateInput(BaseModel):
    """Input for thesis activation"""
    final_size: float = Field(ge=0, le=1)


# Resolve forward reference for ValidationResult
# Import LogicLink after all classes are defined to avoid circular imports
# Use try/except to handle potential circular import during module initialization
try:
    from voyager.models.thesis import LogicLink
    ValidationResult.model_rebuild()
except ImportError:
    # If circular import occurs, model_rebuild will be called when LogicLink is imported elsewhere
    pass
