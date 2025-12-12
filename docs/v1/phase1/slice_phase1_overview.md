# Slice Phase 1 Overview

This document summarizes the full architectural and conceptual design of Slice as defined in Phase 1. It is a high-level executive overview meant for quick onboarding and orientation. Detailed specifications live in the Master Spec and related documents.

-------------------------------------------------------------------------------
## 1. Purpose
-------------------------------------------------------------------------------

Slice is a long-horizon discretionary macro operating system.  
It structures theses, records observations, monitors markets, and enforces deterministic rule-based portfolio actions derived from those theses.

Slice is designed to:

- support human judgment, not replace it  
- enforce discipline and consistency  
- avoid intraday noise  
- unify data, logic, and workflow  
- provide a daily rhythm for macro thinking  

Phase 1 establishes all definitions, schemas, rules, contracts, and architectural boundaries required before any coding.

-------------------------------------------------------------------------------
## 2. Core Concepts
-------------------------------------------------------------------------------

### 2.1 ThesisJSON
A strict, machine-readable representation of a macro thesis:
- hypothesis  
- causal logic  
- drivers  
- disconfirmers  
- expression weights and bands  
- stop-loss rules  
- profit-taking rules  
- timed actions  
- risk rails  
- autonomy permissions  

ThesisJSON is the system’s “unchanging brain.”

### 2.2 ObservationJSON
A structured record of ongoing investor thoughts:
- stance (confirming, disconfirming, mixed)  
- linked drivers/disconfirmers  
- referenced tickers  
- confidence  
- summary and raw text  

Observations are used for drift detection and meta-analysis.

### 2.3 Autonomy Engine
A deterministic rules engine that interprets ThesisJSON and portfolio state.  
Responsibilities include:
- band rebalancing  
- stops  
- profit-taking  
- timed actions  
- global risk rails  
- generating candidate trades  

Autonomy does **not** run intraday and does **not** execute off-hours.

### 2.4 LLM Components
LLMs act only as:
- parsers (turn memos into ThesisJSON)  
- structural critics  
- logical critics  
- observation parsers  
- headline summarizers  

LLMs never execute trades or modify thesis structure automatically.

### 2.5 Architecture
Phase 1 defines a modular codebase:
- db  
- schemas  
- thesis  
- autonomy  
- portfolio  
- quant  
- llm  
- briefing  
- scheduler  
- cli  

The system is designed to remain clean, testable, and evolvable.

-------------------------------------------------------------------------------
## 3. Daily Operational Cycle (Finalized Timing Model)
-------------------------------------------------------------------------------

Slice operates on a strict daily cycle:

### 1. End-of-Day (After Market Close)
- ingest closing prices  
- update expression performance  
- update macro series  
- evaluate autonomy rules in analysis mode  
- generate candidate orders  
- log all evaluations  
- **no execution**

### 2. Pre-Market (Next Session)
- build the Morning Briefing  
- summarize autonomy recommendations  
- auto-stage only critical stops (if allowed)

### 3. Market Open Execution Window
- execute trades only during live market hours  
- default: human-reviewed execution via CLI  
- optional: limited autonomous execution if ThesisJSON permits

This rhythm ensures Slice behaves like a deliberate macro allocator.

-------------------------------------------------------------------------------
## 4. Requirements Completed in Phase 1
-------------------------------------------------------------------------------

Phase 1 produced formal requirements for:

- Morning Briefing (MB-*)  
- Thesis & Thought (TH-*)  
- Diagnostics (DQ-*)  
- Structural Execution (SE-*)  
- Narrative & Meta (NM-*)  
- System Capabilities (SC-*)  

These define the required functionality and guardrails for all later phases.

-------------------------------------------------------------------------------
## 5. Phase 1 Deliverables
-------------------------------------------------------------------------------

Phase 1 produced:

- ThesisJSON specification  
- ObservationJSON specification  
- Autonomy engine specification  
- Full timing model  
- Data model + ERD summary  
- Module architecture  
- LLM contract definitions  
- Phase 2–3 execution roadmap  
- Safety constraints  

This forms the complete intellectual and architectural backbone of Slice.

-------------------------------------------------------------------------------
## 6. What's Next (Phase 2 Preview)
-------------------------------------------------------------------------------

Phase 2 focuses entirely on data:

- build Postgres + pgvector  
- create tables from schema  
- ingest historical market and macro data  
- implement daily and monthly update jobs  
- build CLI tools for data operations  

No autonomy, thesis lifecycle, or UI logic is implemented in Phase 2.

-------------------------------------------------------------------------------
END OF DOCUMENT
-------------------------------------------------------------------------------