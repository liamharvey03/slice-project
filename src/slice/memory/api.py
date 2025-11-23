# src/slice/memory/api.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from slice.memory.workflow import ObservationMemoryWorkflow, ObservationIngestContext


def _normalize_categories(categories: Any) -> str:
    """
    Accepts either:
      - None
      - str: "fed, inflation"
      - list/tuple: ["fed", "inflation"]
    Returns a canonical comma-separated string for the validator.
    """
    if categories is None:
        return ""

    if isinstance(categories, str):
        return categories

    if isinstance(categories, (list, tuple)):
        return ", ".join(str(c) for c in categories if str(c).strip())

    return str(categories)


def build_context_for_text(
    text: str,
    thesis_ref: str | None = None,
    sentiment: str = "NEUTRAL",
    categories: Any = None,
    actionable: str = "monitoring",
    k: int = 5,
    max_chars: int = 2000,
) -> ObservationIngestContext:
    """
    High-level helper for the Slice Copilot / internal code:

      text -> validate+embed+insert -> semantic recall -> context.

    Returns an ObservationIngestContext dataclass with:
      - ok / errors
      - observation_id
      - context_block (string)
      - matches: List[(Observation, distance)]
    """
    # Let the validator normalize id, timestamp, etc.
    raw: Dict[str, Any] = {
        "text": text,
        "timestamp": datetime.utcnow().isoformat(),
        "thesis_ref": thesis_ref or "adhoc",
        # Observation model expects enum-like uppercase: "BULLISH", "BEARISH", etc.
        "sentiment": sentiment.upper(),
        "categories": _normalize_categories(categories),
        "actionable": actionable,
    }

    return ObservationMemoryWorkflow.ingest_and_build_context(
        raw=raw,
        k=k,
        max_chars=max_chars,
    )