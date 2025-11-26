
# slice_autonomy_spec.md — UPDATED WITH DAILY CYCLE LOGIC

## Autonomy Engine Specification (Updated)

This document defines the full behavior of the Slice autonomy engine, now explicitly including the
daily timing model: **EOD evaluation → next open execution**.

---

# 1. Purpose

The autonomy engine enforces deterministic, rule-based portfolio adjustments derived from ThesisJSON:

- band rebalancing  
- stop-loss rules  
- profit-taking  
- timed actions  
- global risk rails  

It performs **analysis after market close**, and **executes trades the following session during market hours**, unless explicitly disabled by the user.

---

# 2. Daily Timing Model (Critical Update)

## 2.1 End of Day (After Close)

Autonomy runs immediately after all markets have officially closed.

### Steps:

1. **Ingest closing prices** (TwelveData EOD)
2. **Update expression performance**
3. **Evaluate autonomy rules** in *analysis mode*
4. **Generate candidate orders**, but do **not execute**
5. **Log decisions** to:
   - Postgres (`autonomy_rule_run`)
   - Human-readable logs (`logs/autonomy/...`)

### Important:
No portfolio changes occur outside market hours.

---

## 2.2 Pre-Market Next Session (08:30–09:15 ET)

Slice:

- Builds the Morning Briefing
- Summarizes autonomy recommendations
- Prepares staged orders

Only **hard stops with explicit autonomy permission** may be auto-staged.

---

## 2.3 Market Open Execution Window (09:30–10:00 ET)

### Execution rules:

1. **Autonomous actions**  
   - Allowed only if ThesisJSON explicitly grants permission  
   - Examples:
     - Max drawdown stops  
     - Hard disconfirmer exits  
     - Mandatory risk-off rails  

2. **Human-reviewed actions (default)**  
   Commands:
   ```
   slice-cli autonomy review
   slice-cli autonomy execute-today
   ```

Slice **never executes trades intraday or off-hours**.

---

# 3. Rule Evaluation Hierarchy

Priority:

1. **Stops**
2. **Profit-taking**
3. **Global rails**
4. **Band rebalancing**
5. **Timed actions**

---

# 4. Execution Adapter

Two implementations:

- `SimulatedExecutionAdapter` (Phase 2)
- `SchwabExecutionAdapter` (Phase 3+)

Execution occurs only during market hours.

---

# 5. Safety

- Global max notional change
- Per-expression ticket minimums
- Confirmation flags
- Full audit logs

---

This updated version supersedes all prior autonomy specifications.
