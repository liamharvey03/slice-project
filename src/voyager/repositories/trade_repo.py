from typing import Optional, List, Any, Mapping
from sqlalchemy import text

from voyager.db import get_engine
from voyager.models.trade import Trade
from voyager.models.common import TradeType


class TradeRepository:

    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def insert(self, trade: Trade) -> Trade:
        engine = self.engine
        sql = text("""
            INSERT INTO trade (
                trade_id, timestamp, asset, action, quantity,
                price, type, thesis_ref, notes
            )
            VALUES (
                :trade_id, :timestamp, :asset, :action, :quantity,
                :price, :type, :thesis_ref, :notes
            )
            ON CONFLICT (trade_id) DO UPDATE SET
                timestamp = EXCLUDED.timestamp,
                asset = EXCLUDED.asset,
                action = EXCLUDED.action,
                quantity = EXCLUDED.quantity,
                price = EXCLUDED.price,
                type = EXCLUDED.type,
                thesis_ref = EXCLUDED.thesis_ref,
                notes = EXCLUDED.notes;
        """)

        with engine.begin() as conn:
            conn.execute(sql, trade.dict())

        return trade

    def _row_to_trade(self, row: Mapping[str, Any]) -> Trade:
        data = dict(row)

        if isinstance(data.get("type"), str):
            try:
                data["type"] = TradeType(data["type"])
            except Exception:
                pass

        return Trade(**data)

    def list_all(self) -> List[Trade]:
        engine = self.engine
        sql = text("""
            SELECT * FROM trade
            ORDER BY timestamp ASC, trade_id ASC
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql).mappings().fetchall()

        return [self._row_to_trade(r) for r in rows]

    def list_by_thesis(self, thesis_id: str) -> List[Trade]:
        engine = self.engine
        sql = text("""
            SELECT * FROM trade
            WHERE thesis_ref = :thesis_id
            ORDER BY timestamp DESC
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql, {"thesis_id": thesis_id}).mappings().fetchall()

        return [self._row_to_trade(r) for r in rows]

    def list_for_thesis(self, thesis_id: str) -> List[Trade]:
        return self.list_by_thesis(thesis_id)
