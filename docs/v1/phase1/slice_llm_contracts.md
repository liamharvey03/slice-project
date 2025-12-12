# Slice LLM Contract Definitions

This document defines the contract for the five LLM services in Slice.
All LLM components operate strictly as parsing, critique, or summarization engines.
No LLM component may execute trades, modify autonomy logic, or alter portfolio state.

-------------------------------------------------------------------------------
1. thesis_parser
-------------------------------------------------------------------------------

Purpose:
Convert a free-form human memo into a fully structured ThesisJSON object.

Input:
{
  "memo_text": "<raw memo>",
  "tickers_in_universe": ["SPY", "QQQ", "GLDM", ...]
}

Output (must match ThesisJSON schema exactly):
{
  "thesis_id": "string",
  "hypothesis": {
    "summary": "string",
    "causal_chain": ["string", ...],
    "horizon": "string",
    "regime_assumptions": ["string", ...]
  },
  "drivers": [
    {
      "name": "string",
      "series_id": "string",
      "direction_expected": "UP | DOWN | FLAT",
      "warning_threshold": "numeric or structured",
      "disconfirm_threshold": "numeric or structured",
      "importance": "HIGH | MEDIUM | LOW"
    }
  ],
  "disconfirmers": [
    {
      "description": "string",
      "condition_type": "LEVEL | TREND | RELATIVE | EVENT",
      "trigger_value": "string or number"
    }
  ],
  "expressions": [
    {
      "expression_id": "string",
      "tickers": {
        "GLDM": 0.15,
        "UUP": 0.10
      },
      "target_weight": 0.25,
      "min_weight": 0.15,
      "max_weight": 0.35,
      "band_behavior": "PULL_TO_TARGET | LINEAR | AGGRESSIVE",
      "stop_loss": {
        "type": "PCT | LEVEL",
        "value": "number"
      },
      "profit_take": {
        "type": "PCT | LEVEL",
        "value": "number"
      },
      "timed_actions": [
        {
          "frequency": "WEEKLY | MONTHLY",
          "day": "string",
          "action": "ADD | TRIM",
          "size": "number"
        }
      ]
    }
  ],
  "risk_rails": {
    "max_total_weight": "number",
    "max_concentration": "number",
    "correlation_notes": ["string", ...]
  },
  "autonomy_permissions": {
    "allow_autonomous_stops": true,
    "allow_autonomous_rebalances": false,
    "allow_autonomous_profit_taking": false
  },
  "status": "DRAFT",
  "_warnings": []
}

Rules:
- Must not invent tickers not in tickers_in_universe.
- Must not contradict Slice architecture.
- If memo lacks required elements, populate _warnings.


-------------------------------------------------------------------------------
2. thesis_critic_stage_1  (Structural Validation)
-------------------------------------------------------------------------------

Purpose:
Validate that ThesisJSON is structurally complete and consistent.

Input:
{
  "thesis_json": { ... }
}

Output:
{
  "valid": true/false,
  "missing_fields": ["path.to.missing", ...],
  "structural_warnings": ["string", ...]
}

Rules:
- Purely structural. No macro views.
- Marks valid=false if any required field missing.
- Does not modify the thesis.


-------------------------------------------------------------------------------
3. thesis_critic_stage_2  (Logical & Causal Validation)
-------------------------------------------------------------------------------

Purpose:
Critique the logical consistency of the thesis without forecasting.

Input:
{
  "thesis_json": { ... }
}

Output:
{
  "critiques": ["string", ...],
  "incoherencies": ["string", ...],
  "driver_alignment_issues": ["string", ...],
  "disconfirmers_issues": ["string", ...],
  "recommended_fixes": ["string", ...]
}

Rules:
- No predictions, no trade suggestions, no narratives.
- Evaluate internal logic only.


-------------------------------------------------------------------------------
4. observation_parser
-------------------------------------------------------------------------------

Purpose:
Convert a free-form investor note into a structured ObservationJSON.

Input:
{
  "note_text": "string",
  "related_thesis": "thesis_id"
}

Output:
{
  "observation_id": "string",
  "timestamp": "ISO8601",
  "stance": "CONFIRMING | DISCONFIRMING | MIXED",
  "linked_drivers": ["driver_name", ...],
  "linked_disconfirmers": ["disconfirmer_description", ...],
  "market_references": ["SPY", "GLDM", ...],
  "confidence": "LOW | MEDIUM | HIGH",
  "summary": "string"
}

Rules:
- Must not invent drivers not in thesis.
- Must not infer nonexistent facts.
- Must remain consistent with ObservationJSON schema.


-------------------------------------------------------------------------------
5. headline_summarizer
-------------------------------------------------------------------------------

Purpose:
Reduce raw headlines into macro themes for the Morning Briefing.

Input:
{
  "raw_headlines": ["string", ...]
}

Output:
{
  "themes": [
    {
      "theme_name": "string",
      "headline_count": number,
      "representative_headline": "string",
      "relevance_to_tickers": ["SPY", "GLDM", ...]
    }
  ]
}

Rules:
- No storytelling, explanations, or market narratives.
- Purely clustering and thematic extraction.


-------------------------------------------------------------------------------
6. trade_proposer (Thesis Session Only)
-------------------------------------------------------------------------------

Purpose:
Provide expression-alignment guidance during thesis sessions.

Input:
{
  "thesis_json": { ... },
  "portfolio_state": { ... }
}

Output:
{
  "suggested_expressions": ["string", ...],
  "risk_notes": ["string", ...],
  "alignment_notes": ["string", ...]
}

Rules:
- No actual trades.
- No price targets.
- No execution logic.
- Supports ideation only.

-------------------------------------------------------------------------------
END OF DOCUMENT
-------------------------------------------------------------------------------