from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

from slice.models.observation import Observation
from slice.memory.retrieval import search_similar_observations


@dataclass
class MemoryItem:
    """
    Normalized representation of a recalled observation for use in prompts.
    """
    id: str
    text: str
    categories: List[str]
    sentiment: str
    thesis_ref: List[str]
    distance: float

    @classmethod
    def from_observation(cls, obs: Observation, distance: float) -> "MemoryItem":
        # obs.categories is already a list[str] from the retrieval layer
        cats = list(obs.categories) if isinstance(obs.categories, (list, tuple)) else []

        # obs.thesis_ref is typically list[str] (text[] in DB), but may be None
        if isinstance(obs.thesis_ref, (list, tuple)):
            thesis_ref = list(obs.thesis_ref)
        elif isinstance(obs.thesis_ref, str):
            thesis_ref = [obs.thesis_ref]
        else:
            thesis_ref = []

        sentiment_str = (
            obs.sentiment.value if hasattr(obs.sentiment, "value") else str(obs.sentiment)
        )

        return cls(
            id=obs.id,
            text=obs.text,
            categories=cats,
            sentiment=sentiment_str,
            thesis_ref=thesis_ref,
            distance=distance,
        )


class MemoryContextBuilder:
    """
    Builds structured memory bundles suitable for LLM prompts.

    It does NOT talk to OpenAI itself – it just calls the vector search layer
    and formats the results.
    """

    @staticmethod
    def build_for_text(
        text: str,
        k: int = 5,
        since: Optional[str] = None,
        until: Optional[str] = None,
        categories: Optional[List[str]] = None,
        sentiment: Optional[str] = None,
        max_chars: int = 3000,
    ) -> Dict[str, Any]:
        """
        Generic entrypoint: recall observations semantically related to
        arbitrary text (thesis, observation draft, etc.).

        Returns a dict that can be passed directly into an LLM prompt builder.
        """
        matches: List[Tuple[Observation, float]] = search_similar_observations(
            query_text=text,
            k=k,
            since=since,
            until=until,
            categories=categories,
            sentiment=sentiment,
        )

        items: List[MemoryItem] = [
            MemoryItem.from_observation(obs, dist) for obs, dist in matches
        ]

        # Build a compact text block to attach in prompts
        context_block = MemoryContextBuilder._format_memory_block(items, max_chars=max_chars)

        return {
            "query_text": text,
            "items": items,
            "context_block": context_block,
        }

    @staticmethod
    def build_for_observation(
        obs: Observation,
        k: int = 5,
        max_chars: int = 3000,
    ) -> Dict[str, Any]:
        """
        Convenience wrapper when you already have an Observation model and want
        similar ones to show in the UI or LLM prompt.
        """
        categories = (
            list(obs.categories)
            if isinstance(obs.categories, (list, tuple))
            else None
        )

        sentiment = (
            obs.sentiment.value if hasattr(obs.sentiment, "value") else str(obs.sentiment)
        )

        return MemoryContextBuilder.build_for_text(
            text=obs.text,
            k=k,
            categories=categories,
            sentiment=sentiment.lower(),
            max_chars=max_chars,
        )

    @staticmethod
    def build_for_thesis(
        thesis_title: str,
        thesis_hypothesis: str,
        k: int = 10,
        max_chars: int = 4000,
    ) -> Dict[str, Any]:
        """
        Use thesis title + hypothesis as a query to retrieve relevant observations.
        """
        query = f"{thesis_title}. {thesis_hypothesis}".strip()
        return MemoryContextBuilder.build_for_text(
            text=query,
            k=k,
            max_chars=max_chars,
        )

    # --------------------------------------------------------------------- #
    # Internal formatting helpers
    # --------------------------------------------------------------------- #

    @staticmethod
    def _format_memory_block(items: List[MemoryItem], max_chars: int) -> str:
        """
        Turn memory items into a compact, deterministic text block that can be
        appended to an LLM prompt. Uses a simple char-budget clip instead of
        tokens to keep it robust and cheap.
        """
        if not items:
            return ""

        lines: List[str] = []
        lines.append("Relevant prior observations:")

        for item in items:
            # One block per memory item
            block = (
                f"- id: {item.id}\n"
                f"  distance: {item.distance:.4f}\n"
                f"  categories: {', '.join(item.categories) if item.categories else '[]'}\n"
                f"  sentiment: {item.sentiment}\n"
                f"  thesis_ref: {', '.join(item.thesis_ref) if item.thesis_ref else '[]'}\n"
                f"  text: {item.text}\n"
            )
            lines.append(block)

        full = "\n".join(lines)

        if len(full) <= max_chars:
            return full

        # Naive truncation from the end; keeps the oldest lines of context
        return full[:max_chars] + "\n...[truncated memory context]..."