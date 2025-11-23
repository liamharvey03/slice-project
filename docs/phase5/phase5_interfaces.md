
⸻

Phase 5 – Public Interfaces Specification

Authoritative contract for Dev A & Dev B
Do not modify without explicit agreement between both developers.

⸻

1. Purpose

Phase 5 introduces the Session Layer – a unifying orchestrator that:
	•	Ingests a user message as an Observation,
	•	Retrieves semantic memory via the Phase 4 memory system,
	•	Retrieves a structured snapshot of quantitative Risk,
	•	Builds deterministic LLM prompts,
	•	Calls the LLM engine,
	•	Returns a structured SessionResponse for the API/UI.

This document defines the public interfaces required to implement that behavior.

Everything in this file is authoritative.

⸻

2. SessionMode

from enum import Enum

class SessionMode(str, Enum):
    STANDARD = "STANDARD"
    ANALYST = "ANALYST"   # deeper quantitative reasoning, no autonomy
    CONCISE = "CONCISE"   # shorter outputs

	•	This mode is passed through SessionOptions and influences prompt-building.
	•	No functional branching beyond prompt construction and LLM config.

⸻

3. SessionOptions

from pydantic import BaseModel
from typing import Optional

class SessionOptions(BaseModel):
    mode: SessionMode = SessionMode.STANDARD
    use_memory: bool = True
    use_risk: bool = True

    # optional knobs – these may be ignored by some prompt modes
    max_memory_items: int = 5
    risk_for_thesis_id: Optional[str] = None
    risk_for_portfolio_id: Optional[str] = None

Semantic rules:
	•	use_memory=False → orchestrator must pass memory_ctx=None.
	•	use_risk=False → orchestrator must pass risk_ctx=None.
	•	If both risk_for_thesis_id and risk_for_portfolio_id are None,
the risk layer performs a default snapshot (i.e., top-level book + active trades).
	•	max_memory_items controls the k parameter when requesting memory context.

⸻

4. SessionResponse

This is the object returned by:
	•	SessionOrchestrator.run_session
	•	/api/v1/session/step

from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class SessionResponse(BaseModel):
    observation_id: int
    llm_response: str

    memory_context: Optional[Dict[str, Any]] = None
    risk_snapshot: Optional[Dict[str, Any]] = None

    # for observability
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None

Semantic rules:
	•	memory_context must be the raw dict returned by the memory wrapper.
	•	risk_snapshot must be a pure dict representation of RiskSnapshot (below).
	•	If memory/risk is disabled by options → these fields are None.

⸻

5. Memory Interface – Dev B owns implementation

This is the exact signature Dev B must provide.

File: src/slice/memory/interface.py

from typing import Optional

def get_memory_context_for_text(text: str, k: int) -> Optional[dict]:
    """
    Return a dictionary representing the semantic memory context for the given text,
    using Phase 4’s embedding + recall workflow.

    Return None if:
      - no matching memories,
      - the memory system is disabled,
      - or an internal error occurs.

    Must NOT raise exceptions to the caller.
    Must NOT return Pydantic models; return a simple JSON-serializable dict.
    """
    ...

Behavior rules:
	•	The wrapper must route through Phase 4’s ObservationMemoryWorkflow or equivalent, not bypass DB or raw embeddings.
	•	Output schema must follow Phase 4 memory response structure:

{
    "k": int,
    "items": [
        {
            "observation_id": int,
            "text": str,
            "thesis_ref": str,
            "similarity": float
        },
        ...
    ]
}

	•	If no items → return None, not an empty dict.

⸻

6. Risk Interface – Dev A implements

File: src/slice/risk/interface.py

6.1 RiskSnapshot

from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class RiskSnapshot(BaseModel):
    # top-level book metrics (portfolio-level risk)
    book_gross: float
    book_net: float
    duration: Optional[float] = None
    dv01: Optional[float] = None

    # per-asset or per-trade exposures
    exposures: List[Dict[str, Any]]

    # related backtests or diagnostics (Phase 4 artifacts)
    backtests: List[Dict[str, Any]]

6.2 get_snapshot

from typing import Optional

def get_snapshot(thesis_id: Optional[str] = None,
                 portfolio_id: Optional[str] = None) -> Optional[RiskSnapshot]:
    """
    Retrieve a structured, quantitative RiskSnapshot.

    Rules:
    - If thesis_id provided -> snapshot scoped to trades linked to that thesis.
    - If portfolio_id provided -> snapshot scoped to that portfolio.
    - If neither provided -> snapshot for the top-level book.
    - Must return None (not exception) if:
        * no valid trades,
        * no risk data,
        * risk system disabled,
        * or repository errors.

    Data MUST come from existing Phase 4 repositories:
        - RiskReport
        - BacktestResult
        - TradeRepository
    """
    ...

6.3 render_risk_snapshot_text

def render_risk_snapshot_text(snapshot: RiskSnapshot) -> str:
    """
    Deterministic, fully non-LLM rendering of the risk snapshot as text.
    Used directly in the LLM prompt.

    Format (example structure):
    - Book Gross / Net
    - Duration / DV01 (if available)
    - Exposures (asset, direction, size)
    - Backtests: win rate, max drawdown, PnL summary

    Must produce clean, fixed-order, stable text with no randomness.
    """
    ...


⸻

7. Session Orchestrator – Dev A implements

File: src/slice/session/orchestrator.py

7.1 Class + signature

class SessionOrchestrator:

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def run_session(self, text: str, options: SessionOptions) -> SessionResponse:
        """
        Main entrypoint for Phase 5.

        Steps:
        1. Ingest new Observation via existing Phase 4 ingestion pipeline.
        2. If options.use_memory:
               memory_ctx = get_memory_context_for_text(text, k=options.max_memory_items)
           Else:
               memory_ctx = None
        3. If options.use_risk:
               snapshot = get_snapshot(
                   thesis_id=options.risk_for_thesis_id,
                   portfolio_id=options.risk_for_portfolio_id
               )
               risk_ctx = snapshot.dict() if snapshot else None
           Else:
               risk_ctx = None
        4. Build deterministic LLM messages via build_prompt(memory_ctx, risk_ctx, text, options)
        5. Call llm_client with strict config (temperature=0 or specified mode)
        6. Construct SessionResponse with:
               - observation_id
               - llm_response
               - memory_context
               - risk_snapshot
               - token counts & latency (from LLM client)
        7. Call log_session_event(...) (non-blocking, swallow errors)
        """
        ...


⸻

8. Prompt Builder – Dev A implements

File: src/slice/session/prompts.py

from typing import List, Dict, Any

def build_prompt(memory_ctx: Optional[dict],
                 risk_ctx: Optional[dict],
                 user_text: str,
                 options: SessionOptions) -> List[Dict[str, str]]:
    """
    Return a list of messages for the LLM:
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": full_compiled_prompt},
        ]

    Deterministic construction:
        - Always show memory block first (if not None)
        - Always show risk block second (if not None)
        - Always show user text last
        - Mode-specific headers (STANDARD, ANALYST, CONCISE)
    """
    ...

SYSTEM_PROMPT must include:
	•	Non-autonomy rules (LLM never computes metrics).
	•	Deterministic behavior.
	•	Reliance only on provided memory/risk blocks.
	•	No hallucinated portfolio objects.
	•	No price predictions, no risk calculations.

⸻

9. Logging Interface – Dev A implements

File: src/slice/session/logging.py

def log_session_event(
    observation_id: int,
    llm_model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    memory_used: bool,
    risk_used: bool,
):
    """
    Non-blocking logging to DB or file.
    Must never raise to the orchestrator.
    """
    ...


⸻

10. FastAPI Endpoint – Dev A implements

File: src/slice/api/session_routes.py

@router.post("/api/v1/session/step", response_model=SessionResponse)
async def session_step(payload: dict):
    """
    Payload:
        {
            "text": "...",
            "options": {...}
        }

    Behavior:
        - Parse text + SessionOptions
        - Instantiate SessionOrchestrator
        - Return SessionResponse
    """


⸻

11. Test Requirements

Dev A must provide:
	•	Unit tests for:
	•	build_prompt
	•	render_risk_snapshot_text
	•	get_snapshot (using fixed fixtures)
	•	SessionOrchestrator.run_session (with mocked memory + risk + LLM)
	•	/api/v1/session/step FastAPI route

Dev B must provide:
	•	Unit tests for memory wrapper:
	•	get_memory_context_for_text
	•	Correct integration with Phase 4’s memory system
	•	Deterministic ordering + shape of returned dict

⸻

12. Non-Negotiable Rules
	1.	LLMs do not compute risk, returns, backtests, greeks, or signals.
	2.	Repositories must be used for all DB interactions.
	3.	Output must be JSON-serializable.
	4.	Prompt assembly must be deterministic.
	5.	Memory and risk sections appear in a fixed order if present:
	1.	Memory
	2.	Risk
	3.	User text

⸻

END OF SPECIFICATION