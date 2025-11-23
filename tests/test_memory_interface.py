import pytest
from slice.memory.interface import get_memory_context_for_text


def test_memory_returns_none_for_k_zero():
    result = get_memory_context_for_text("hello world", 0)
    assert result is None


def test_memory_returns_none_for_empty_text():
    result = get_memory_context_for_text("", 5)
    assert result is None


def test_memory_does_not_raise_errors_for_bad_input():
    try:
        get_memory_context_for_text(None, 5)  # type: ignore
        get_memory_context_for_text(12345, 5)  # type: ignore
        get_memory_context_for_text("valid", -10)
    except Exception as e:
        pytest.fail(f"Function raised an exception: {e}")


def test_memory_structure_when_results_exist(monkeypatch):
    """
    We monkeypatch the underlying MemoryService so we don't need a real DB.
    """
    class FakeResult:
        observation_id = 42
        text = "previous observation"
        thesis_ref = "thesis_abc"
        similarity = 0.88

    class FakeService:
        def recall_similar_text(self, text, k):
            return [FakeResult()]

    # Patch MemoryService inside the interface module
    import slice.memory.interface as interface_module
    monkeypatch.setattr(interface_module, "MemoryService", lambda: FakeService())

    result = get_memory_context_for_text("new text", 3)

    assert result is not None
    assert result["k"] == 3
    assert len(result["items"]) == 1

    first = result["items"][0]
    assert first["observation_id"] == 42
    assert first["text"] == "previous observation"
    assert first["thesis_ref"] == "thesis_abc"
    assert abs(first["similarity"] - 0.88) < 1e-9