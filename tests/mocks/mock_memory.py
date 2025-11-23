def fake_memory_context():
    return {
        "k": 2,
        "items": [
            {
                "observation_id": 999,
                "text": "Mock memory observation #1",
                "thesis_ref": "mock_thesis",
                "similarity": 0.99
            },
            {
                "observation_id": 1000,
                "text": "Mock memory observation #2",
                "thesis_ref": "mock_thesis_2",
                "similarity": 0.95
            },
        ],
    }


def mock_get_memory_context_for_text(text, k):
    return fake_memory_context()