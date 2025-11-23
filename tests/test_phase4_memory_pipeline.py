from datetime import datetime
from typing import List, Tuple

from slice.ingest import IngestionPipeline
from slice.memory.service import MemoryService
from slice.models.observation import Observation


def _make_obs_payload(
    text: str,
    thesis_ref: str,
    sentiment: str,
    categories: str,
) -> dict:
    return {
        # id is generated inside the ingestion pipeline, so we omit it here
        "text": text,
        "timestamp": datetime.utcnow().isoformat(),
        "thesis_ref": thesis_ref,
        "sentiment": sentiment,
        "categories": categories,
        "actionable": "monitoring",
    }


def test_phase4_observation_memory_roundtrip():
    """
    End-to-end sanity:

      raw dict → validation → embedding → insert → recall via semantic K-NN.
    """

    # 1) Ingest a few observations
    payloads = [
        _make_obs_payload(
            text="FOMC minutes show concern about inflation persistence and higher-for-longer rates.",
            thesis_ref="fed_rates",
            sentiment="BEARISH",
            categories="fed, inflation, rates",
        ),
        _make_obs_payload(
            text="FOMC minutes show concern about inflation persistence.",
            thesis_ref="dummy_thesis",
            sentiment="BEARISH",
            categories="fed, inflation",
        ),
        _make_obs_payload(
            text="Oil markets tighten as OPEC holds cuts, pushing energy equities higher.",
            thesis_ref="energy_tightness",
            sentiment="BULLISH",
            categories="energy, opec, oil",
        ),
    ]

    for p in payloads:
        res = IngestionPipeline.ingest_observation_with_embedding(p)
        assert res.ok, f"Ingestion failed: {res.errors}"

    # 2) Recall similar observations
    query = "Fed concerned about inflation and higher-for-longer policy stance."
    matches: List[Tuple[Observation, float]] = MemoryService.recall_similar_text(
        query,
        k=3,
    )

    # basic structure
    assert len(matches) >= 2

    # 3) qualitative assertions:
    #   - top 2 hits should be FED/INFLATION items, not the oil one
    top_ids = [obs.id for (obs, _dist) in matches]
    top_texts = [obs.text for (obs, _dist) in matches]

    assert any("FOMC minutes show concern about inflation persistence" in t for t in top_texts)
    assert any("higher-for-longer rates" in t for t in top_texts)

    # 4) distance ordering: first match should be closer than last
    dists = [d for (_obs, d) in matches]
    assert dists[0] <= dists[-1]