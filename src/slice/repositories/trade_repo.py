from typing import Optional, List
from sqlalchemy import text

from slice.db import get_engine
from slice.models.trade import Trade


class TradeRepository:

    @staticmethod
    def insert(trade: Trade) -> None:
        engine = get_engine()
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

    @staticmethod
    def list_for_thesis(thesis_id: str) -> List[Trade]:
        engine = get_engine()
        sql = text("""
            SELECT * FROM trade
            WHERE thesis_ref = :thesis_id
            ORDER BY timestamp DESC
        """)

        with engine.connect() as conn:
            rows = conn.execute(sql, {"thesis_id": thesis_id}).mappings().fetchall()

        return [Trade(**r) for r in rows]