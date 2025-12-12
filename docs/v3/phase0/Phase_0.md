# V3 Phase 0: Foundation

## Overview

This phase establishes the foundational data layer for V3 thesis creation. No business logic yet — just schema, models, and the series registry.

## Prerequisites

- Existing Voyager codebase with PostgreSQL + pgvector
- Existing `phase4_schema.sql` with `thesis` table

---

## Task 1: Schema Migration

**File:** `sql/v3_schema.sql`

Add new columns to `thesis` table and create new tables.

```sql
-- ===========================================
-- V3 Schema Migration
-- ===========================================

-- 1. Extend thesis table
ALTER TABLE thesis ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'DRAFT';
ALTER TABLE thesis ADD COLUMN IF NOT EXISTS risk_rails JSONB;
ALTER TABLE thesis ADD COLUMN IF NOT EXISTS final_size FLOAT;

-- 2. Create thesis_snapshot table
CREATE TABLE IF NOT EXISTS thesis_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID NOT NULL REFERENCES thesis(id),
    snapshot_type VARCHAR(20) NOT NULL,  -- pre_critique | post_critique | activation
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thesis_snapshot_thesis ON thesis_snapshot(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_snapshot_type ON thesis_snapshot(thesis_id, snapshot_type);

-- 3. Create logic_validation table
CREATE TABLE IF NOT EXISTS logic_validation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID NOT NULL REFERENCES thesis(id),
    links JSONB NOT NULL,  -- Array of LogicLink objects
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logic_validation_thesis ON logic_validation(thesis_id);

-- 4. Create backtest_result table
CREATE TABLE IF NOT EXISTS backtest_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID NOT NULL REFERENCES thesis(id),
    expression JSONB NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    metrics JSONB NOT NULL,
    equity_curve JSONB NOT NULL,
    factor_exposure JSONB,
    iteration_count INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_result_thesis ON backtest_result(thesis_id);
CREATE INDEX IF NOT EXISTS idx_backtest_result_created ON backtest_result(thesis_id, created_at DESC);

-- 5. Create critique_session table (for conversation history)
CREATE TABLE IF NOT EXISTS critique_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID NOT NULL REFERENCES thesis(id),
    conversation JSONB NOT NULL,  -- Array of {role, content, timestamp}
    status VARCHAR(20) DEFAULT 'active',  -- active | completed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_critique_session_thesis ON critique_session(thesis_id);
```

---

## Task 2: Extended Pydantic Models

**File:** `src/voyager/models/thesis.py`

Extend the existing `Thesis` model. Add new classes.

```python
# Add these imports at top
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

# Add new enum for V3 status
class ThesisStatusV3(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    CRITIQUED = "CRITIQUED"
    BACKTESTED = "BACKTESTED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

# Add RiskRails model
class RiskRails(BaseModel):
    max_dd_tolerance: float = Field(ge=0, le=1, description="e.g., 0.08 = 8%")
    position_cap: float = Field(ge=0, le=1, description="e.g., 0.10 = 10%")
    stop_loss: Optional[float] = Field(default=None, ge=0, le=1)
    time_horizon: Optional[str] = Field(default=None, description="ISO date string")

# Extend Thesis model - add these fields
# NOTE: If modifying existing Thesis class, add these fields:
#   status: ThesisStatusV3 = ThesisStatusV3.DRAFT
#   risk_rails: Optional[RiskRails] = None
#   final_size: Optional[float] = None

# Add ThesisSnapshot model
class ThesisSnapshot(BaseModel):
    id: str
    thesis_id: str
    snapshot_type: str  # "pre_critique" | "post_critique" | "activation"
    content: dict  # Full thesis state at snapshot time
    created_at: str  # ISO datetime

# Add LogicLink model
class LogicLink(BaseModel):
    claim: str  # "Fed hikes → real yields up"
    series_a: str  # "FEDFUNDS"
    series_b: str  # "DFII10"
    query_type: str  # "correlation" | "conditional_returns"
    result: float  # The computed value
    interpretation: str  # "supports" | "weak" | "contradicts"

# Add LogicValidation model
class LogicValidation(BaseModel):
    id: str
    thesis_id: str
    links: List[LogicLink]
    created_at: str  # ISO datetime
```

---

## Task 3: V3-Specific Models

**File:** `src/voyager/models/v3.py` (NEW FILE)

```python
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
```

---

## Task 4: Series Registry

**File:** `src/voyager/data/series_registry.json` (NEW FILE)

```json
{
  "series": [
    {
      "id": "FEDFUNDS",
      "source": "FRED",
      "name": "Federal Funds Effective Rate",
      "category": "rates",
      "aliases": ["fed funds", "fed rate", "federal funds", "fed hikes", "fed policy"],
      "frequency": "daily"
    },
    {
      "id": "DGS10",
      "source": "FRED",
      "name": "10-Year Treasury Constant Maturity Rate",
      "category": "rates",
      "aliases": ["10y yield", "10 year", "treasury yield", "10y treasury", "long rates"],
      "frequency": "daily"
    },
    {
      "id": "DGS2",
      "source": "FRED",
      "name": "2-Year Treasury Constant Maturity Rate",
      "category": "rates",
      "aliases": ["2y yield", "2 year", "short rates", "2y treasury"],
      "frequency": "daily"
    },
    {
      "id": "DFII10",
      "source": "FRED",
      "name": "10-Year Treasury Inflation-Indexed Security",
      "category": "rates",
      "aliases": ["real yields", "10y real", "tips yield", "real yield", "real rates"],
      "frequency": "daily"
    },
    {
      "id": "T10YIE",
      "source": "FRED",
      "name": "10-Year Breakeven Inflation Rate",
      "category": "rates",
      "aliases": ["breakeven", "inflation expectations", "10y breakeven"],
      "frequency": "daily"
    },
    {
      "id": "GLD",
      "source": "TwelveData",
      "name": "SPDR Gold Shares",
      "category": "commodity",
      "aliases": ["gold", "gold etf", "xau"],
      "frequency": "daily"
    },
    {
      "id": "SLV",
      "source": "TwelveData",
      "name": "iShares Silver Trust",
      "category": "commodity",
      "aliases": ["silver", "silver etf"],
      "frequency": "daily"
    },
    {
      "id": "USO",
      "source": "TwelveData",
      "name": "United States Oil Fund",
      "category": "commodity",
      "aliases": ["oil", "crude", "wti", "oil etf"],
      "frequency": "daily"
    },
    {
      "id": "DBC",
      "source": "TwelveData",
      "name": "Invesco DB Commodity Index",
      "category": "commodity",
      "aliases": ["commodities", "commodity index", "broad commodities"],
      "frequency": "daily"
    },
    {
      "id": "UUP",
      "source": "TwelveData",
      "name": "Invesco DB US Dollar Index Bullish Fund",
      "category": "fx",
      "aliases": ["dollar", "usd", "dxy", "dollar index", "greenback"],
      "frequency": "daily"
    },
    {
      "id": "FXE",
      "source": "TwelveData",
      "name": "Invesco CurrencyShares Euro Trust",
      "category": "fx",
      "aliases": ["euro", "eur", "eurusd"],
      "frequency": "daily"
    },
    {
      "id": "FXY",
      "source": "TwelveData",
      "name": "Invesco CurrencyShares Japanese Yen Trust",
      "category": "fx",
      "aliases": ["yen", "jpy", "usdjpy"],
      "frequency": "daily"
    },
    {
      "id": "SPY",
      "source": "TwelveData",
      "name": "SPDR S&P 500 ETF",
      "category": "equity",
      "aliases": ["s&p", "sp500", "stocks", "equities", "us stocks", "s&p 500"],
      "frequency": "daily"
    },
    {
      "id": "QQQ",
      "source": "TwelveData",
      "name": "Invesco QQQ Trust",
      "category": "equity",
      "aliases": ["nasdaq", "tech", "tech stocks", "qqq"],
      "frequency": "daily"
    },
    {
      "id": "IWM",
      "source": "TwelveData",
      "name": "iShares Russell 2000 ETF",
      "category": "equity",
      "aliases": ["small caps", "russell", "russell 2000"],
      "frequency": "daily"
    },
    {
      "id": "EFA",
      "source": "TwelveData",
      "name": "iShares MSCI EAFE ETF",
      "category": "equity",
      "aliases": ["international", "developed markets", "eafe", "ex-us"],
      "frequency": "daily"
    },
    {
      "id": "EEM",
      "source": "TwelveData",
      "name": "iShares MSCI Emerging Markets ETF",
      "category": "equity",
      "aliases": ["emerging markets", "em", "emerging"],
      "frequency": "daily"
    },
    {
      "id": "TLT",
      "source": "TwelveData",
      "name": "iShares 20+ Year Treasury Bond ETF",
      "category": "rates",
      "aliases": ["long bonds", "treasury bonds", "long duration", "tlt"],
      "frequency": "daily"
    },
    {
      "id": "IEF",
      "source": "TwelveData",
      "name": "iShares 7-10 Year Treasury Bond ETF",
      "category": "rates",
      "aliases": ["intermediate bonds", "7-10 year", "ief"],
      "frequency": "daily"
    },
    {
      "id": "TIP",
      "source": "TwelveData",
      "name": "iShares TIPS Bond ETF",
      "category": "rates",
      "aliases": ["tips", "inflation protected", "tips etf"],
      "frequency": "daily"
    },
    {
      "id": "VIX",
      "source": "TwelveData",
      "name": "CBOE Volatility Index",
      "category": "volatility",
      "aliases": ["vix", "volatility", "fear index", "vol"],
      "frequency": "daily"
    }
  ]
}
```

**File:** `src/voyager/data/series_registry.py` (NEW FILE)

```python
"""
Series Registry for V3 thesis validation.

Maps concepts (e.g., "real yields") to concrete data series (e.g., "DFII10").
"""
from dataclasses import dataclass
from typing import Optional, List
import json
from pathlib import Path


@dataclass
class SeriesEntry:
    """A single series in the registry"""
    id: str
    source: str  # "FRED" | "TwelveData"
    name: str
    category: str  # "rates" | "fx" | "commodity" | "equity" | "volatility"
    aliases: List[str]
    frequency: str  # "daily" | "weekly" | "monthly"


class SeriesRegistry:
    """
    Registry of available data series with concept-to-series mapping.
    
    Usage:
        registry = SeriesRegistry()
        candidates = registry.search_by_concept("real yields")
        # Returns [SeriesEntry(id="DFII10", ...)]
    """
    
    def __init__(self, path: Path = None):
        """Load registry from JSON file"""
        if path is None:
            path = Path(__file__).parent / "series_registry.json"
        
        with open(path) as f:
            data = json.load(f)
        
        self._entries: dict[str, SeriesEntry] = {}
        for s in data["series"]:
            self._entries[s["id"]] = SeriesEntry(
                id=s["id"],
                source=s["source"],
                name=s["name"],
                category=s["category"],
                aliases=s["aliases"],
                frequency=s["frequency"]
            )
        
        self._alias_index = self._build_alias_index()
    
    def _build_alias_index(self) -> dict[str, List[str]]:
        """Build index mapping lowercase aliases to series IDs"""
        index: dict[str, List[str]] = {}
        for series_id, entry in self._entries.items():
            for alias in entry.aliases:
                key = alias.lower()
                if key not in index:
                    index[key] = []
                index[key].append(series_id)
            # Also index the series ID itself
            index[series_id.lower()] = [series_id]
        return index
    
    def search_by_concept(self, concept: str) -> List[SeriesEntry]:
        """
        Find series matching a concept.
        
        Args:
            concept: Natural language concept (e.g., "real yields", "gold")
            
        Returns:
            List of matching SeriesEntry objects. Empty if no match.
        """
        concept_lower = concept.lower().strip()
        
        # Exact match first
        if concept_lower in self._alias_index:
            return [self._entries[sid] for sid in self._alias_index[concept_lower]]
        
        # Partial match fallback
        matches = set()
        for alias, series_ids in self._alias_index.items():
            # Check if concept contains alias or alias contains concept
            if concept_lower in alias or alias in concept_lower:
                matches.update(series_ids)
        
        return [self._entries[sid] for sid in matches]
    
    def get_by_id(self, series_id: str) -> Optional[SeriesEntry]:
        """Get series by exact ID"""
        return self._entries.get(series_id)
    
    def list_by_category(self, category: str) -> List[SeriesEntry]:
        """List all series in a category"""
        return [e for e in self._entries.values() if e.category == category]
    
    def list_all(self) -> List[SeriesEntry]:
        """List all series"""
        return list(self._entries.values())
    
    def list_categories(self) -> List[str]:
        """List all unique categories"""
        return list(set(e.category for e in self._entries.values()))
```

---

## Task 5: New Repositories

**File:** `src/voyager/repositories/thesis_snapshot_repository.py` (NEW FILE)

```python
"""
Repository for thesis snapshots.
"""
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
import json
from datetime import datetime
import uuid

from voyager.models.thesis import ThesisSnapshot


class ThesisSnapshotRepository:
    """CRUD operations for thesis snapshots"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
    
    def insert(self, snapshot: ThesisSnapshot) -> ThesisSnapshot:
        """Insert a new snapshot"""
        query = text("""
            INSERT INTO thesis_snapshot (id, thesis_id, snapshot_type, content, created_at)
            VALUES (:id, :thesis_id, :snapshot_type, :content, :created_at)
            RETURNING id, thesis_id, snapshot_type, content, created_at
        """)
        
        snapshot_id = snapshot.id or f"snap_{uuid.uuid4().hex[:12]}"
        created_at = snapshot.created_at or datetime.utcnow().isoformat()
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {
                "id": snapshot_id,
                "thesis_id": snapshot.thesis_id,
                "snapshot_type": snapshot.snapshot_type,
                "content": json.dumps(snapshot.content),
                "created_at": created_at
            })
            conn.commit()
            row = result.fetchone()
        
        return self._row_to_model(row)
    
    def get_by_id(self, snapshot_id: str) -> Optional[ThesisSnapshot]:
        """Get snapshot by ID"""
        query = text("""
            SELECT id, thesis_id, snapshot_type, content, created_at
            FROM thesis_snapshot
            WHERE id = :id
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"id": snapshot_id})
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def list_by_thesis(self, thesis_id: str) -> List[ThesisSnapshot]:
        """List all snapshots for a thesis"""
        query = text("""
            SELECT id, thesis_id, snapshot_type, content, created_at
            FROM thesis_snapshot
            WHERE thesis_id = :thesis_id
            ORDER BY created_at ASC
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            rows = result.fetchall()
        
        return [self._row_to_model(row) for row in rows]
    
    def get_latest_by_type(self, thesis_id: str, snapshot_type: str) -> Optional[ThesisSnapshot]:
        """Get most recent snapshot of a specific type"""
        query = text("""
            SELECT id, thesis_id, snapshot_type, content, created_at
            FROM thesis_snapshot
            WHERE thesis_id = :thesis_id AND snapshot_type = :snapshot_type
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {
                "thesis_id": thesis_id,
                "snapshot_type": snapshot_type
            })
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def _row_to_model(self, row) -> ThesisSnapshot:
        """Convert DB row to model"""
        return ThesisSnapshot(
            id=str(row.id),
            thesis_id=str(row.thesis_id),
            snapshot_type=row.snapshot_type,
            content=row.content if isinstance(row.content, dict) else json.loads(row.content),
            created_at=row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at)
        )
```

**File:** `src/voyager/repositories/logic_validation_repository.py` (NEW FILE)

```python
"""
Repository for logic validation results.
"""
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
import json
from datetime import datetime
import uuid

from voyager.models.thesis import LogicValidation, LogicLink


class LogicValidationRepository:
    """CRUD operations for logic validations"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
    
    def insert(self, validation: LogicValidation) -> LogicValidation:
        """Insert a new validation"""
        query = text("""
            INSERT INTO logic_validation (id, thesis_id, links, created_at)
            VALUES (:id, :thesis_id, :links, :created_at)
            RETURNING id, thesis_id, links, created_at
        """)
        
        validation_id = validation.id or f"val_{uuid.uuid4().hex[:12]}"
        created_at = validation.created_at or datetime.utcnow().isoformat()
        
        # Serialize links
        links_json = [link.dict() for link in validation.links]
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {
                "id": validation_id,
                "thesis_id": validation.thesis_id,
                "links": json.dumps(links_json),
                "created_at": created_at
            })
            conn.commit()
            row = result.fetchone()
        
        return self._row_to_model(row)
    
    def get_by_thesis(self, thesis_id: str) -> Optional[LogicValidation]:
        """Get most recent validation for a thesis"""
        query = text("""
            SELECT id, thesis_id, links, created_at
            FROM logic_validation
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def list_by_thesis(self, thesis_id: str) -> List[LogicValidation]:
        """List all validations for a thesis"""
        query = text("""
            SELECT id, thesis_id, links, created_at
            FROM logic_validation
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            rows = result.fetchall()
        
        return [self._row_to_model(row) for row in rows]
    
    def _row_to_model(self, row) -> LogicValidation:
        """Convert DB row to model"""
        links_data = row.links if isinstance(row.links, list) else json.loads(row.links)
        links = [LogicLink(**link) for link in links_data]
        
        return LogicValidation(
            id=str(row.id),
            thesis_id=str(row.thesis_id),
            links=links,
            created_at=row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at)
        )
```

**File:** `src/voyager/repositories/backtest_result_repository.py` (NEW FILE)

```python
"""
Repository for backtest results.
"""
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
import json
from datetime import datetime
import uuid

from voyager.models.v3 import BacktestResult, BacktestMetrics, EquityPoint, FactorExposureResult


class BacktestResultRepository:
    """CRUD operations for backtest results"""
    
    def __init__(self, engine: Engine):
        self._engine = engine
    
    def insert(self, result: BacktestResult) -> BacktestResult:
        """Insert a new backtest result"""
        query = text("""
            INSERT INTO backtest_result 
            (id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at)
            VALUES (:id, :thesis_id, :expression, :period_start, :period_end, :metrics, :equity_curve, :factor_exposure, :iteration_count, :created_at)
            RETURNING id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at
        """)
        
        result_id = result.id or f"bt_{uuid.uuid4().hex[:12]}"
        created_at = result.created_at or datetime.utcnow().isoformat()
        
        with self._engine.connect() as conn:
            db_result = conn.execute(query, {
                "id": result_id,
                "thesis_id": result.thesis_id,
                "expression": json.dumps(result.expression),
                "period_start": result.period_start,
                "period_end": result.period_end,
                "metrics": json.dumps(result.metrics.dict()),
                "equity_curve": json.dumps([ep.dict() for ep in result.equity_curve]),
                "factor_exposure": json.dumps(result.factor_exposure.dict()) if result.factor_exposure else None,
                "iteration_count": result.iteration_count,
                "created_at": created_at
            })
            conn.commit()
            row = db_result.fetchone()
        
        return self._row_to_model(row)
    
    def get_latest_by_thesis(self, thesis_id: str) -> Optional[BacktestResult]:
        """Get most recent backtest for a thesis"""
        query = text("""
            SELECT id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at
            FROM backtest_result
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            row = result.fetchone()
        
        return self._row_to_model(row) if row else None
    
    def count_by_thesis(self, thesis_id: str) -> int:
        """Count backtest iterations for a thesis"""
        query = text("""
            SELECT COUNT(*) FROM backtest_result WHERE thesis_id = :thesis_id
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            return result.scalar() or 0
    
    def list_by_thesis(self, thesis_id: str) -> List[BacktestResult]:
        """List all backtests for a thesis"""
        query = text("""
            SELECT id, thesis_id, expression, period_start, period_end, metrics, equity_curve, factor_exposure, iteration_count, created_at
            FROM backtest_result
            WHERE thesis_id = :thesis_id
            ORDER BY created_at DESC
        """)
        
        with self._engine.connect() as conn:
            result = conn.execute(query, {"thesis_id": thesis_id})
            rows = result.fetchall()
        
        return [self._row_to_model(row) for row in rows]
    
    def _row_to_model(self, row) -> BacktestResult:
        """Convert DB row to model"""
        metrics_data = row.metrics if isinstance(row.metrics, dict) else json.loads(row.metrics)
        equity_data = row.equity_curve if isinstance(row.equity_curve, list) else json.loads(row.equity_curve)
        factor_data = None
        if row.factor_exposure:
            factor_data = row.factor_exposure if isinstance(row.factor_exposure, dict) else json.loads(row.factor_exposure)
        
        return BacktestResult(
            id=str(row.id),
            thesis_id=str(row.thesis_id),
            expression=row.expression if isinstance(row.expression, dict) else json.loads(row.expression),
            period_start=str(row.period_start),
            period_end=str(row.period_end),
            metrics=BacktestMetrics(**metrics_data),
            equity_curve=[EquityPoint(**ep) for ep in equity_data],
            factor_exposure=FactorExposureResult(**factor_data) if factor_data else None,
            iteration_count=row.iteration_count,
            created_at=row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at)
        )
```

---

## Task 6: Extend ThesisRepository

**File:** `src/voyager/repositories/thesis_repository.py`

Add these methods to the existing `ThesisRepository` class:

```python
# Add these methods to existing ThesisRepository class

def update_status(self, thesis_id: str, status: str) -> Optional["Thesis"]:
    """Update thesis status"""
    query = text("""
        UPDATE thesis 
        SET status = :status
        WHERE id = :thesis_id
        RETURNING *
    """)
    
    with self._engine.connect() as conn:
        result = conn.execute(query, {"thesis_id": thesis_id, "status": status})
        conn.commit()
        row = result.fetchone()
    
    return self._row_to_model(row) if row else None

def update_risk_rails(self, thesis_id: str, risk_rails: dict) -> Optional["Thesis"]:
    """Update thesis risk rails"""
    query = text("""
        UPDATE thesis 
        SET risk_rails = :risk_rails
        WHERE id = :thesis_id
        RETURNING *
    """)
    
    with self._engine.connect() as conn:
        result = conn.execute(query, {
            "thesis_id": thesis_id, 
            "risk_rails": json.dumps(risk_rails)
        })
        conn.commit()
        row = result.fetchone()
    
    return self._row_to_model(row) if row else None

def update_final_size(self, thesis_id: str, final_size: float) -> Optional["Thesis"]:
    """Update thesis final size"""
    query = text("""
        UPDATE thesis 
        SET final_size = :final_size
        WHERE id = :thesis_id
        RETURNING *
    """)
    
    with self._engine.connect() as conn:
        result = conn.execute(query, {"thesis_id": thesis_id, "final_size": final_size})
        conn.commit()
        row = result.fetchone()
    
    return self._row_to_model(row) if row else None

def list_by_status(self, status: str) -> List["Thesis"]:
    """List theses by status"""
    query = text("""
        SELECT * FROM thesis WHERE status = :status ORDER BY start_date DESC
    """)
    
    with self._engine.connect() as conn:
        result = conn.execute(query, {"status": status})
        rows = result.fetchall()
    
    return [self._row_to_model(row) for row in rows]
```

---

## Verification

After completing this phase:

1. Run schema migration against database
2. Verify new tables exist: `thesis_snapshot`, `logic_validation`, `backtest_result`, `critique_session`
3. Verify `thesis` table has new columns: `status`, `risk_rails`, `final_size`
4. Test `SeriesRegistry`:
   ```python
   from voyager.data.series_registry import SeriesRegistry
   registry = SeriesRegistry()
   assert len(registry.search_by_concept("gold")) > 0
   assert registry.get_by_id("GLD") is not None
   ```
5. Test new repositories with basic insert/get operations

---

## Dependencies

No new external dependencies. Uses existing:
- `sqlalchemy`
- `pydantic`
- `psycopg2` (or `asyncpg`)

---

## Next Phase

Phase 1: Quant Service — implements `QuantService` with `correlation()`, `conditional_returns()`, `distribution()` methods.