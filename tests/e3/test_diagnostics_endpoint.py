"""
E3: Tests for diagnostics API endpoint.

Verifies:
- Endpoint returns stable shape with all four tool keys
- Metrics are correctly serialized
- All keys present even when counts are zero
"""
import pytest
from fastapi.testclient import TestClient

from slice.api.main import app
from slice.llm.metrics import llm_stats, reset_stats, record_llm_call


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_diagnostics_endpoint_returns_all_keys(client):
    """All four tool keys are present in response."""
    reset_stats()

    response = client.get("/api/v1/diagnostics/llm")

    assert response.status_code == 200
    data = response.json()

    assert "llm_tool_metrics" in data
    metrics = data["llm_tool_metrics"]

    expected_tools = {"thesis_review", "cross_theses", "intuition_qa", "daily_summary"}
    assert set(metrics.keys()) == expected_tools


def test_diagnostics_endpoint_zero_counts(client):
    """Zero counts are correctly returned."""
    reset_stats()

    response = client.get("/api/v1/diagnostics/llm")
    data = response.json()
    metrics = data["llm_tool_metrics"]

    for tool_name in metrics:
        tool_metrics = metrics[tool_name]
        assert tool_metrics["calls"] == 0
        assert tool_metrics["errors"] == 0
        assert tool_metrics["avg_latency_ms"] == 0.0


def test_diagnostics_endpoint_reflects_actual_metrics(client):
    """Endpoint reflects actual metrics after some calls."""
    reset_stats()

    # Make some calls
    record_llm_call("thesis_review", latency_ms=100, success=True)
    record_llm_call("thesis_review", latency_ms=200, success=False)
    record_llm_call("intuition_qa", latency_ms=150, success=True)

    response = client.get("/api/v1/diagnostics/llm")
    data = response.json()
    metrics = data["llm_tool_metrics"]

    # Check thesis_review
    thesis_review = metrics["thesis_review"]
    assert thesis_review["calls"] == 2
    assert thesis_review["errors"] == 1
    assert thesis_review["avg_latency_ms"] == 150.0  # (100 + 200) / 2

    # Check intuition_qa
    intuition_qa = metrics["intuition_qa"]
    assert intuition_qa["calls"] == 1
    assert intuition_qa["errors"] == 0
    assert intuition_qa["avg_latency_ms"] == 150.0

    # Check other tools are still zero
    assert metrics["cross_theses"]["calls"] == 0
    assert metrics["daily_summary"]["calls"] == 0


def test_diagnostics_endpoint_stable_shape(client):
    """Response shape is stable regardless of metrics state."""
    reset_stats()

    response1 = client.get("/api/v1/diagnostics/llm")
    data1 = response1.json()

    # Make some calls
    record_llm_call("thesis_review", latency_ms=100, success=True)

    response2 = client.get("/api/v1/diagnostics/llm")
    data2 = response2.json()

    # Both should have same top-level structure
    assert set(data1.keys()) == set(data2.keys())
    assert set(data1["llm_tool_metrics"].keys()) == set(data2["llm_tool_metrics"].keys())

    # Each tool should have same keys
    for tool_name in data1["llm_tool_metrics"]:
        tool1 = data1["llm_tool_metrics"][tool_name]
        tool2 = data2["llm_tool_metrics"][tool_name]
        assert set(tool1.keys()) == set(tool2.keys())
        assert set(tool1.keys()) == {"calls", "errors", "avg_latency_ms"}

