from typing import Dict, List

from pydantic import BaseModel


class Position(BaseModel):
    """
    A single portfolio position, represented in monetary terms.
    """

    asset: str
    quantity: float
    value: float  # current market value of this position


class PortfolioTotals(BaseModel):
    """
    Aggregate totals for the portfolio.
    """

    portfolio_value: float
    gross_exposure: float
    net_exposure: float


class PortfolioSnapshot(BaseModel):
    """
    Snapshot of the current portfolio state at a point in time.
    """

    positions: List[Position]
    totals: PortfolioTotals


class PortfolioDepthSnapshot(BaseModel):
    """
    Higher-level diagnostics on concentration, factors, and thesis exposure.
    The exact key structure of each dict is left flexible; E1 only requires
    that these are present and consistently shaped.
    """

    concentration: Dict[str, float]
    factors: Dict[str, float]
    thesis_exposures: Dict[str, float]