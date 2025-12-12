# Dev B – Memory Wrapper Implementation Notes (Phase 5)

This file documents the implementation of the required Phase 5 memory interface:

**File:** `src/slice/memory/interface.py`  
**Function:** `get_memory_context_for_text(text: str, k: int) -> Optional[dict]`

## 1. Purpose

The memory wrapper provides the Session Orchestrator with a deterministic,
JSON-serializable memory block using the Phase 4 semantic recall system.

It performs:
1. Validation (`k > 0`)
2. Phase 4 semantic recall via `MemoryService.recall_similar_text`
3. Normalization into the Phase 5-required schema
4. Full exception-swallowing (returns None on any error)

## 2. Exact Output Schema (from Phase 5 spec)

```json
{
  "k": 5,
  "items": [
    {
      "observation_id": 123,
      "text": "Original observation text...",
      "thesis_ref": "thesis_xyz",
      "similarity": 0.92
    }
  ]
}