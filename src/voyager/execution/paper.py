"""
E5: PaperExecutionAdapter - Paper-execution harness for turning TradePlans into Trade rows.
"""
from __future__ import annotations
from datetime import date, datetime
from uuid import uuid4

from voyager.models.execution import TradeLeg, TradePlan
from voyager.models.thesis import Thesis
from voyager.models.trade import Trade
from voyager.models.common import TradeType
from voyager.repositories.trade_repo import TradeRepository
from voyager.quant.price_source import PriceSource


class PaperExecutionAdapter:
    """
    Paper-execution harness for turning TradePlans into Trade rows.
    
    Conceptually depends on a SizingEngine to build TradePlans from Theses.
    E5 v1 inlines a NaiveSizingEngine implementation inside create_plan_from_thesis;
    later phases may inject a different sizing engine while preserving this class's
    public methods and the TradePlan DTO.
    """

    def __init__(self, trade_repo: TradeRepository, price_source: PriceSource):
        """
        Initialize the adapter.
        
        Args:
            trade_repo: Repository for persisting trades
            price_source: Source for current market prices
        """
        self.trade_repo = trade_repo
        self.price_source = price_source
        # future: self.sizing_engine: SizingEngine = NaiveSizingEngine(...)

    def create_plan_from_thesis(
        self,
        thesis: Thesis,
        total_notional: float,
    ) -> TradePlan:
        """
        Use the current sizing policy (E5 v1: NaiveSizingEngine) to convert
        thesis.expression (long-only) into a TradePlan for the given total_notional.
        
        E5 v1 policy:
        - total_notional must be positive
        - all legs must be LONG
        - allocations sum <= 100 (unallocated capital implicitly stays in cash)
        
        Later phases may delegate this to an injected SizingEngine that uses
        portfolio/risk information, without changing this method's signature
        or the TradePlan DTO.
        
        Args:
            thesis: Thesis with expression legs
            total_notional: Total capital to deploy
            
        Returns:
            TradePlan with legs mirroring thesis expression
            
        Raises:
            ValueError: If notional is non-positive, legs contain SHORT, or allocations sum > 100
        """
        if total_notional <= 0:
            raise ValueError("total_notional must be positive")

        legs: list[TradeLeg] = []
        total_pct = 0.0

        for leg in thesis.expression:
            if leg.direction.value.upper() != "LONG":
                raise ValueError("PaperExecutionAdapter v1 only supports long legs")

            leg_size_pct = leg.size_pct if leg.size_pct is not None else 0.0
            legs.append(
                TradeLeg(
                    asset=leg.asset,
                    direction="LONG",
                    size_pct=leg_size_pct,
                )
            )
            total_pct += leg_size_pct

        if total_pct > 100.0 + 1e-6:
            raise ValueError(f"Expression legs sum to {total_pct}%, must be <= 100")

        return TradePlan(
            thesis_id=thesis.id,
            total_notional=total_notional,
            legs=legs,
        )

    def execute_plan(
        self,
        plan: TradePlan,
        as_of: date | None = None,
    ) -> list[Trade]:
        """
        Execute plan legs as paper trades at current prices.
        
        Long-only, immediate fill, no costs.
        
        This method is intentionally dumb in E5 v1: no slippage, no fees,
        no leverage/margin checks. It assumes the sizing policy has already
        produced an acceptable TradePlan.
        
        Args:
            plan: TradePlan to execute
            as_of: Optional date for trade timestamp (defaults to now)
            
        Returns:
            List of executed Trade records
            
        Raises:
            RuntimeError: If price is invalid (<= 0) for any asset
        """
        if not plan.legs:
            return []

        exec_dt = (
            datetime.combine(as_of, datetime.min.time())
            if as_of is not None
            else datetime.utcnow()
        )

        trades: list[Trade] = []

        for leg in plan.legs:
            notional = plan.total_notional * (leg.size_pct / 100.0)
            if notional <= 0:
                continue

            price = self.price_source.get_current_price(leg.asset)
            if price <= 0:
                raise RuntimeError(f"Invalid price {price} for asset {leg.asset}")

            quantity = notional / price

            trade = Trade(
                trade_id=str(uuid4()),
                timestamp=exec_dt,
                asset=leg.asset,
                action="BUY",  # long-only, v1
                quantity=quantity,
                price=price,
                type=TradeType.SIMULATED,
                thesis_ref=plan.thesis_id,
            )

            self.trade_repo.insert(trade)
            trades.append(trade)

        return trades

