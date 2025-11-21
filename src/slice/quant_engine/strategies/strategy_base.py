# src/slice/quant_engine/strategies/strategy_base.py

from __future__ import annotations

import backtrader as bt
from typing import Dict, List


class StrategyBase(bt.Strategy):
    """
    Base class for all Slice Backtrader strategies.

    Responsibilities:
    - Provide a uniform API: compute_target_weights() -> {symbol: weight}
    - Map symbols to Backtrader data feeds (multi-asset support)
    - Route entry/exit via order_target_percent()
    - Maintain a deterministic in-memory trade log for later extraction
    """

    params = dict(
        symbols=None,               # Optional[List[str]]; if None, infer from data._name
        rebalance_on_every_bar=True,
    )

    def __init__(self) -> None:
        # Map symbol -> data feed
        self.symbol_to_data: Dict[str, bt.LineSeries] = {}

        for data in self.datas:
            # Expect data._name to be set when added to Cerebro
            symbol = data._name or data._dataname
            self.symbol_to_data[symbol] = data

        # If explicit symbol list provided, enforce it
        if self.p.symbols is not None:
            missing = [s for s in self.p.symbols if s not in self.symbol_to_data]
            if missing:
                raise ValueError(f"Missing data feeds for symbols: {missing}")

        # Order / trade logging for BacktestResultJSON
        self.order_log: List[dict] = []
        self.trade_log: List[dict] = []

    # ---------- Child API ----------

    def compute_target_weights(self) -> Dict[str, float]:
        """
        Child strategies MUST override this.

        Returns
        -------
        dict: {symbol: target_weight} in [-1.0, 1.0]
        where weights are fractions of total portfolio equity.

        Example:
            return {"GLD": 0.25, "UUP": -0.10}
        """
        raise NotImplementedError

    # ---------- Core Backtrader Hook ----------

    def next(self) -> None:
        """
        Called every bar. Computes target weights and routes to broker.
        """
        if not self.p.rebalance_on_every_bar:
            # Placeholder for more complex rules later
            pass

        targets = self.compute_target_weights()
        if not isinstance(targets, dict):
            raise TypeError("compute_target_weights() must return dict[symbol, weight].")

        # Enforce deterministic order of execution
        for symbol in sorted(targets.keys()):
            target = float(targets[symbol])

            data = self.symbol_to_data.get(symbol)
            if data is None:
                raise ValueError(f"compute_target_weights() returned unknown symbol: {symbol}")

            # Use Backtrader's built-in sizing by percent of equity
            self.order_target_percent(data=data, target=target)

    # ---------- Logging ----------

    def log(self, msg: str) -> None:
        """
        Minimal logger used by strategies; can be replaced later.
        """
        print(msg)

    def notify_order(self, order: bt.Order) -> None:
        """
        Capture executed orders into order_log.
        """
        if order.status not in [order.Completed, order.Partial]:
            return

        dt = bt.num2date(order.executed.dt)

        record = {
            "datetime": dt,
            "symbol": order.data._name or order.data._dataname,
            "size": order.executed.size,
            "price": order.executed.price,
            "value": order.executed.value,
            "commission": order.executed.comm,
            "order_ref": order.ref,
            "direction": "buy" if order.isbuy() else "sell",
            "status": "partial" if order.status == order.Partial else "completed",
        }
        self.order_log.append(record)

    def notify_trade(self, trade: bt.Trade) -> None:
        """
        Capture closed trades into trade_log.
        """
        if not trade.isclosed:
            return

        # Backtrader stores datetimes as float-like numbers
        dt_open = bt.num2date(trade.dtopen) if trade.dtopen is not None else None
        dt_close = bt.num2date(trade.dtclose) if trade.dtclose is not None else None

        # Symbol name: prefer `_name`, fall back to `_dataname`
        data = trade.data
        symbol = getattr(data, "_name", None) or getattr(data, "_dataname", None)

        # There is no `trade.priceclose` in Backtrader.
        # Approximate exit price from the data feed at the close bar.
        try:
            price_close = float(data.close[0])
        except Exception:
            price_close = None

        record = {
            "symbol": symbol,
            "dt_open": dt_open,
            "dt_close": dt_close,
            "size": trade.size,
            "price_open": trade.price,        # average entry price
            "price_close": price_close,       # exit close from data
            "pnl": trade.pnl,
            "pnl_commission": trade.pnlcomm,
        }

        self.trade_log.append(record)