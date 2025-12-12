Here is a complete replacement for slice_phase1_master_spec.md, in Markdown, clean and ready to paste into VSCode.

# Slice Phase 1 Master Specification

This document is the canonical specification for Phase 1 of Slice.

It defines:

- System purpose and philosophy  
- User requirements  
- Thesis and Observation schemas  
- Autonomy engine behavior and timing  
- Data model overview  
- Module architecture  
- LLM contract definitions  
- Safety constraints  
- Phase 2–3 roadmap  

Phase 1 is **architecture and specification only**. No implementation details in this document may be overridden in later phases without explicit revision.

-------------------------------------------------------------------------------
## 1. Executive Summary
-------------------------------------------------------------------------------

Slice is a long-horizon discretionary macro “operating system” for a single investor.

It formalizes how investment theses are created, expressed in a portfolio, monitored over time, and partially automated via rule-based execution. Slice is **not** a trading bot, price forecaster, or narrative generator. It is a disciplined framework that:

- Structures theses into strict, machine-readable objects (ThesisJSON).  
- Records observations in a parallel structured format (ObservationJSON).  
- Evaluates the thesis against market and macro data.  
- Enforces pre-defined autonomy rules (bands, stops, profit-taking, timed actions).  
- Produces a daily Morning Briefing.  

All autonomy is **deterministic** and derived from explicit rules inside ThesisJSON. The system operates on a **daily rhythm**:

- Evaluate using end-of-day (EOD) data.  
- Act (execute trades) during the next session’s market hours, typically near the open.  

Human judgment remains central. Slice supports thinking and discipline; it does not replace discretionary macro decision-making.

-------------------------------------------------------------------------------
## 2. System Philosophy and Principles
-------------------------------------------------------------------------------

1. **Human-in-the-loop macro**  
   Slice assists, but does not supplant, the investor’s judgment. Theses and rules are defined by the human. The system enforces consistency and memory.

2. **Deterministic autonomy**  
   All autonomous behavior is explicit and rule-based. No LLM or hidden logic can alter trades or rules. The autonomy engine only executes what is specified in ThesisJSON.

3. **Slow, structural macro, not intraday trading**  
   Slice is built around daily EOD data and macro series. It avoids intraday noise and high-frequency behavior. The investor’s time horizon is weeks to months, not minutes.

4. **Structured truth: JSON as the core interface**  
   Theses and observations are represented as strict JSON objects (ThesisJSON, ObservationJSON). This ensures clarity, repeatability, and auditability.

5. **Single source of truth: Postgres + pgvector**  
   Market data, macro series, theses, observations, autonomy runs, and LLM-related embeddings live in one database.

6. **LLM as parser and critic, not as agent**  
   LLMs are used to parse memos into structured form, critique logic, summarize headlines, and organize observations. They do not execute trades, activate theses, or modify rules.

-------------------------------------------------------------------------------
## 3. User Requirements (Phase 1)
-------------------------------------------------------------------------------

The requirements are grouped by usage domain. They are a condensed form of the MB/TH/DQ/SE/NM requirements defined during Phase 1.

### 3.1 Morning Briefing (MB-*)

- **MB-01**: The system must produce a concise daily Morning Briefing summarizing cross-asset performance, key moves, and portfolio PnL/attribution, linked back to thesis expressions.
- **MB-02**: The Morning Briefing must include summarized macro/news themes, focusing on assets and tickers relevant to active theses and portfolio positions. It is factual and non-narrative.
- **MB-03**: The briefing must highlight expression- and thesis-level performance and any material deviations from expectations.
- **MB-04**: The briefing must display yield curve and basic rates structure against a configurable historical backdrop (e.g., current curve vs curve 6 months ago).

### 3.2 Thesis & Thought (TH-*)

- **TH-01**: A user must be able to write a free-form memo and have it parsed into a structured ThesisJSON object.
- **TH-02**: The system must support attaching charts/tables (as structured data) referenced in the thesis; the parsing process must handle tabular/graph-derived data.
- **TH-03**: A thesis must undergo LLM critique (structural and logical), and the system must support iteratively updating the thesis in response to critiques. A thesis cannot be activated if it fails structural validation.
- **TH-04**: Each thesis must be tested quantitatively (backtests, basic scenarios) against historical and current macro data, consistent with the thesis’s drivers and expressions.
- **TH-05**: Slice must track thesis evolution and flag drift between original thesis, ongoing observations, and portfolio expressions (e.g., the investor’s thinking diverging from original logic).

### 3.3 Diagnostics & Quant (DQ-*)

- **DQ-01**: The system must flag serious disconfirmers and divergences clearly (e.g., via alerts or “red” indicators) whenever real-world data materially contradicts the thesis drivers or disconfirmers.
- **DQ-02**: The system must compute daily expression-level performance, drawdowns, and simple attribution.
- **DQ-03**: In addition to PnL, Slice must surface basic analytics daily (e.g., expression performance vs benchmark, key risk metrics) without requiring heavy sweeping backtests every day.

### 3.4 Structural Execution (SE-*)

- **SE-01**: Each thesis must explicitly define its portfolio expressions (underweights/overweights, spreads, themes) and map them to concrete instruments (ETFs, FX, etc.).
- **SE-02**: Each expression must define bands, stops, profit-taking levels, and optional timed actions as part of the thesis definition, not bolted on afterward.
- **SE-03**: These bands, stops, and timed actions must be machine-readable and directly consumed by the autonomy engine—forming the “structural brain” that governs ongoing adjustments.

### 3.5 Narrative & Meta (NM-*)

- **NM-01**: The system must support storing, querying, and reviewing observations (ObservationJSON) as a history of the investor’s thinking.
- **NM-02**: The system must support reflective analysis on how theses and observations performed over time (at a meta level), but Phase 1 only specifies the data structure; higher-order analytics can arrive later.

-------------------------------------------------------------------------------
## 4. ThesisJSON Specification
-------------------------------------------------------------------------------

ThesisJSON is the core object representing a fully structured thesis. It is the “unchanging brain” from which autonomy is derived.

This section defines the conceptual schema. Implementation details (types, constraints) are in `slice_thesis_observation_schema.md`.

### 4.1 Top-Level Structure

```json
{
  "thesis_id": "thesis-2025-gold-01",
  "metadata": {
    "title": "Gold as real rate hedge",
    "author": "Liam",
    "created_at": "ISO8601",
    "last_updated_at": "ISO8601",
    "status": "DRAFT | READY_REVIEW | ACTIVE | REVIEW | RETIRED"
  },
  "hypothesis": { ... },
  "drivers": [ ... ],
  "disconfirmers": [ ... ],
  "expressions": [ ... ],
  "risk_rails": { ... },
  "autonomy_permissions": { ... },
  "audit_log": [ ... ]
}

4.2 Hypothesis

"hypothesis": {
  "summary": "Concise explanation of the thesis",
  "causal_chain": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ..."
  ],
  "horizon": "e.g. 6–18 months",
  "regime_assumptions": [
    "e.g. Fed near end of hiking cycle",
    "e.g. Inflation expectations anchored"
  ]
}

4.3 Drivers

"drivers": [
  {
    "driver_id": "drv-real-yields",
    "name": "US real yields",
    "series_id": "FRED:RIFLGFCY10_N.B" ,
    "direction_expected": "UP | DOWN | FLAT",
    "warning_threshold": "structured condition",
    "disconfirm_threshold": "structured condition",
    "importance": "HIGH | MEDIUM | LOW"
  }
]

Drivers are macro or market series that materially shape the thesis outcome. Thresholds can be described as structured conditions (e.g., JSON expressions) defined elsewhere.

4.4 Disconfirmers

"disconfirmers": [
  {
    "disconfirmer_id": "dcf-real-yields-up",
    "description": "Real yields rise > 150 bps and stay there for 3+ months",
    "condition_type": "LEVEL | TREND | RELATIVE | EVENT",
    "trigger_value": "structured condition"
  }
]

Disconfirmers are explicit situations that materially weaken or kill the thesis.

4.5 Expressions

Expressions are how the thesis enters the portfolio.

"expressions": [
  {
    "expression_id": "expr-gldm-uup-01",
    "label": "Overweight gold vs USD cash",
    "tickers": {
      "GLDM": 0.20,
      "UUP": -0.10
    },
    "target_weight": 0.20,
    "min_weight": 0.10,
    "max_weight": 0.30,
    "band_behavior": "PULL_TO_TARGET | LINEAR | AGGRESSIVE",
    "rebalance_frequency": "DAILY | WEEKLY | MONTHLY",
    "stop_loss": {
      "type": "PCT | LEVEL",
      "value": -0.15
    },
    "profit_take": {
      "type": "PCT | LEVEL",
      "value": 0.20
    },
    "timed_actions": [
      {
        "action_id": "ta-monthly-add",
        "frequency": "MONTHLY",
        "day_rule": "FIRST_TRADING_DAY",
        "action": "ADD | TRIM",
        "size": 0.02
      }
    ],
    "notes": "Optional free-text notes"
  }
]

4.6 Risk Rails

"risk_rails": {
  "max_total_weight": 0.40,
  "max_concentration_per_expression": 0.25,
  "correlation_notes": [
    "GLDM positively correlated with X, negatively with Y"
  ]
}

Risk rails define global constraints within the thesis context.

4.7 Autonomy Permissions

"autonomy_permissions": {
  "allow_autonomous_stops": true,
  "allow_autonomous_rebalances": true,
  "allow_autonomous_profit_taking": false,
  "allow_autonomous_timed_actions": true
}

These flags define what the autonomy engine is allowed to execute without explicit daily confirmation, within the broader system constraints.

⸻

5. ObservationJSON Specification

⸻

Observations represent the investor’s ongoing thoughts and market impressions. They are separate from the thesis but linked to it.

5.1 Structure

{
  "observation_id": "obs-2025-01-15-01",
  "thesis_id": "thesis-2025-gold-01",
  "timestamp": "ISO8601",
  "stance": "CONFIRMING | DISCONFIRMING | MIXED",
  "linked_drivers": ["drv-real-yields"],
  "linked_disconfirmers": ["dcf-real-yields-up"],
  "market_references": ["GLDM", "UUP"],
  "confidence": "LOW | MEDIUM | HIGH",
  "summary": "Short summary in user's own style",
  "raw_text": "Full original note text"
}

Observations are used later for drift analysis, thesis evolution analysis, and meta-evaluation of the investor’s thinking.

⸻

6. Autonomy Engine Specification (Conceptual)

⸻

The autonomy engine reads ThesisJSON and current portfolio/data state, then computes a set of candidate actions based on rules. It does not call LLMs, and LLMs do not call it.

6.1 Responsibilities
	•	Enforce band rebalancing rules.
	•	Apply stop-loss and drawdown logic.
	•	Apply profit-taking rules.
	•	Execute timed actions.
	•	Respect global risk rails.
	•	Log all evaluations and actions deterministically.

6.2 Daily Timing Model

Slice operates on a strict daily rhythm:

End of Day (after close)
	•	Ingest EOD prices and macro data.
	•	Update expression performance.
	•	Evaluate autonomy rules in analysis mode:
	•	band rebalancing
	•	stops
	•	profit-taking
	•	timed actions
	•	global rails
	•	Generate candidate orders but do not execute.
	•	Log all results to Postgres and human-readable logs.

Pre-Market (next session)
	•	Build Morning Briefing.
	•	Summarize autonomy recommendations.
	•	Optionally auto-stage orders only for CRITICAL stops, and only if permitted by autonomy_permissions.

Market Open Window
	•	Execute trades during live market hours only.
	•	Default: human-reviewed execution via CLI (e.g., slice-cli autonomy review and slice-cli autonomy execute-today).
	•	Optional: fully autonomous execution of specific categories (e.g., hard stops) if explicitly allowed.

No intraday evaluation loop is run in Phase 1 design; intraday modules (if ever added) must be explicitly scoped later.

6.3 Rule Evaluation Priority
	1.	Stops
	2.	Profit-taking
	3.	Global risk rails
	4.	Band rebalancing
	5.	Timed actions

Higher-priority rules override lower-priority ones if there is a conflict.

6.4 Execution Adapter

The autonomy engine is decoupled from the broker via an ExecutionAdapter interface.
	•	SimulatedExecutionAdapter — For backtests and dry runs (Phase 2–3).
	•	SchwabExecutionAdapter — Real trades, Phase 3+ only, respecting all constraints.

⸻

7. Data Model Overview (Conceptual ERD)

⸻

Implementation details and exact SQL live in slice_schema.sql.
This section summarizes the logical entities.

Key tables:
	•	assets
	•	asset_id, ticker, name, type (EQUITY_ETF, FX, MACRO_SERIES, etc.)
	•	price_timeseries
	•	asset_id, date, open, high, low, close, volume (for ETFs/FX)
	•	macro_timeseries
	•	series_id, date, value
	•	theses
	•	thesis_id, metadata JSONB, thesis_json JSONB, embeddings (via pgvector)
	•	observations
	•	observation_id, thesis_id, observation_json JSONB, embeddings
	•	expression_performance
	•	expression_id, date, pnl, drawdown, weight, etc.
	•	autonomy_rule_run
	•	run_id, thesis_id, date, evaluated_rules, candidate_actions JSONB
	•	trades
	•	trade_id, thesis_id, expression_id, asset_id, side, quantity, price, timestamp

All tables are indexed appropriately (primarily on id + date).
Data is daily or lower frequency.

⸻

8. Module Architecture

⸻

The codebase will be organized along these boundaries:
	•	slice_app/db/
	•	DB engine setup, SQLAlchemy models, migrations.
	•	slice_app/schemas/
	•	JSON schemas for ThesisJSON and ObservationJSON.
	•	slice_app/thesis/
	•	Thesis lifecycle (create, update, validate, activate/deactivate).
	•	Mapping between raw memos and structured thesis.
	•	slice_app/autonomy/
	•	Runtime models for applying rules.
	•	Rule evaluation engine.
	•	Interaction with ExecutionAdapter.
	•	slice_app/portfolio/
	•	Portfolio state representation.
	•	Expression performance computations.
	•	slice_app/quant/
	•	Data access helpers for time series.
	•	Backtesting and simple scenario analysis.
	•	slice_app/llm/
	•	Calls to LLMs for parsing, critique, summarization, and suggestions.
	•	Adherence to LLM contracts defined below.
	•	slice_app/briefing/
	•	Morning Briefing builder.
	•	Integration of market data, macro data, portfolio, and headlines.
	•	slice_app/scheduler/
	•	Job definitions for EOD updates, daily autonomy eval, briefing generation (Phase 2+).
	•	slice_app/cli/
	•	Command line interface.
	•	Primary control surface for the user.

⸻

9. LLM Contract Definitions (Full)

⸻

LLMs are used only as parsers, critics, and summarizers within strict contracts.
They must not execute trades, change autonomy rules, or activate theses.

This section defines the contracts for the core LLM services.
A more focused version lives in slice_llm_contracts.md.

9.1 thesis_parser

Purpose
Convert a free-form memo into a fully structured ThesisJSON object.

Input

{
  "memo_text": "<raw memo>",
  "tickers_in_universe": ["SPY", "QQQ", "GLDM", "..."]
}

Output (must match ThesisJSON schema)

{
  "thesis_id": "string",
  "hypothesis": {
    "summary": "string",
    "causal_chain": ["string", "..."],
    "horizon": "string",
    "regime_assumptions": ["string", "..."]
  },
  "drivers": [
    {
      "driver_id": "string",
      "name": "string",
      "series_id": "string",
      "direction_expected": "UP | DOWN | FLAT",
      "warning_threshold": "string or structured",
      "disconfirm_threshold": "string or structured",
      "importance": "HIGH | MEDIUM | LOW"
    }
  ],
  "disconfirmers": [
    {
      "disconfirmer_id": "string",
      "description": "string",
      "condition_type": "LEVEL | TREND | RELATIVE | EVENT",
      "trigger_value": "string or number"
    }
  ],
  "expressions": [
    {
      "expression_id": "string",
      "label": "string",
      "tickers": { "GLDM": 0.20 },
      "target_weight": 0.20,
      "min_weight": 0.10,
      "max_weight": 0.30,
      "band_behavior": "PULL_TO_TARGET | LINEAR | AGGRESSIVE",
      "rebalance_frequency": "DAILY | WEEKLY | MONTHLY",
      "stop_loss": {
        "type": "PCT | LEVEL",
        "value": -0.15
      },
      "profit_take": {
        "type": "PCT | LEVEL",
        "value": 0.20
      },
      "timed_actions": [
        {
          "action_id": "string",
          "frequency": "WEEKLY | MONTHLY",
          "day_rule": "string",
          "action": "ADD | TRIM",
          "size": 0.02
        }
      ],
      "notes": "string"
    }
  ],
  "risk_rails": {
    "max_total_weight": 0.40,
    "max_concentration_per_expression": 0.25,
    "correlation_notes": ["string", "..."]
  },
  "autonomy_permissions": {
    "allow_autonomous_stops": true,
    "allow_autonomous_rebalances": true,
    "allow_autonomous_profit_taking": false,
    "allow_autonomous_timed_actions": true
  },
  "metadata": {
    "title": "string",
    "author": "string",
    "created_at": "ISO8601",
    "last_updated_at": "ISO8601",
    "status": "DRAFT"
  },
  "_warnings": []
}

Rules
	•	Must not invent tickers not in tickers_in_universe.
	•	Must not contradict the Phase 1 architecture or autonomy rules.
	•	If the memo lacks information, the parser fills in what it can and uses _warnings to signal missing or ambiguous fields.

⸻

9.2 thesis_critic_stage_1 (Structural Validation)

Purpose
Check structural completeness and adherence to ThesisJSON requirements.

Input

{
  "thesis_json": { "...": "..." }
}

Output

{
  "valid": true,
  "missing_fields": ["path.to.field", "..."],
  "structural_warnings": ["string", "..."]
}

Rules
	•	Purely structural: no macro opinions.
	•	Marks valid = false if any required fields are missing or malformed.
	•	Does not modify the thesis.
	•	Used as a gatekeeper between DRAFT and READY_REVIEW.

⸻

9.3 thesis_critic_stage_2 (Logical & Causal Review)

Purpose
Critique the thesis’s internal logic, coherence, and alignment between hypothesis, drivers, disconfirmers, and expressions.

Input

{
  "thesis_json": { "...": "..." }
}

Output

{
  "critiques": ["string", "..."],
  "incoherencies": ["string", "..."],
  "driver_alignment_issues": ["string", "..."],
  "disconfirmers_issues": ["string", "..."],
  "recommended_fixes": ["string", "..."]
}

Rules
	•	No forecasting, no trade recommendations.
	•	Only evaluates internal logical consistency.
	•	Helps the user refine ThesisJSON before activation.

⸻

9.4 observation_parser

Purpose
Convert free-form notes into ObservationJSON.

Input

{
  "note_text": "string",
  "related_thesis": "thesis-2025-gold-01"
}

Output

{
  "observation_id": "string",
  "thesis_id": "thesis-2025-gold-01",
  "timestamp": "ISO8601",
  "stance": "CONFIRMING | DISCONFIRMING | MIXED",
  "linked_drivers": ["drv-real-yields"],
  "linked_disconfirmers": ["dcf-real-yields-up"],
  "market_references": ["GLDM", "UUP"],
  "confidence": "LOW | MEDIUM | HIGH",
  "summary": "string",
  "raw_text": "string"
}

Rules
	•	Must not link to drivers/disconfirmers that do not exist in the given thesis.
	•	Must not invent non-existent facts.
	•	Must adhere to ObservationJSON structure.

⸻

9.5 headline_summarizer

Purpose
Cluster and summarize raw headlines into themes for Morning Briefing.

Input

{
  "raw_headlines": ["string", "..."]
}

Output

{
  "themes": [
    {
      "theme_name": "string",
      "headline_count": 5,
      "representative_headline": "string",
      "relevance_to_tickers": ["SPY", "GLDM"]
    }
  ]
}

Rules
	•	No narrative, no “why markets moved.”
	•	Only thematic clustering and relevance mapping to tickers.

⸻

9.6 trade_proposer (Thesis Session Only)

Purpose
During a thesis-building session, suggest ways the expressions could be aligned with the thesis narrative and drivers.
This is a thinking aid, not an execution engine.

Input

{
  "thesis_json": { "...": "..." },
  "portfolio_state": { "...": "..." }
}

Output

{
  "suggested_expressions": ["string", "..."],
  "risk_notes": ["string", "..."],
  "alignment_notes": ["string", "..."]
}

Rules
	•	Must not generate actual trade instructions or order details.
	•	Must not include price targets or timing advice.
	•	Supports ideation; actual decisions are made by the user via ThesisJSON edits.

⸻

10. Safety and Constraints

⸻

	•	LLMs cannot execute trades, modify autonomy rules, or activate/deactivate theses.
	•	Autonomy engine does not call LLMs.
	•	Execution happens only during market hours (no off-hours trading).
	•	All actions are logged in both DB and human-readable logs.
	•	A thesis cannot become ACTIVE unless it passes structural validation and the core fields are present and coherent.
	•	No cross-thesis interference without explicit design in later phases.

⸻

11. Phase 2 and Phase 3 Roadmap (High-Level)

⸻

Phase 2: Data Pipeline & Infrastructure
	•	Set up Postgres + pgvector.
	•	Implement schemas from slice_schema.sql.
	•	Implement data ingestion from TwelveData, yfinance, and FRED.
	•	Perform historical backfill for all required assets and macro series.
	•	Implement daily and monthly update scripts (no scheduler yet).
	•	Implement basic CLI for data operations.

Phase 3: Core Logic Implementation
	•	Thesis lifecycle implementation (parser, critics, validator, state transitions).
	•	Autonomy engine wiring (without broker integration at first).
	•	Morning Briefing builder.
	•	Basic quant tools for expression performance and scenario checks.
	•	CLI and minimal UI integration.

⸻

12. Glossary

⸻

	•	ThesisJSON: Structured object representing a full macro thesis.
	•	ObservationJSON: Structured object representing a single observation linked to a thesis.
	•	Expression: A concrete portfolio representation of a thesis (weights in instruments, bands, stops, etc.).
	•	Autonomy engine: Rule engine that evaluates ThesisJSON against portfolio and data and generates candidate actions.
	•	LLM: Large language model used only for parsing, critique, and summarization under strict contracts.
	•	EOD (End of Day): After market close, when daily evaluation runs.
	•	ExecutionAdapter: Abstraction layer between autonomy engine and broker or simulator.

⸻

END OF DOCUMENT