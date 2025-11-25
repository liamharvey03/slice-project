from typing import List

from slice.intelligence.context.data_access import DataAccess


class FakeTrade:
    def __init__(self, symbol, quantity, price, thesis_ref=None):
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.thesis_ref = thesis_ref


class FakeTradeRepo:
    def __init__(self, trades: List[FakeTrade]):
        self._trades = trades

    def list_all(self):
        return self._trades


class FakeThesisRepo:
    def __init__(self, theses):
        self._theses = theses

    def get(self, tid):
        return self._theses.get(tid)

    def get_all(self):
        return list(self._theses.values())


class FakeObsRepo:
    pass


def test_data_access_portfolio_depth_and_macro_regimes():
    trades = [
        FakeTrade("AAPL", 10, 100.0, thesis_ref=1),
        FakeTrade("MSFT", 5, 200.0, thesis_ref=1),
        FakeTrade("TLT", -2, 150.0, thesis_ref=2),
    ]

    theses = {
        1: {"id": 1, "title": "Growth Tech"},
        2: {"id": 2, "title": "Rates Hedge"},
    }

    # DataAccess uses positional args: (thesis_repo, obs_repo, trade_repo)
    da = DataAccess(
        FakeThesisRepo(theses),
        FakeObsRepo(),
        FakeTradeRepo(trades),
    )

    # --- Portfolio snapshot ---
    snap = da.get_current_portfolio()
    assert "positions" in snap and "totals" in snap
    assert len(snap["positions"]) == 3

    # --- Portfolio depth ---
    depth = da.get_portfolio_depth(theses.values())
    assert "concentration" in depth
    assert "factors" in depth
    assert "thesis_exposures" in depth

    conc = depth["concentration"]
    assert conc["largest_weight"] > 0.0

    # --- Macro snapshot & regimes ---
    macro = da.get_macro_snapshot()
    assert "growth" in macro
    assert "inflation" in macro

    regimes = da.get_regimes()
    assert "growth" in regimes
    assert "inflation" in regimes
    assert "liquidity" in regimes
    assert "usd" in regimes

    # --- Quant summaries ---
    qs = da.get_quant_summaries()
    assert "strategies" in qs
    assert isinstance(qs["strategies"], list)
