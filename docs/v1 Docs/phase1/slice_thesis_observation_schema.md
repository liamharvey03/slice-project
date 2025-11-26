
# Slice – ThesisJSON & ObservationJSON Specification (v1)

## 1. ThesisJSON

This JSON object is the canonical representation of a thesis in Slice. It lives in `thesis.thesis_json` in Postgres and is the source of truth for:

- drivers
- disconfirmers
- expressions
- risk rails
- lifecycle
- autonomy rules

### 1.1 Top-level structure

```jsonc
{
  "version": "1.0",
  "title": "Gold as a pressure valve for high real yields",
  "hypothesis": {
    "summary": "Gold will outperform as real yields peak and policy/fiscal uncertainty grows.",
    "narrative": "Full prose explanation of the idea, causal chain, historical analogs, etc.",
    "time_horizon": "6-18 months",
    "regime_assumptions": [
      "US growth decelerating but not collapsing",
      "Fed near end of hiking cycle",
      "Fiscal concerns keep term premium elevated"
    ]
  },
  "context": {
    "created_from_memo_id": "memo_2025_11_20_01",
    "macro_background": [
      "US real 10y near cycle highs",
      "Gold held up despite rising reals",
      "Positioning stretched in USTs"
    ],
    "tags": ["gold", "real-yields", "US-rates", "macro-hedge"]
  },
  "drivers": [],
  "disconfirmers": [],
  "expressions": [],
  "risk_rails": {},
  "lifecycle": {
    "status": "ACTIVE",
    "birth_date": "2025-11-20",
    "next_review_date": "2026-02-01",
    "burial_criteria": [
      "Two core disconfirmers triggered for > 1 month",
      "3m rolling performance below -10% with no structural justification"
    ]
  },
  "meta": {
    "author": "Liam",
    "collaborators": [],
    "notes": ""
  }
}
```

---

### 1.2 Drivers

Drivers are animating macro variables that should support the thesis when they move as expected.

**Requirements**

- At least **one PRIMARY** driver, usually more
- Each driver must have:
  - `name`
  - `description`
  - `macro_series_ref`
  - `expected_direction`
  - `importance`
  - thresholds (at least a warning or disconfirm threshold)

**Schema**

```jsonc
"drivers": [
  {
    "id": "drv_real_10y",
    "name": "US 10y real yield",
    "description": "Primary macro driver; thesis assumes real yields are near cycle peak and path is sideways-to-lower.",
    "macro_series_ref": {
      "type": "FRED",
      "id": "DFII10",
      "transform": "daily"
    },
    "expected_direction": "STABLE_OR_LOWER",     // UP, DOWN, STABLE, STABLE_OR_LOWER, ELEVATED, etc.
    "importance": "PRIMARY",                     // PRIMARY or SECONDARY
    "thresholds": {
      "warning": 2.5,
      "disconfirm": 3.0
    },
    "notes": "Above 3% real for more than 1–2 months severely weakens the thesis."
  }
]
```

---

### 1.3 Disconfirmers

Disconfirmers describe conditions that seriously weaken or kill the thesis.

**Requirements**

- At least **one CRITICAL** disconfirmer
- At least **two total** disconfirmers per thesis
- CRITICAL disconfirmers must be quantitatively defined where possible

**Schema**

```jsonc
"disconfirmers": [
  {
    "id": "disc_real_10y_persistently_high",
    "description": "Real 10y > 3.0% for more than 2 months without gold drawing down significantly.",
    "linked_driver_id": "drv_real_10y",
    "condition": {
      "type": "MACRO_SERIES_CONDITION",
      "series_ref": {
        "type": "FRED",
        "id": "DFII10"
      },
      "operator": ">",
      "value": 3.0,
      "lookback_days": 60,
      "required_fraction": 0.7
    },
    "severity": "CRITICAL",  // INFO / WARNING / CRITICAL
    "notes": "Signals a structural regime where high reals do not pressure gold; thesis needs re-write."
  }
]
```

---

### 1.4 Expressions

Expressions encode how the thesis shows up in the portfolio (trades).

**Requirements**

Each expression must specify:

- `expression_type`
- one or more `legs`
- a `sizing` block with:
  - `target_portfolio_weight_pct`
  - `min_weight_pct`
  - `max_weight_pct`
- `rebalancing` rules
- at least one `stops` rule
- at least one `profit_taking` rule
- `constraints`
- optional `timed_actions`

**Schema**

```jsonc
"expressions": [
  {
    "id": "expr_gold_overweight",
    "label": "Overweight GLDM as core expression",
    "expression_type": "LONG",        // LONG, SHORT, SPREAD, RELATIVE, BASKET, etc.
    "legs": [
      {
        "role": "PRIMARY",
        "asset_symbol": "GLDM",
        "direction": "LONG"
      }
    ],
    "linkage": {
      "linked_driver_ids": ["drv_real_10y", "drv_term_premium"],
      "linked_disconfirmmer_ids": ["disc_real_10y_persistently_high"]
    },
    "sizing": {
      "target_portfolio_weight_pct": 15.0,
      "min_weight_pct": 10.0,
      "max_weight_pct": 20.0,
      "scaling_rule": "LINEAR_WITH_CONVICTION",
      "notes": "Conviction-based scaling can be extended later."
    },
    "rebalancing": {
      "band_rebalance": true,
      "rebalance_threshold_pct": 3.0,    // rebalance if outside [target ± 3%]
      "rebalance_frequency": "DAILY"
    },
    "stops": {
      "max_drawdown_pct": 15.0,
      "trailing_stop_pct": 10.0,
      "hard_stop_rule": "If GLDM drops > 20% from peak while drivers unchanged, trigger review."
    },
    "profit_taking": {
      "take_profit_levels": [
        {
          "threshold_return_pct": 25.0,
          "action": "TRIM",
          "trim_to_weight_pct": 10.0
        }
      ]
    },
    "timed_actions": [
      {
        "id": "ta_add_on_dips",
        "description": "Add 2% monthly if driver state supportive.",
        "type": "CALENDAR_AND_CONDITION",
        "schedule": "MONTHLY",
        "conditions": [
          {
            "type": "DRIVER_STATE",
            "driver_id": "drv_real_10y",
            "state": "STABLE_OR_LOWER"
          }
        ],
        "action": {
          "type": "ADJUST_WEIGHT",
          "delta_weight_pct": 2.0,
          "max_weight_pct": 20.0
        }
      }
    ],
    "constraints": {
      "max_notional_usd": 5000,
      "min_ticket_size_usd": 500
    },
    "notes": ""
  }
]
```

---

### 1.5 Risk Rails

Risk rails define thesis-level guardrails beyond individual expressions.

**Schema**

```jsonc
"risk_rails": {
  "overall_exposure": {
    "max_gross_pct": 40.0,
    "max_net_pct": 30.0,
    "max_single_expression_pct": 20.0
  },
  "correlation_limits": {
    "max_pairwise_corr": 0.8,
    "notes": "Flag if expressions become overly correlated with each other or with SPY."
  },
  "volatility_limits": {
    "target_annualized_vol_pct": 10.0,
    "max_annualized_vol_pct": 15.0
  },
  "autonomy_permissions": {
    "allow_band_rebalancing": true,
    "allow_stop_execution": true,
    "allow_timed_actions": true,
    "require_human_confirm_for": ["MAJOR_SIZE_UP"]
  }
}
```

---

### 1.6 Lifecycle

**Schema**

```jsonc
"lifecycle": {
  "status": "ACTIVE",                   // DRAFT, READY_REVIEW, ACTIVE, REVIEWED, RETIRED
  "birth_date": "2025-11-20",
  "next_review_date": "2026-02-01",
  "burial_criteria": [
    "Two core disconfirmers triggered for > 1 month",
    "3m rolling performance below -10% with no structural justification"
  ]
}
```

---

## 2. ObservationJSON

ObservationJSON represents your ongoing observations tied to a thesis. It lives in `observation.observation_json` and is embedded for drift/behavioral analysis.

### 2.1 Structure

```jsonc
{
  "version": "1.0",
  "thesis_id": "thesis_2025_gold_01",
  "timestamp": "2025-11-21T09:45:00Z",
  "source": "USER_NOTE",              // USER_NOTE, IMPORTED, CHAT
  "summary": "Real yields pushed higher but gold barely moved; positioning may be shifting.",
  "body": "Longer note in your own voice...",
  "tags": ["real-yields", "gold", "positioning"],
  "classification": {
    "stance": "MIXED",                // CONFIRMING, DISCONFIRMING, MIXED, NEUTRAL
    "certainty": "MEDIUM",            // LOW, MEDIUM, HIGH
    "emotional_tone": "CALM"         // optional, for later behavioral analytics
  },
  "driver_links": [
    {
      "driver_id": "drv_real_10y",
      "perceived_effect": "DISCONFIRMING",  // SUPPORTING, DISCONFIRMING, NEUTRAL
      "comment": "Real 10y broke above 2.7%, near my warning zone."
    }
  ],
  "disconfirmer_links": [
    {
      "disconfirmer_id": "disc_real_10y_persistently_high",
      "status": "AT_RISK",            // NOT_TRIGGERED, AT_RISK, TRIGGERED
      "comment": "We might be entering the range where this disconfirmer fires if it persists."
    }
  ],
  "market_links": [
    {
      "asset_symbol": "GLDM",
      "relationship": "PRIMARY_EXPRESSION",
      "comment": "GLDM holding firm despite rate move."
    },
    {
      "asset_symbol": "DXY",
      "relationship": "SECONDARY_CONTEXT",
      "comment": ""
    }
  ],
  "impact_on_thesis": {
    "proposed_action": "REVIEW",      // NONE, WATCH, REVIEW, ESCALATE
    "notes": "Consider whether high real yields can persist without crushing gold; possible regime shift.",
    "llm_suggested_updates": [
      {
        "type": "ADJUST_THRESHOLD",
        "target": "drivers.drv_real_10y.thresholds.warning",
        "suggested_new_value": 2.8,
        "rationale": "Recent behavior suggests prior warning level may be too tight."
      }
    ]
  }
}
```

### 2.2 DB Fields That Pair With ObservationJSON

In the Postgres `observation` table:

- `id` (PK)
- `thesis_id` (FK)
- `created_at`
- `raw_text`
- `observation_json` (this schema)
- `embedding` (vector)
- `intuition_eval` (UNASSESSED, CONFIRMED, DISCONFIRMED, UNCLEAR)
- `eval_time`

This enables:

- “how yesterday’s observations aged”
- drift detection
- history of thought evolution tied to the thesis
