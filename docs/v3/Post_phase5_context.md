# Voyager V3 Architecture Summary

## Document Purpose

This document provides comprehensive context on the V3 thesis management system architecture. It is intended as persistent project context for AI assistants working on Voyager, enabling them to understand the system without re-reading implementation details.

**Last Updated:** December 2024  
**Status:** Phases 0-5 Complete, Phase 6 (UI) Pending

---

## Executive Summary

Voyager V3 is a complete redesign of the investment thesis management system. It bridges quantitative analysis with investment decision-making through a structured four-screen workflow that combines LLM-powered critique with rigorous backtesting.

**Core Philosophy:**
- Logic drives quantitative validation (not the reverse)
- PM maintains control; system provides information
- Transparency over "magic" — all calculations visible
- Quant analysis infused throughout, not siloed

**What V3 Replaced:**
- Unrealistic synthetic price paths → Real historical backtesting (VectorBT)
- Generic scenarios → Thesis-specific driver validation
- Missing factor decomposition → 5-factor attribution model
- Clunky thesis entry → Four-screen guided workflow
- Loose LLM-quant coupling → Integrated validation pipeline

---

## Four-Screen Thesis Workflow

### Screen 1: Draft & Validate
**Purpose:** Create thesis and validate causal logic against data

**Flow:**
1. PM writes thesis (hypothesis, drivers, disconfirmers, expression)
2. QueryTranslator extracts causal claims via LLM
3. SeriesRegistry resolves concepts to data series (DFII10, GLD, etc.)
4. QuantService runs correlation/relationship tests
5. Results show which claims data supports/contradicts

**Status Transition:** WATCHLIST → VALIDATED

**Key Insight:** LLM does linguistic parsing; resolution is deterministic. No LLM hallucination in data mapping.

---

### Screen 2: Critique
**Purpose:** Structured LLM critique across six dimensions

**Dimensions:**
1. Logical Coherence — Does A → B → C follow?
2. Causal Mechanism — How does A cause B?
3. Hidden Assumptions — What's taken for granted?
4. Empirical Grounding — Does data support claims?
5. Historical Precedent — Has this worked before?
6. Expression Fit — Does the trade capture the thesis?

**Flow:**
1. CritiqueEngine generates summary with concerns
2. PM drills down on specific dimensions
3. LLM may suggest thesis edits
4. PM accepts/rejects suggestions
5. Snapshots capture pre/post critique state

**Status Transition:** VALIDATED → CRITIQUED

---

### Screen 3: Backtest & Expression
**Purpose:** Quantitative performance validation

**Flow:**
1. BacktestEngine runs thesis expression against historical data
2. Computes: Total Return, CAGR, Volatility, Sharpe, Max Drawdown
3. Factor exposure analysis (rates, real yields, FX, commodities, equity)
4. PM can iterate on expression weights
5. Each iteration tracked with count

**Status Transition:** CRITIQUED → BACKTESTED

---

### Screen 4: Constraints & Sizing
**Purpose:** Risk-aware position sizing and activation

**Core Formula:**
```
implied_size = max_dd_tolerance / historical_max_dd
suggested_size = min(implied_size, position_cap)
```

**Flow:**
1. PM sets risk rails (max DD tolerance, position cap, stop loss)
2. SizingService computes suggested size
3. Portfolio impact shown (correlation to book, marginal vol)
4. PM adjusts final size
5. Activation creates snapshot and transitions to ACTIVE

**Status Transition:** BACKTESTED → ACTIVE

---

## Status Lifecycle

```
WATCHLIST → VALIDATED → CRITIQUED → BACKTESTED → ACTIVE → CLOSED
    │           │           │            │          │
    └───────────┴───────────┴────────────┴──────────┴──→ CLOSED
                    (can abandon from any state)
```

**Valid Transitions:**
```python
VALID_TRANSITIONS = {
    "WATCHLIST": ["VALIDATED", "CLOSED"],
    "VALIDATED": ["CRITIQUED", "WATCHLIST", "CLOSED"],
    "CRITIQUED": ["BACKTESTED", "VALIDATED", "CLOSED"],
    "BACKTESTED": ["ACTIVE", "CRITIQUED", "CLOSED"],
    "ACTIVE": ["CLOSED"],
    "CLOSED": []
}
```

---

## Architecture Layers

### Layer 1: Data Layer

**Database:** PostgreSQL with pgvector extension

**Core Tables:**
- `thesis` — Main thesis record with V3 fields (risk_rails, final_size)
- `market_data` — OHLCV price data from TwelveData
- `econ_data` — Macro series from FRED

**V3 Tables:**
- `logic_validation` — Stores validation results with LogicLink array
- `thesis_snapshot` — Point-in-time thesis state (pre_critique, post_critique, activation)
- `critique_session` — Conversation history by dimension
- `backtest_result` — Backtest metrics, equity curve, factor exposure

**Key Schema Decisions:**
- All IDs are TEXT (not UUID) for readable prefixes: `thesis_`, `val_`, `snap_`, `bt_`, `cs_`
- JSONB for flexible nested structures (links, expression, risk_rails)
- Timestamps as ISO strings for portability

---

### Layer 2: Repository Layer

**Pattern:** Repository per entity, injected via factories

**Repositories:**
- `ThesisRepository` — CRUD + update methods for individual fields
- `LogicValidationRepository` — Insert, get_by_thesis, list_by_thesis
- `ThesisSnapshotRepository` — Insert, list_by_thesis, get_latest_by_type
- `BacktestResultRepository` — Insert, get_latest, count_by_thesis, list_by_thesis
- `TradeRepository` — Position tracking (via DataAccess)

**Update Methods in ThesisRepository:**
```python
update_status(thesis_id, status)
update_hypothesis(thesis_id, hypothesis)
update_list_field(thesis_id, field, value, action)  # drivers, disconfirmers
update_expression(thesis_id, expression)
update_risk_rails(thesis_id, risk_rails)
update_final_size(thesis_id, final_size)
```

---

### Layer 3: Quant Layer

**QuantService** (`src/voyager/quant/quant_service.py`)
- `correlation(series_a, series_b, period)` — Pearson correlation with p-value
- `conditional_returns(asset, condition_series, threshold)` — Returns when condition met
- `distribution(series, period)` — Stats: mean, std, percentiles, current rank
- `relationship_strength(series_a, series_b, expected_direction)` — Interpretation layer

**BacktestEngine** (`src/voyager/quant/backtest_engine.py`)
- Built on VectorBT (free version)
- Static allocation with optional rebalancing
- Commission: 0.1%, Slippage: 0.05%
- Equity curve sampled to max 500 points
- Factor exposure via OLS regression

**Factor Proxies:**
| Factor | Proxy | Rationale |
|--------|-------|-----------|
| rates_level | TLT | Long-term Treasury |
| real_yields | TIP | TIPS bonds |
| fx | UUP | USD strength |
| commodities | GLD | Gold (reliable data) |
| equity | SPY | S&P 500 |

---

### Layer 4: LLM Layer

**QueryTranslator** (`src/voyager/llm/query_translator.py`)
- Extracts CausalLink objects from thesis text
- Resolves concepts to series via SeriesRegistry (deterministic)
- Returns ambiguities for PM clarification
- No LLM in data resolution — prevents hallucination

**CritiqueEngine** (`src/voyager/llm/critique_engine.py`)
- Six-dimension critique framework
- Summary mode: Initial concerns across all dimensions
- Drill-down mode: Multi-turn conversation on specific dimension
- Can suggest thesis edits (PM decides to accept)

**LLM Integration:**
- Uses OpenAI GPT-4 via existing client
- 30-second timeout on all calls
- Graceful degradation on failure (empty concerns, error message)
- JSON extraction via `extract_json()` utility

---

### Layer 5: Service Layer

**ValidationService** (`src/voyager/services/v3/validation_service.py`)
- Orchestrates Screen 1 workflow
- QueryTranslator → QuantService → Persistence
- Handles ambiguity resolution flow
- Updates thesis status to VALIDATED

**CritiqueService** (`src/voyager/services/v3/critique_service.py`)
- Orchestrates Screen 2 workflow
- Manages conversation history in database
- Creates pre/post critique snapshots
- Applies thesis edit suggestions via repository

**BacktestService** (`src/voyager/services/v3/backtest_service.py`)
- Orchestrates Screen 3 workflow
- Loads thesis, converts expression, runs backtest
- Computes factor exposure
- Tracks iteration count
- Updates thesis status to BACKTESTED

**SizingService** (`src/voyager/services/v3/sizing_service.py`)
- Orchestrates Screen 4 sizing
- Core formula: implied_size = tolerance / max_dd
- Portfolio impact calculation (optional)
- Returns None gracefully if no portfolio or insufficient data

**ThesisService** (`src/voyager/services/v3/thesis_service.py`)
- Lifecycle orchestration across all screens
- CRUD operations with status-aware editing
- Status transitions with validation
- Activation with snapshot creation

---

### Layer 6: API Layer

**Router:** `/api/v3/thesis` prefix, 17 endpoints

**Endpoint Summary:**
```
POST   /api/v3/thesis                         Create draft
GET    /api/v3/thesis/{id}                    Get thesis
PATCH  /api/v3/thesis/{id}                    Update thesis
GET    /api/v3/thesis/{id}/snapshots          List snapshots

POST   /api/v3/thesis/{id}/validate           Run validation
POST   /api/v3/thesis/{id}/validate/clarify   Submit clarifications
GET    /api/v3/thesis/{id}/validation         Get latest validation

POST   /api/v3/thesis/{id}/critique/start     Start critique
POST   /api/v3/thesis/{id}/critique/message   Continue conversation
POST   /api/v3/thesis/{id}/critique/complete  Complete critique
POST   /api/v3/thesis/{id}/critique/apply-edit Apply edit suggestion

POST   /api/v3/thesis/{id}/backtest           Run backtest
GET    /api/v3/thesis/{id}/backtest/latest    Get latest backtest
GET    /api/v3/thesis/{id}/backtest/history   List all backtests

POST   /api/v3/thesis/{id}/sizing             Compute sizing
POST   /api/v3/thesis/{id}/activate-with-rails Activate thesis
```

**Error Handling:**
- 200: Success
- 400: Bad request (validation errors, wrong status)
- 404: Thesis not found
- 422: Pydantic validation error
- 500: Internal server error

---

## Data Models

### Core Models (`src/voyager/models/thesis.py`)

```python
class Thesis(BaseModel):
    id: str
    title: str
    hypothesis: str
    drivers: List[str]  # Min 1
    disconfirmers: List[str]  # Min 1
    expression: List[ThesisExpressionLeg]  # Min 1
    start_date: str
    review_date: Optional[str]
    status: ThesisStatus
    tags: List[str]
    monitor_indices: List[str]
    notes: Optional[str] = None
    risk_rails: Optional[RiskRails] = None  # V3
    final_size: Optional[float] = None  # V3

class ThesisExpressionLeg(BaseModel):
    asset: str
    direction: Direction  # LONG or SHORT
    size_pct: float

class RiskRails(BaseModel):
    max_dd_tolerance: float
    position_cap: float
    stop_loss: Optional[float] = None
    time_horizon: Optional[str] = None
```

### V3 Models (`src/voyager/models/v3.py`)

```python
# QueryTranslator outputs
class CausalLink(BaseModel):
    claim: str
    concept_a: str
    concept_b: str
    direction: str  # "positive" or "negative"

class ResolvedLink(BaseModel):
    claim: str
    series_a: str
    series_b: str
    query_type: str
    direction: str

class Ambiguity(BaseModel):
    concept: str
    candidates: List[dict]

# Validation
class ValidationResult(BaseModel):
    status: str  # "complete" | "needs_clarification" | "parse_failed"
    links: Optional[List[LogicLink]] = None
    ambiguities: Optional[List[Ambiguity]] = None
    error_message: Optional[str] = None

# Critique
class Concern(BaseModel):
    dimension: str
    severity: str  # "high" | "medium" | "low"
    summary: str

class CritiqueSummary(BaseModel):
    concerns: List[Concern]
    opening_message: str

class CritiqueResponse(BaseModel):
    message: str
    thesis_edit_suggestion: Optional[dict] = None

# Backtest
class BacktestMetrics(BaseModel):
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float

class BacktestResult(BaseModel):
    id: str
    thesis_id: str
    expression: dict
    period_start: str
    period_end: str
    metrics: BacktestMetrics
    equity_curve: List[EquityPoint]
    factor_exposure: Optional[FactorExposureResult] = None
    iteration_count: int

# Sizing
class SizingResult(BaseModel):
    historical_max_dd: float
    tolerance: float
    implied_size: float
    position_cap: float
    suggested_size: float
    portfolio_impact: Optional[PortfolioImpact] = None

class PortfolioImpact(BaseModel):
    correlation_to_book: float
    marginal_vol: float
```

### Enums (`src/voyager/models/common.py`)

```python
class ThesisStatus(str, Enum):
    WATCHLIST = "WATCHLIST"
    VALIDATED = "VALIDATED"
    CRITIQUED = "CRITIQUED"
    BACKTESTED = "BACKTESTED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
```

---

## SeriesRegistry

**Location:** `src/voyager/data/series_registry.json`

**Purpose:** Maps natural language concepts to concrete data series

**Structure:**
```json
{
  "series": [
    {
      "id": "DFII10",
      "source": "FRED",
      "name": "10-Year Treasury Inflation-Indexed Security",
      "category": "rates",
      "aliases": ["real yields", "10y real", "tips yield", "real rates"],
      "frequency": "daily"
    }
  ]
}
```

**Categories:**
- `rates` — FEDFUNDS, DGS10, DGS2, DFII10, T10YIE, TLT, IEF, TIP
- `commodity` — GLD, SLV, USO, DBC
- `fx` — UUP, FXE, FXY
- `equity` — SPY, QQQ, IWM, EFA, EEM
- `volatility` — VIXY (not VIX — using ETF for TwelveData compatibility)

**Key Method:**
```python
SeriesRegistry.search_by_concept(concept: str) -> List[dict]
# Returns matching series with scores
# Used by QueryTranslator for deterministic resolution
```

---

## Dependency Injection

**Location:** `src/voyager/api/deps.py`

**Pattern:** Singleton factories with module-level caching

```python
_validation_service_instance: Optional[ValidationService] = None

def get_validation_service_instance() -> ValidationService:
    global _validation_service_instance
    if _validation_service_instance is None:
        _validation_service_instance = ValidationService(
            query_translator=get_query_translator_instance(),
            quant_service=get_quant_service_instance(),
            validation_repo=LogicValidationRepository(get_engine()),
            thesis_repo=get_data_access_instance().thesis_repo
        )
    return _validation_service_instance
```

**Available Factories:**
- `get_engine()` — SQLAlchemy engine
- `get_data_access_instance()` — DataAccess with all core repos
- `get_series_registry_instance()` — SeriesRegistry singleton
- `get_quant_service_instance()` — QuantService
- `get_backtest_engine_instance()` — BacktestEngine
- `get_backtest_service_instance()` — BacktestService
- `get_query_translator_instance()` — QueryTranslator
- `get_critique_engine_instance()` — CritiqueEngine
- `get_validation_service_instance()` — ValidationService
- `get_critique_service_instance()` — CritiqueService
- `get_sizing_service_instance()` — SizingService
- `get_thesis_service_instance()` — ThesisService

---

## CLI Tools

**Location:** `scripts/cli/`

| Tool | Purpose | Example |
|------|---------|---------|
| `quant_cli.py` | Test QuantService | `python scripts/cli/quant_cli.py correlation DFII10 GLD --period 5Y` |
| `backtest_cli.py` | Test BacktestEngine | `python scripts/cli/backtest_cli.py run '{"GLD": 0.7, "TIP": 0.3}'` |
| `llm_cli.py` | Test LLM layer | `python scripts/cli/llm_cli.py validate <thesis_id>` |
| `sizing_cli.py` | Test SizingService | `python scripts/cli/sizing_cli.py compute <thesis_id> --max-dd 0.08` |

---

## Data Backfill

**Script:** `scripts/backfill_data.py`

**Sources:**
- TwelveData API — ETFs and FX
- FRED API — Macro series
- yfinance fallback — When TwelveData fails

**Features:**
- Retry logic with exponential backoff
- Connection pooling via requests.Session
- 30-second timeout
- 1.5-second delay between requests (rate limiting)

**Series Loaded:**
- 21 ETFs (equity, rates, commodities, FX, volatility)
- 9 FRED series (rates, inflation, employment, GDP)

---

## Test Structure

**Location:** `tests/v3/`

| File | Tests | Coverage |
|------|-------|----------|
| `test_quant_service.py` | ~10 | QuantService methods |
| `test_backtest_engine.py` | 11 | BacktestEngine, expression conversion |
| `test_query_translator.py` | 6 | Link extraction, resolution |
| `test_critique_engine.py` | 8 | Critique, drill-down |
| `test_validation_service.py` | 7 | Full validation flow |
| `test_integration.py` | 2 | End-to-end workflows |
| `test_sizing_service.py` | 15 | Sizing, portfolio impact |
| `test_thesis_service.py` | 14 | CRUD, transitions, activation |
| `test_api_routes.py` | 30+ | All API endpoints |

**Total:** 100+ tests

**Test Patterns:**
- Mock LLM client with `AsyncMock` for async services
- Real QuantService with test database for integration tests
- `TestClient` for API route testing

---

## Error Handling Patterns

**Validation Errors:**
```python
if thesis is None:
    raise ValueError(f"Thesis not found: {thesis_id}")
```

**LLM Failures (Graceful Degradation):**
```python
try:
    result = await self._llm.chat(messages)
except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("LLM error: %s", e, exc_info=True)
    return CritiqueSummary(concerns=[], opening_message="Error analyzing thesis.")
```

**API Layer:**
```python
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e)) from e
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e)) from e
```

---

## Code Quality Standards

**Pylint Target:** 9.0+/10 for all files

**Common Fixes Applied:**
- Trailing whitespace removal
- Line length ≤ 100 characters
- `input` parameter renamed to avoid builtin shadowing
- Lazy logging: `logger.error("Error: %s", e)` not f-strings
- `from e` on exception re-raises
- Import order: stdlib → third-party → local

**Acceptable Disables:**
- `# pylint: disable=broad-exception-caught` — LLM error handling
- `# pylint: disable=too-many-arguments` — Service constructors
- `# pylint: disable=too-many-positional-arguments` — Complex methods

---

## Known Limitations

1. **No retry logic on LLM calls** — Single attempt with 30s timeout
2. **No LLM response caching** — Repeated requests hit API
3. **Equity curve precision loss** — Sampled to 500 points
4. **Portfolio impact requires trades** — Returns None if no positions
5. **Single-threaded backtests** — No parallel execution
6. **Simple correlation interpretation** — Thresholds at 0.3/0.6

---

## File Structure

```
src/voyager/
├── api/
│   ├── main.py              # FastAPI app
│   ├── deps.py              # Dependency injection
│   └── v3_routes.py         # V3 API endpoints
├── data/
│   ├── series_registry.json # Concept-to-series mapping
│   └── series_registry.py   # SeriesRegistry class
├── llm/
│   ├── query_translator.py  # Causal link extraction
│   ├── critique_engine.py   # Six-dimension critique
│   └── tools.py             # extract_json utility
├── models/
│   ├── common.py            # Enums (ThesisStatus, Direction)
│   ├── thesis.py            # Core models (Thesis, RiskRails)
│   └── v3.py                # V3 models (ValidationResult, etc.)
├── quant/
│   ├── quant_service.py     # Correlation, distribution
│   └── backtest_engine.py   # VectorBT wrapper
├── repositories/
│   ├── thesis_repo.py       # Thesis CRUD
│   ├── logic_validation_repository.py
│   ├── thesis_snapshot_repository.py
│   └── backtest_result_repository.py
└── services/v3/
    ├── validation_service.py
    ├── critique_service.py
    ├── backtest_service.py
    ├── sizing_service.py
    └── thesis_service.py

scripts/
├── backfill_data.py         # Data loading
└── cli/
    ├── quant_cli.py
    ├── backtest_cli.py
    ├── llm_cli.py
    └── sizing_cli.py

sql/
├── voyager_schema.sql       # Core tables
└── v3_schema.sql            # V3 tables

tests/v3/
├── test_quant_service.py
├── test_backtest_engine.py
├── test_query_translator.py
├── test_critique_engine.py
├── test_validation_service.py
├── test_integration.py
├── test_sizing_service.py
├── test_thesis_service.py
└── test_api_routes.py
```

---

## Phase Summary

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| 0 | Foundation | Schema, models, SeriesRegistry, repositories |
| 1 | Quant Service | correlation(), distribution(), relationship_strength() |
| 2 | Backtest Engine | VectorBT integration, factor exposure, BacktestService |
| 3 | LLM Layer | QueryTranslator, CritiqueEngine, ValidationService, CritiqueService |
| 4 | Sizing & Lifecycle | SizingService, ThesisService, status transitions |
| 5 | API Layer | 17 REST endpoints, full workflow support |
| 6 | UI Layer | Pending — four-screen Streamlit or React app |

---

## For AI Assistants

When working on Voyager V3:

1. **Check existing patterns** — Look at how similar problems were solved in prior phases
2. **Use dependency injection** — Don't instantiate services directly; use factories
3. **Match error handling** — ValueError for validation, graceful degradation for LLM
4. **Maintain pylint standards** — Target 9.0+, fix trailing whitespace
5. **Write tests** — Unit tests with mocks, integration tests with real DB
6. **Document bugs** — The completion guides show issues encountered and solutions

**Key Files to Reference:**
- `src/voyager/api/deps.py` — How services are wired
- `src/voyager/models/v3.py` — All V3 data structures
- `src/voyager/services/v3/` — Service patterns
- `tests/v3/` — Test patterns and fixtures

---

## Appendix: Complete API Reference

### Create Thesis
```bash
POST /api/v3/thesis
Content-Type: application/json

{
  "title": "Gold Real Yields Thesis",
  "hypothesis": "When real yields fall, gold rises as opportunity cost decreases",
  "drivers": ["falling real yields", "Fed dovish pivot"],
  "disconfirmers": ["rising real yields", "strong USD"],
  "expression": [
    {"asset": "GLD", "direction": "LONG", "size_pct": 70},
    {"asset": "TIP", "direction": "SHORT", "size_pct": 30}
  ]
}

Response: {"thesis": {...}, "status": "created"}
```

### Run Validation
```bash
POST /api/v3/thesis/{id}/validate

Response (complete):
{
  "status": "complete",
  "links": [
    {
      "claim": "falling real yields cause gold to rise",
      "series_a": "DFII10",
      "series_b": "GLD",
      "result": -0.62,
      "interpretation": "supports"
    }
  ]
}

Response (needs clarification):
{
  "status": "needs_clarification",
  "ambiguities": [
    {
      "concept": "rates",
      "candidates": [
        {"id": "FEDFUNDS", "name": "Federal Funds Rate"},
        {"id": "DGS10", "name": "10-Year Treasury"}
      ]
    }
  ]
}
```

### Start Critique
```bash
POST /api/v3/thesis/{id}/critique/start

Response:
{
  "concerns": [
    {
      "dimension": "causal_mechanism",
      "severity": "medium",
      "summary": "The transmission mechanism from real yields to gold is not fully specified"
    }
  ],
  "opening_message": "I have some questions about the causal mechanism..."
}
```

### Run Backtest
```bash
POST /api/v3/thesis/{id}/backtest?start_date=2020-01-01

Response:
{
  "id": "bt_abc123",
  "thesis_id": "thesis_xyz",
  "metrics": {
    "total_return": 0.45,
    "cagr": 0.12,
    "volatility": 0.15,
    "sharpe": 0.80,
    "max_drawdown": 0.18
  },
  "equity_curve": [...],
  "factor_exposure": {
    "betas": {"commodities": 0.7, "rates_level": -0.3, ...},
    "r_squared": 0.85
  },
  "iteration_count": 3
}
```

### Compute Sizing
```bash
POST /api/v3/thesis/{id}/sizing
Content-Type: application/json

{
  "max_dd_tolerance": 0.08,
  "position_cap": 0.10
}

Response:
{
  "historical_max_dd": 0.18,
  "tolerance": 0.08,
  "implied_size": 0.44,
  "position_cap": 0.10,
  "suggested_size": 0.10,
  "portfolio_impact": {
    "correlation_to_book": 0.35,
    "marginal_vol": 0.02
  }
}
```

### Activate Thesis
```bash
POST /api/v3/thesis/{id}/activate-with-rails
Content-Type: application/json

{
  "final_size": 0.08,
  "max_dd_tolerance": 0.08,
  "position_cap": 0.10
}

Response: {"thesis": {..., "status": "ACTIVE"}, "status": "activated"}
```

---

*End of V3 Architecture Summary*