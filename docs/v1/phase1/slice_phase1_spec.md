# Slice Phase 1 Full Specification

This document consolidates the entire Phase 1 design of Slice.  
It is the authoritative specification for architecture, schemas, autonomy, LLM behavior, timing, and system boundaries.

No implementation may contradict this document.

-------------------------------------------------------------------------------
# 1. Purpose
-------------------------------------------------------------------------------

Slice is a discretionary macro “operating system” for a single investor.  
Its goals are to:

- formalize theses into structured objects  
- record observations in structured format  
- evaluate thesis drivers vs real data  
- enforce deterministic portfolio rules at daily frequency  
- support human macro thinking without replacing judgment  

Slice is NOT:

- a price forecaster  
- an intraday trading bot  
- a reactive algorithm  
- a narrative generator  

Slice is a **slow, structural macro decision-support system**.

Phase 1 defines everything needed before coding: requirements, schemas, logic, architecture, LLM contracts, timing, and safety.

-------------------------------------------------------------------------------
# 2. System Philosophy
-------------------------------------------------------------------------------

1. **Human at the center**  
   Slice enhances judgment; it does not replace it.

2. **Daily-cycle macro, not intraday trading**  
   Slice evaluates at EOD, executes next open.  
   No intraday decisions.

3. **Deterministic autonomy**  
   Autonomy follows only explicit rules inside ThesisJSON.

4. **Strict structured truth**  
   Theses and observations are JSON objects with fixed fields.

5. **One source of truth**  
   Postgres + pgvector stores all data, theses, observations, autonomy runs, logs.

6. **LLM is a parser/critic, not an agent**  
   It converts memos into structured logic, but cannot act on the portfolio.

-------------------------------------------------------------------------------
# 3. Requirements
-------------------------------------------------------------------------------

Grouped by functional domain:

### Morning Briefing (MB)
- MB-01: Daily newsletter summarizing market moves and portfolio impact.
- MB-02: Headline summarization aligned to active thesis tickers.
- MB-03: Expression and thesis-level performance updates.
- MB-04: Yield curve and basic macro structures plotted vs configurable history.

### Thesis & Thought (TH)
- TH-01: Memos → structured ThesisJSON.
- TH-02: Charts/tables parseable into structured fields.
- TH-03: Two-stage critique before activation.
- TH-04: Thesis must be tested against historical data and regimes.
- TH-05: Drift detection between thesis logic and observations.

### Diagnostics & Quant (DQ)
- DQ-01: Flag severe disconfirmers clearly.
- DQ-02: Expression-level performance and risk analytics.
- DQ-03: Daily analytics beyond PnL, without heavy backtesting.

### Structural Execution (SE)
- SE-01: Expressions must be fully defined inside ThesisJSON.
- SE-02: Bands, stops, profit-taking, and timed actions must be embedded in ThesisJSON.
- SE-03: Autonomy engine derives all rules solely from ThesisJSON.

### Narrative & Meta (NM)
- NM-01: Store and retrieve ObservationJSON.
- NM-02: Long-term reflection on thesis evolution and observation drift.

-------------------------------------------------------------------------------
# 4. ThesisJSON Specification
-------------------------------------------------------------------------------

ThesisJSON is the “unchanging brain” of Slice.