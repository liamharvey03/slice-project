# src/slice/api/memory_app.py

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from slice.memory.api import build_context_for_text


app = FastAPI(title="Slice Memory API", version="0.1.0")


class ObservationRequest(BaseModel):
    text: str
    thesis_ref: Optional[str] = None
    sentiment: str = "NEUTRAL"
    categories: Optional[List[str]] = None
    actionable: str = "monitoring"
    k: int = 5
    max_chars: int = 2000


class Match(BaseModel):
    id: str
    distance: float
    text: str
    categories: List[str]
    sentiment: str
    thesis_ref: List[str]


class MemoryResponse(BaseModel):
    ok: bool
    errors: List[str]
    observation_id: Optional[str]
    context_block: Optional[str]
    matches: List[Match]


@app.post("/api/v1/memory/observe_and_recall", response_model=MemoryResponse)
def observe_and_recall(req: ObservationRequest) -> MemoryResponse:
    # Normalize categories to pass into build_context_for_text
    categories = req.categories or []

    ctx = build_context_for_text(
        text=req.text,
        thesis_ref=req.thesis_ref,
        sentiment=req.sentiment,
        categories=categories,
        actionable=req.actionable,
        k=req.k,
        max_chars=req.max_chars,
    )

    # Convert errors (ValidationIssue objects, etc.) to strings for JSON
    errors_str: List[str] = [str(e) for e in ctx.errors] if ctx.errors else []

    matches: List[Match] = []
    for obs, dist in ctx.matches:
        matches.append(
            Match(
                id=obs.id,
                distance=float(dist),
                text=obs.text,
                categories=list(obs.categories),
                sentiment=obs.sentiment.value
                if hasattr(obs.sentiment, "value")
                else str(obs.sentiment),
                thesis_ref=list(obs.thesis_ref),
            )
        )

    return MemoryResponse(
        ok=ctx.ok,
        errors=errors_str,
        observation_id=ctx.observation_id,
        context_block=ctx.context_block,
        matches=matches,
    )