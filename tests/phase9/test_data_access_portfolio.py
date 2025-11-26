import pytest

from slice.intelligence.context.data_access import DataAccess
from slice.models.portfolio import PortfolioSnapshot, PortfolioDepthSnapshot


# --- Helper fakes -----------------------------------------------------------

class DummyThesis:
    def __init__(self, thesis_id: int, title: str = "dummy"):
        self.id = thesis_id
        self.title = title


class ThesisRepoDummy:
    """Minimal thesis repo; only used to satisfy DataAccess.__init__."""
    def get_by_id(self, thesis_id: int):
        return DummyThesis(thesis_id)


class ObservationRepoDummy:
    """Minimal observation repo; portfolio-related methods shouldn't hit this."""
    def list_for_thesis(self, thesis_id: int):
        return []

    def list_recent(self, limit: int = 10):
        return []


class TradeRepoEmpty:
    """Trade repo that reports no trades."""
    def list_all(self):
        return []


def _new_data_access_for_portfolio(trade_repo=None):
    """
    Construct a DataAccess instance with dummy thesis/observation repos
    and a supplied trade_repo (defaulting to an empty one).
    """
    thesis_repo = ThesisRepoDummy()
    obs_repo = ObservationRepoDummy()
    if trade_repo is None:
        trade_repo = TradeRepoEmpty()
    return DataAccess(thesis_repo, obs_repo, trade_repo)


# --- Tests: get_current_portfolio ------------------------------------------


def test_get_current_portfolio_with_no_trades_returns_empty_positions():
    da = _new_data_access_for_portfolio(trade_repo=TradeRepoEmpty())

    portfolio = da.get_current_portfolio()

    assert isinstance(portfolio, PortfolioSnapshot)

    data = portfolio.dict()

    # We expect at least these keys based on the Phase 8–9 design and codex scan.
    assert "positions" in data
    assert "totals" in data

    positions = data["positions"]
    totals = data["totals"]

    assert isinstance(positions, list)
    assert positions == [] or len(positions) == 0

    assert isinstance(totals, dict)
    # Totals should at least have these keys; numeric values may all be zero.
    for key in ("portfolio_value", "gross_exposure", "net_exposure"):
        assert key in totals
        assert isinstance(totals[key], (int, float))


# --- Tests: get_portfolio_depth --------------------------------------------


def test_get_portfolio_depth_shape_on_empty_portfolio():
    da = _new_data_access_for_portfolio(trade_repo=TradeRepoEmpty())

    # Depth may depend on current portfolio and/or theses; we pass an empty list here.
    depth = da.get_portfolio_depth(theses=[])

    assert isinstance(depth, PortfolioDepthSnapshot)

    depth_dict = depth.dict()
    # Shape comes from codex summary: {concentration, factors, thesis_exposures}
    assert "concentration" in depth_dict
    assert "factors" in depth_dict
    assert "thesis_exposures" in depth_dict

    assert isinstance(depth_dict["concentration"], dict)
    assert isinstance(depth_dict["factors"], dict)
    assert isinstance(depth_dict["thesis_exposures"], dict)
