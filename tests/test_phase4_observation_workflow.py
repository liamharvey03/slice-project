from datetime import datetime

from slice.memory.workflow import ObservationMemoryWorkflow


def test_observation_ingest_and_context_smoke():
    raw = {
        "text": "Fed outlook is becoming more hawkish due to sticky inflation.",
        "timestamp": datetime.utcnow().isoformat(),
        "thesis_ref": "fed_rates",
        "sentiment": "BEARISH",
        "categories": "fed, inflation",
        "actionable": "monitoring",
    }

    res = ObservationMemoryWorkflow.ingest_and_build_context(raw, k=3, max_chars=500)

    assert res.ok
    assert res.observation_id is not None
    assert isinstance(res.context_block, str)