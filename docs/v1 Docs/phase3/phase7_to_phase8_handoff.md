# Phase 7 → Phase 8 Handoff

## Current State (End of Phase 7)

- Intelligence layer exposes four new engines:
  - Long-horizon analysis
  - Strategy recommendation
  - Portfolio diagnostics
  - Narrative coherence
- All engines:
  - Use `ContextBuilder` for deterministic context assembly.
  - Call `OrchestratorClient.run_analyst(...)`.
  - Are reachable through `/api/v1/intel/*` routes.
- Phase 4–6 behavior and contracts are preserved (`SessionResponse`, existing routes/tests).

## Priority TODOs for Phase 8

### 1. Real portfolio surfaces

- Replace stub portfolio dicts (`current_portfolio`, `portfolio_snapshot`) with:
  - Concrete portfolio models (positions, weights, tags).
  - DataAccess methods to fetch portfolio state.
- Wire portfolio data into:
  - `build_strategy_context`
  - `build_portfolio_diagnostics_context`
  - `build_narrative_coherence_context`

### 2. Rich macro_view

- Extend `macro_view` beyond risk snapshot:
  - Macro regime tagging (growth/inflation/rates).
  - Key indicators (PMIs, breakevens, curves).
  - External feeds as needed.
- Ensure the same macro_view is shared across engines for consistency.

### 3. Constraints and policies

- Introduce explicit user / mandate constraints:
  - Max sector/asset weights.
  - Risk limits (VaR, drawdown, leverage).
  - Liquidity and tenor constraints.
- Surface constraints in:
  - Strategy recommendations (what is feasible).
  - Diagnostics (which limits are at risk).
  - Narrative (how constraints shape positioning).

### 4. Dependency wiring

- Implement real `DataAccess.depends()` and `OrchestratorClient.depends()`:
  - Construct repositories, DB handles, and LLM clients.
  - Register dependencies in the FastAPI startup wiring.
- Ensure Phase 7 routes work end-to-end in a production environment.

### 5. UX and response shaping

- Standardize response formatting for Phase 7 engines:
  - Headline summary.
  - Bullet-point drivers and risks.
  - Optional structured metadata for UI consumption.
- Add guardrails / validation where needed (length limits, redaction).

## Notes on Shortcuts Taken in Phase 7

- Portfolio and macro structures are deliberately minimal to avoid premature API design.
- Some engines share overlapping responsibilities (strategy vs narrative); Phase 8 should refine boundaries based on user feedback.
- Tests rely on fakes and duck-typing; future work may want typed interfaces once the domain stabilizes.
