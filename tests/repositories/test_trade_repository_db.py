import datetime as dt

import pytest

from voyager.models.common import TradeType
from voyager.models.trade import Trade
from voyager.repositories.trade_repo import TradeRepository


# Use the first defined enum value as the default type so we don't depend on
# any specific variant name (CASH, SPOT, etc.).
DEFAULT_TRADE_TYPE = list(TradeType)[0]


def _make_trade(
    trade_id: str,
    ts: dt.datetime,
    asset: str = "SPY",
    action: str = "BUY",
    quantity: float = 10.0,
    price: float = 100.0,
    trade_type: TradeType = DEFAULT_TRADE_TYPE,
    thesis_ref: str | None = None,
    notes: str = "",
) -> Trade:
    return Trade(
        trade_id=trade_id,
        timestamp=ts,
        asset=asset,
        action=action,
        quantity=quantity,
        price=price,
        type=trade_type,
        thesis_ref=thesis_ref,
        notes=notes,
    )


@pytest.mark.usefixtures("clean_core_tables")
def test_insert_and_list_all_roundtrip(db_engine):
    repo = TradeRepository(engine=db_engine)

    t1 = _make_trade(
        trade_id="tr1",
        ts=dt.datetime(2025, 1, 1, 10, 0, 0),
        asset="SPY",
        action="BUY",
        quantity=5.0,
        price=400.0,
        thesis_ref="thesis-1",
        notes="first trade",
    )
    t2 = _make_trade(
        trade_id="tr2",
        ts=dt.datetime(2025, 1, 1, 11, 0, 0),
        asset="TLT",
        action="SELL",
        quantity=3.0,
        price=100.0,
        thesis_ref="thesis-2",
        notes="second trade",
    )

    repo.insert(t1)
    repo.insert(t2)

    all_trades = repo.list_all()
    ids = [t.trade_id for t in all_trades]

    # list_all is ordered by timestamp ASC, trade_id ASC
    assert ids == ["tr1", "tr2"]

    # basic field integrity check
    loaded_t1 = all_trades[0]
    assert loaded_t1.asset == "SPY"
    assert loaded_t1.quantity == 5.0
    assert loaded_t1.price == 400.0
    assert isinstance(loaded_t1.type, TradeType)
    assert loaded_t1.thesis_ref == "thesis-1"


@pytest.mark.usefixtures("clean_core_tables")
def test_list_by_thesis_filters_and_orders_desc(db_engine):
    repo = TradeRepository(engine=db_engine)

    # Older trade linked to t1
    t1 = _make_trade(
        trade_id="tr1",
        ts=dt.datetime(2025, 1, 1, 9, 0, 0),
        asset="SPY",
        action="BUY",
        quantity=5.0,
        price=400.0,
        thesis_ref="t1",
    )
    # Newer trade also linked to t1
    t2 = _make_trade(
        trade_id="tr2",
        ts=dt.datetime(2025, 1, 1, 12, 0, 0),
        asset="SPY",
        action="SELL",
        quantity=2.0,
        price=410.0,
        thesis_ref="t1",
    )
    # Trade linked to another thesis
    t3 = _make_trade(
        trade_id="tr3",
        ts=dt.datetime(2025, 1, 1, 13, 0, 0),
        asset="TLT",
        action="BUY",
        quantity=1.0,
        price=100.0,
        thesis_ref="t2",
    )

    repo.insert(t1)
    repo.insert(t2)
    repo.insert(t3)

    trades_for_t1 = repo.list_by_thesis("t1")
    ids = [t.trade_id for t in trades_for_t1]

    # list_by_thesis ORDER BY timestamp DESC
    assert ids == ["tr2", "tr1"]
    assert all(t.thesis_ref == "t1" for t in trades_for_t1)