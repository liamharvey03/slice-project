from typing import List

from voyager.intelligence.context.context_builder import ContextBuilder
from voyager.intelligence.context.data_access import DataAccess


class FakeThesis:
    def __init__(self, tid, title):
        self.id = tid
        self.title = title

    def dict(self):
        return {"id": self.id, "title": self.title}


class FakeRiskSnapshot:
    def dict(self):
        return {"book_gross": 1.0}


class FakeThesisRepo:
    def __init__(self, theses):
        self._theses = theses

    def list_all(self):
        return list(self._theses.values())

    def get_by_id(self, tid):
        return self._theses.get(tid)


class FakeObsRepo:
    def list_for_thesis(self, tid):
        return []

    def list_recent(self, limit):
        return []


class FakeTradeRepo:
    def list_all(self):
        return []


class DummyDataAccess(DataAccess):
    def __init__(self):
        super().__init__(
            thesis_repo=FakeThesisRepo({1: FakeThesis(1, "Test")}),
            obs_repo=FakeObsRepo(),
            trade_repo=FakeTradeRepo(),
        )

    def get_risk_snapshot(self):
        return FakeRiskSnapshot()

    def get_current_portfolio(self):
        return {"positions": [], "totals": {"portfolio_value": 0.0}}

    def get_portfolio_depth(self, theses: List[FakeThesis]):
        return {
            "concentration": {},
            "factors": {},
            "thesis_exposures": {"theses": [], "unassigned": {"weight": 0.0, "positions": []}},
        }

    def get_macro_snapshot(self):
        return {"growth": {}, "inflation": {}, "rates": {}, "liquidity": {}, "fx": {}}

    def get_regimes(self):
        return {"growth": "unknown", "inflation": "unknown", "liquidity": "unknown", "usd": "unknown"}

    def get_quant_summaries(self):
        return {"strategies": [], "scenarios": [], "risk_flags": []}


def test_context_builder_phase8_helpers_smoke():
    da = DummyDataAccess()
    cb = ContextBuilder(da)

    strat_ctx = cb.build_strategy_context_from_data()
    assert strat_ctx["kind"] == "strategy_context"
    assert "current_portfolio" in strat_ctx
    assert "macro_view" in strat_ctx

    diag_ctx = cb.build_portfolio_diagnostics_context_from_data()
    assert diag_ctx["kind"] == "portfolio_diagnostics_context"
    assert "thesis_exposures" in diag_ctx

    narr_ctx = cb.build_narrative_coherence_context_from_data(window_label="test_window")
    assert narr_ctx["kind"] == "narrative_coherence_context"
    assert "macro_view" in narr_ctx
    assert "portfolio_snapshot" in narr_ctx
