# src/slice/memory/workflow.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from slice.ingest import IngestionPipeline
from slice.memory.context_builder import MemoryContextBuilder
from slice.models.observation import Observation
from slice.llm_validation import ValidationResult


@dataclass
class ObservationIngestContext:
    """
    Result of:
      raw dict -> validate -> embed -> insert -> memory recall.
    """
    ok: bool
    errors: List[Any]
    observation_id: str | None
    context_block: str | None
    matches: List[Tuple[Observation, float]]


class ObservationMemoryWorkflow:
    @staticmethod
    def ingest_and_build_context(
        raw: Dict[str, Any],
        k: int = 5,
        max_chars: int = 2000,
    ) -> ObservationIngestContext:
        """
        High-level workflow:

          1) Ingest observation with embedding (validate + insert).
          2) If successful, run semantic recall and build a context block.

        This is what a UI or Copilot layer should call.
        """
        # 1) Ingest (validate + embed + insert)
        res: ValidationResult = IngestionPipeline.ingest_observation_with_embedding(raw)

        if not res.ok or res.model is None:
            return ObservationIngestContext(
                ok=False,
                errors=res.errors,
                observation_id=None,
                context_block=None,
                matches=[],
            )

        obs: Observation = res.model

        # 2) Build context for this text
        ctx = MemoryContextBuilder.build_for_text(
            text=obs.text,
            k=k,
            max_chars=max_chars,
        )

        context_block = ctx.get("context_block")
        matches = ctx.get("matches", [])

        return ObservationIngestContext(
            ok=True,
            errors=[],
            observation_id=obs.id,
            context_block=context_block,
            matches=matches,
        )