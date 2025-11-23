from enum import Enum
from typing import Optional, Dict, Any

from pydantic import BaseModel


class SessionMode(str, Enum):
    STANDARD = "STANDARD"
    ANALYST = "ANALYST"
    CONCISE = "CONCISE"


class SessionOptions(BaseModel):
    mode: SessionMode = SessionMode.STANDARD
    use_memory: bool = True
    use_risk: bool = True

    # Memory recall limit
    max_memory_items: int = 5

    # Risk scoping
    risk_for_thesis_id: Optional[str] = None
    risk_for_portfolio_id: Optional[str] = None


class SessionResponse(BaseModel):
    observation_id: int
    llm_response: str

    memory_context: Optional[Dict[str, Any]] = None
    risk_snapshot: Optional[Dict[str, Any]] = None

    # LLM accounting / observability
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None