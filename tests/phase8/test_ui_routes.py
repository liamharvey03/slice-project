from typing import Any, Dict, List

from fastapi.testclient import TestClient

from slice.api.main import app
import slice.api.ui_routes as ui_routes_mod


class _FakeThesis:
    def __init__(self, thesis_id: int, title: str = "Thesis"):
        self.id = thesis_id
        self.title = title

    def dict(self) -> Dict[str, Any]:
        return {"thesis_id": self.id, "title": self.title}


class _FakeDataAccess:
    """
    Minimal fake implementing the Phase 8 DataAccess surface
    that ui_routes expects.
    """

    def __init__(self):
        self._portfolio = {
            "total_value": 1000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 5, "price": 100.0, "market_value": 500.0},
                {"symbol": "TLT", "quantity": 5, "price": 100.0, "market_value": 500.0},
            ],
        }
        self._depth = {
            "concentration": {"top_name_weight": 0.5},
            "factors": {"equity_beta": 1.0},
            "thesis_exposures": {
                "theses": [
                    {"id": 1, "title": "Thesis 1", "weight": 0.5, "positions": ["AAPL"]},
                    {"id": 2, "title": "Thesis 2", "weight": 0.5, "positions": ["TLT"]},
                ],
                "unassigned": {"weight": 0.0, "positions": []},
            },
        }
        self._risk = {"volatility": 0.15}

    # Legacy getters
    def get_all_theses(self) -> List[_FakeThesis]:
        return [_FakeThesis(1, "Thesis 1"), _FakeThesis(2, "Thesis 2")]

    def get_risk_snapshot(self):
        class _Snap:
            def __init__(self, data: Dict[str, Any]):
                self._data = data

            def dict(self) -> Dict[str, Any]:
                return self._data

        return _Snap(self._risk)

    # Phase 8 getters
    def get_current_portfolio(self) -> Dict[str, Any]:
        return self._portfolio

    def get_portfolio_depth(self, theses) -> Dict[str, Any]:
        return self._depth

    def get_macro_snapshot(self) -> Dict[str, Any]:
        return {"growth": "trend", "inflation": "anchored"}

    def get_regimes(self) -> Dict[str, Any]:
        return {"risk_regime": "calm", "policy_regime": "neutral"}

    def get_quant_summaries(self) -> Dict[str, Any]:
        return {"perf": {"1m": 0.02}, "risk": {"max_dd": -0.05}}


client = TestClient(app)


def _install_fake_data_access(monkeypatch) -> None:
    def _fake_get_da():
        return _FakeDataAccess()

    monkeypatch.setattr(ui_routes_mod, "get_data_access", _fake_get_da)


def test_ui_health():
    resp = client.get("/ui/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ui_portfolio_view(monkeypatch):
    _install_fake_data_access(monkeypatch)

    resp = client.get("/ui/portfolio")
    assert resp.status_code == 200

    data = resp.json()
    assert "portfolio" in data
    assert "depth" in data

    portfolio = data["portfolio"]
    depth = data["depth"]

    assert portfolio["total_value"] == 1000.0
    assert len(portfolio["positions"]) == 2

    assert "concentration" in depth
    assert "factors" in depth
    assert "thesis_exposures" in depth


def test_ui_strategy_context(monkeypatch):
    _install_fake_data_access(monkeypatch)

    resp = client.get("/ui/strategy-context")
    assert resp.status_code == 200
    ctx = resp.json()

    assert ctx["kind"] == "strategy_context"
    assert len(ctx["active_theses"]) == 2
    assert "current_portfolio" in ctx
    assert "risk_profile" in ctx
    assert "macro_view" in ctx


def test_ui_diagnostics_context(monkeypatch):
    _install_fake_data_access(monkeypatch)

    resp = client.get("/ui/diagnostics-context")
    assert resp.status_code == 200
    ctx = resp.json()

    assert ctx["kind"] == "portfolio_diagnostics_context"
    assert "current_portfolio" in ctx
    assert "risk_profile" in ctx
    assert "factor_exposures" in ctx
    assert "thesis_exposures" in ctx
    assert "stress_tests" in ctx
    assert "recent_performance" in ctx


def test_ui_narrative_context(monkeypatch):
    _install_fake_data_access(monkeypatch)

    resp = client.get("/ui/narrative-context")
    assert resp.status_code == 200
    ctx = resp.json()

    assert ctx["kind"] == "narrative_coherence_context"
    assert len(ctx["theses"]) == 2
    assert "macro_view" in ctx
    assert "portfolio_snapshot" in ctx
    assert "quant_summaries" in ctx
