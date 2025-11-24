# Phase 7 Completion – Intelligence Layer

## Scope

Phase 7 extends the intelligence layer with:

- Long-horizon reasoning engine
- Strategy recommendation engine
- Portfolio diagnostics engine
- Narrative coherence engine

All engines:

- Live under `src/slice/intelligence/`
- Use `ContextBuilder` for deterministic context assembly
- Call `OrchestratorClient` (`run_analyst`) and return `SessionResponse`
- Are exposed via `/api/v1/intel/*` FastAPI routes

## Engines and Contexts

### Long-horizon analysis

- File: `src/slice/intelligence/long_horizon.py`
- Entry: `run_long_horizon_analysis(...)`
- Context builder: `ContextBuilder.build_long_horizon_context(...)`
- Route: `POST /api/v1/intel/horizon`
- Purpose: multi-month macro path reasoning for a single thesis.

### Strategy recommendation

- File: `src/slice/intelligence/strategy.py`
- Entry: `run_strategy_recommendation(...)`
- Context builder: `ContextBuilder.build_strategy_context(...)`
- Route: `POST /api/v1/intel/strategy`
- Purpose: high-level portfolio strategy guidance from theses + risk snapshot.

### Portfolio diagnostics

- File: `src/slice/intelligence/portfolio_diagnostics.py`
- Entry: `run_portfolio_diagnostics(...)`
- Context builder: `ContextBuilder.build_portfolio_diagnostics_context(...)`
- Route: `POST /api/v1/intel/diagnostics`
- Purpose: summarize portfolio risk/exposures and flag concentrations.

### Narrative coherence

- File: `src/slice/intelligence/narrative.py`
- Entry: `run_narrative_coherence(...)`
- Context builder: `ContextBuilder.build_narrative_coherence_context(...)`
- Route: `POST /api/v1/intel/narrative`
- Purpose: produce a coherent macro + portfolio narrative across theses.

## API Surface

All routes are mounted under `/api/v1/intel` in `src/slice/api/intelligence_routes.py`.

Legacy Phase 6 routes remain unchanged:

- `/thesis/review`
- `/thesis/consistency`
- `/qa`
- `/commentary/daily`
- `/commentary/weekly`

Phase 7 adds:

- `/horizon`
- `/strategy`
- `/diagnostics`
- `/narrative`

## Tests

Phase 7 tests live under `tests/phase7`:

- `test_long_horizon.py`
- `test_strategy.py`
- `test_portfolio_diagnostics.py`
- `test_narrative.py`
- `test_phase7_workflows.py`

Phase 4–6 tests remain under `tests/phase4`, `tests/phase5`, `tests/phase6`.

## Known Limitations

- Portfolio structure, factor exposures, and performance are stubs; they are modeled as dicts with extension points.
- Macro view is currently derived from risk snapshot only; no external macro feeds are wired.
- FastAPI dependencies for `DataAccess` and `OrchestratorClient` (`.depends`) are placeholders and must be wired in production.
