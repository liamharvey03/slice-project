from typing import Optional, Dict, Any, List
from .service import MemoryService  # Phase 4 recall engine


def get_memory_context_for_text(text: str, k: int) -> Optional[dict]:
    """
    Phase 5 Memory Interface – Dev B implements.

    Must return:
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

    Return None on:
    - no results
    - recall errors
    - k <= 0

    Never raise exceptions. Always return JSON-serializable primitives.
    """

    # Rule: if k is zero or negative → no recall
    if k <= 0:
        return None

    try:
        # Phase 4 recall engine
        service = MemoryService()

        # This function is guaranteed by Phase 4:
        # returns a list of recall items with similarity scores.
        raw_items: List[Any] = service.recall_similar_text(text=text, k=k)

        # If no results → per spec return None (NOT empty dict)
        if not raw_items:
            return None

        items: List[Dict[str, Any]] = []

        for raw in raw_items:
            # Handle both dict-like and object-like results
            if isinstance(raw, dict):
                observation_id = raw.get("observation_id")
                text_value = raw.get("text") or raw.get("content") or ""
                thesis_ref = raw.get("thesis_ref") or raw.get("thesis_id") or ""
                similarity = raw.get("similarity") or raw.get("score") or 0.0
            else:
                observation_id = getattr(raw, "observation_id", None)
                text_value = getattr(raw, "text", "") or getattr(raw, "content", "")
                thesis_ref = getattr(raw, "thesis_ref", "") or getattr(raw, "thesis_id", "")
                similarity = getattr(raw, "similarity", None) or getattr(raw, "score", 0.0)

            # Skip malformed entries
            if observation_id is None:
                continue

            items.append(
                {
                    "observation_id": int(observation_id),
                    "text": str(text_value),
                    "thesis_ref": str(thesis_ref),
                    "similarity": float(similarity),
                }
            )

        # Edge case: all entries filtered out → treat as no memory
        if not items:
            return None

        return {
            "k": k,
            "items": items,
        }

    except Exception:
        # Spec: must never raise errors outward
        return None