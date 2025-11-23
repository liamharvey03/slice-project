from src.slice.risk.interface import (
    RiskSnapshot,
    get_snapshot,
    render_risk_snapshot_text,
)


def test_render_snapshot_text_deterministic():
    snap = RiskSnapshot(
        book_gross=100,
        book_net=50,
        duration=3.0,
        dv01=12000,
        exposures=[{"asset": "GLD", "size": 10, "direction": "LONG", "weight": 0.2}],
        backtests=[{
            "strategy": "mean_reversion",
            "total_return": 0.12,
            "max_drawdown": -0.05,
            "volatility": 0.18,
            "win_rate": 0.62,
        }],
    )

    text1 = render_risk_snapshot_text(snap)
    text2 = render_risk_snapshot_text(snap)

    assert text1 == text2
    assert "Book Gross" in text1
    assert "Exposures:" in text1
    assert "Backtests:" in text1


def test_get_snapshot_no_trades_returns_none(monkeypatch):
    # Monkeypatch trade repo to simulate no trades
    class DummyRepo:
        @staticmethod
        def list_all():
            return []

    monkeypatch.setattr(
        "src.slice.repositories.trade_repo.TradeRepository", DummyRepo
    )

    result = get_snapshot()
    assert result is None