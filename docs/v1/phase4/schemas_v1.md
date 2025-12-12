

⸻

📄 Slice Phase 4 – Core Schemas v1

This document defines the canonical JSON schemas for:
	•	Thesis
	•	Observation
	•	Trade
	•	Scenario

These schemas are the authoritative source for Phase 4.
All Pydantic models, DB tables, LLM contracts, and internal logic MUST match these structures exactly.

⸻

1. Thesis JSON Schema (v1)

Intent: Structured representation of a macro thesis, including causal story, drivers, disconfirmers, and its portfolio expression.

Canonical Example

{
  "id": "thesis_2025_01_fed_cuts_gold",
  "title": "Gold outperforms as real rates fall on Fed cuts",
  "hypothesis": "If the Fed cuts into sticky inflation, real rates will fall and gold will outperform nominal bonds.",
  "drivers": [
    "Fed cuts policy rate while inflation remains elevated",
    "Real yields decline on the long end of the curve",
    "Market narrative shifts toward inflation hedge assets"
  ],
  "disconfirmers": [
    "Real yields stay high or rise",
    "USD strengthens materially",
    "Inflation falls faster than expected and credibility improves"
  ],
  "expression": [
    {
      "asset": "GLD",
      "direction": "LONG",
      "size_pct": 15.0
    },
    {
      "asset": "TLT",
      "direction": "SHORT",
      "size_pct": 10.0
    }
  ],
  "start_date": "2025-01-15",
  "review_date": "2025-07-15",
  "status": "ACTIVE",
  "tags": ["rates", "inflation", "gold"],
  "monitor_indices": ["US10Y_REAL", "DXY", "US_CPI_YOY"],
  "notes": "Structural lean: long gold vs long duration."
}

Field Definitions
	•	id: string — Unique thesis identifier.
	•	title: string — Human-readable short title.
	•	hypothesis: string — Core causal claim.
	•	drivers: string[] — Supporting conditions that strengthen the thesis.
	•	disconfirmers: string[] — Conditions that weaken or invalidate the thesis.
	•	expression: ExpressionLeg[]
	•	asset: string
	•	direction: "LONG" | "SHORT"
	•	size_pct: number | null (0–100)
	•	start_date: string — ISO date.
	•	review_date: string | null
	•	status: "ACTIVE" | "CLOSED" | "WATCHLIST"
	•	tags: string[]
	•	monitor_indices: string[] — Must correspond to canonical price / macro series.
	•	notes: string | null

⸻

2. Observation JSON Schema (v1)

Intent: A structured log of raw thoughts, datapoints, or narrative cues linked to theses.

Canonical Example

{
  "id": "obs_2025_01_15_093001",
  "timestamp": "2025-01-15T09:30:01Z",
  "text": "CPI print came in slightly hot, but 10y real yields fell intraday as market priced earlier cuts.",
  "thesis_ref": ["thesis_2025_01_fed_cuts_gold"],
  "sentiment": "BULLISH",
  "categories": ["macro_data", "inflation", "rates"],
  "actionable": "MONITORING"
}

Field Definitions
	•	id: string
	•	timestamp: datetime (ISO8601)
	•	text: string — Raw natural-language observation.
	•	thesis_ref: string[] — Linked thesis IDs (0 or more).
	•	sentiment: enum —
	•	VERY_BULLISH, BULLISH, NEUTRAL, BEARISH, VERY_BEARISH, ANXIOUS, CONFIDENT
	•	categories: string[]
	•	actionable: "YES" | "NO" | "MONITORING"

DB-only (not in JSON):
	•	embedding: vector(1536) — pgvector column derived from text.

⸻

3. Trade JSON Schema (v1)

Intent: Normalized representation of a trade, consistent with Phase 3 backtest output and future broker execution.

Canonical Example

{
  "trade_id": "sim_2025_01_15_1",
  "timestamp": "2025-01-15T14:05:00Z",
  "asset": "GLD",
  "action": "BUY",
  "quantity": 50.0,
  "price": 192.35,
  "type": "SIMULATED",
  "thesis_ref": "thesis_2025_01_fed_cuts_gold",
  "notes": "Initial sizing leg toward 15% GLD target."
}

Field Definitions
	•	trade_id: string
	•	timestamp: datetime (ISO8601)
	•	asset: string
	•	action: "BUY" | "SELL"
	•	quantity: number
	•	price: number
	•	type: "SIMULATED" | "REAL"
	•	thesis_ref: string | null
	•	notes: string | null

⸻

4. Scenario JSON Schema (v1)

Intent: Structured what-if scenario used for scenario grids, sensitivity testing, and risk lensing.

Canonical Example

{
  "scenario_id": "scenario_2025_soft_landing",
  "name": "Soft landing with early cuts",
  "assumptions": {
    "US_CPI_YOY": "falls to ~2.5%",
    "US_UNEMPLOYMENT": "rises to ~4.5%",
    "FED_FUNDS": "cut by 100bp over the year",
    "US10Y_YIELD": "3.25–3.75%"
  },
  "expected_impact": {
    "SPY": 0.08,
    "TLT": 0.05,
    "GLD": 0.12,
    "DXY": -0.03
  },
  "description": "Fed engineers a soft landing: inflation cools without recession; real yields drift lower; gold benefits."
}

Field Definitions
	•	scenario_id: string
	•	name: string
	•	assumptions: {string: string | number} — key/value macro assumptions
	•	expected_impact: {string: number} — asset → expected return (decimal)
	•	description: string

⸻

End of File