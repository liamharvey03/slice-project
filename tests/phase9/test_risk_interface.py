import voyager.risk.interface as ri


class FakeTradeRepoNoTrades:
    """
    Fake TradeRepository for the 'no trades' case.
    Must accept arbitrary init args because the real code may pass config/engine.
    """

    def __init__(self, *args, **kwargs):
        pass

    def list_for_thesis(self, *args, **kwargs):
        return []

    def list_for_portfolio(self, *args, **kwargs):
        return []

    def list_all(self, *args, **kwargs):
        return []


class FakeTradeRepoWithTrades:
    """
    Fake TradeRepository that returns at least one 'trade' object.
    We don't care about the trade fields; current risk stub ignores them anyway.
    """

    class DummyTrade:
        def __init__(self, symbol="AAPL"):
            self.symbol = symbol

    def __init__(self, *args, **kwargs):
        pass

    def list_for_thesis(self, *args, **kwargs):
        return [self.DummyTrade()]

    def list_for_portfolio(self, *args, **kwargs):
        return [self.DummyTrade()]

    def list_all(self, *args, **kwargs):
        return [self.DummyTrade()]


def test_get_snapshot_returns_none_when_no_trades(monkeypatch):
    monkeypatch.setattr(ri, "TradeRepository", FakeTradeRepoNoTrades)

    snapshot = ri.get_snapshot()
    assert snapshot is None


def test_get_snapshot_still_returns_none_when_trades_exist(monkeypatch):
    monkeypatch.setattr(ri, "TradeRepository", FakeTradeRepoWithTrades)

    snapshot = ri.get_snapshot()
    assert snapshot is None


def test_render_risk_snapshot_text_on_manual_snapshot():
    # Construct a minimal valid RiskSnapshot for the current schema.
    snapshot = ri.RiskSnapshot(
        book_gross=0.0,
        book_net=0.0,
        exposures=[],
        backtests=[],
    )

    text = ri.render_risk_snapshot_text(snapshot)
    assert isinstance(text, str)
    assert "[RISK SNAPSHOT]" in text
    lower = text.lower()
    assert "gross" in lower
    assert "net" in lower
