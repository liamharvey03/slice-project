from fastapi.testclient import TestClient

from voyager.api.main import app


client = TestClient(app)


def test_ui_portfolio_endpoint_shape():
    resp = client.get("/ui/portfolio")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, dict)
    # From ui_routes: expects portfolio + depth
    assert "portfolio" in data
    assert "depth" in data
    assert isinstance(data["portfolio"], dict)
    assert isinstance(data["depth"], dict)


def test_ui_strategy_context_endpoint_shape():
    resp = client.get("/ui/strategy-context")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, dict)
    # From ui_routes: this should be a strategy context dict
    # We keep assertions loose but non-trivial.
    assert "kind" in data
    assert isinstance(data.get("kind"), str)
    assert "current_portfolio" in data
    assert "risk_profile" in data
    assert "macro_view" in data


def test_ui_diagnostics_context_endpoint_shape():
    resp = client.get("/ui/diagnostics-context")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, dict)
    assert "kind" in data
    assert isinstance(data.get("kind"), str)
    assert "current_portfolio" in data
    assert "risk_profile" in data
    assert "factor_exposures" in data
    assert "stress_tests" in data
    assert "recent_performance" in data


def test_ui_narrative_context_endpoint_shape():
    resp = client.get("/ui/narrative-context")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, dict)
    assert "kind" in data
    assert isinstance(data.get("kind"), str)
    assert "theses" in data
    assert "macro_view" in data
    assert "portfolio_snapshot" in data
    assert "quant_summaries" in data
