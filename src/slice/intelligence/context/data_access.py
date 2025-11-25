from typing import Optional, List, Any, Dict, Iterable
from slice.repositories.thesis_repo import ThesisRepository
from slice.repositories.observation_repo import ObservationRepository
from slice.repositories.trade_repo import TradeRepository
from slice.risk.interface import get_snapshot
from slice.models.thesis import Thesis
from slice.models.observation import Observation


class DataAccess:
    """
    Deterministic DB accessor layer used by Phase 6 context builders.
    Does NOT call LLMs. Does NOT mutate state.
    """

    @classmethod
    def depends(cls) -> "DataAccess":
        """
        FastAPI dependency hook for DataAccess.

        In production wiring, this should be replaced or overridden to return
        a fully wired DataAccess instance. In tests, this is usually monkeypatched.
        """
        raise RuntimeError("DataAccess dependency not wired")

    def __init__(
        self,
        thesis_repo: ThesisRepository,
        obs_repo: ObservationRepository,
        trade_repo: TradeRepository,
    ):
        self.thesis_repo = thesis_repo
        self.obs_repo = obs_repo
        self.trade_repo = trade_repo

    def get_thesis(self, thesis_id: int) -> Optional[Thesis]:
        return self.thesis_repo.get_by_id(thesis_id)

    def get_all_theses(self) -> List[Thesis]:
        """Return all theses if the repository supports it, else recent or empty list.

        This keeps Phase 8 DataAccess robust when used with repositories that only
        expose list_recent (e.g. SQL-backed ThesisRepository) while still satisfying
        Phase 8 tests that expect list_all on fake repos.
        """
        repo = self.thesis_repo

        if hasattr(repo, "list_all"):
            return repo.list_all()
        if hasattr(repo, "list_recent"):
            return repo.list_recent(limit=50)
        return []

    def get_observations_for_thesis(self, thesis_id: int) -> List[Observation]:
        return self.obs_repo.list_for_thesis(thesis_id)

    def get_recent_observations(self, limit: int = 10) -> List[Observation]:
        return self.obs_repo.list_recent(limit)

    def get_risk_snapshot(self) -> Optional[Any]:
        return get_snapshot()
    # -------------------------------------------------------------------------
    # PHASE 8 EXTENSIONS
    # -------------------------------------------------------------------------

    def get_current_portfolio(self) -> Dict[str, Any]:
        """
        Return a deterministic portfolio snapshot by reading all trades.
        Uses PortfolioAdapter to build an end-to-end snapshot.
        """
        from slice.intelligence.context.portfolio_adapter import build_portfolio_snapshot

        # Minimal trade-loading logic:
        trades = []
        try:
            # If repository has a method to list all trades, use it.
            # If not, empty list -> empty portfolio.
            if hasattr(self.trade_repo, "list_all"):
                trades = list(self.trade_repo.list_all())
            else:
                trades = []
        except Exception:
            trades = []

        # Convert trades into position dicts
        # Expecting trade model fields: symbol, quantity, price, thesis_ref
        raw_positions = []
        for t in trades:
            try:
                raw_positions.append(
                    {
                        "symbol": t.symbol,
                        "quantity": t.quantity,
                        "price": t.price,
                        "thesis_id": getattr(t, "thesis_ref", None),
                    }
                )
            except Exception:
                # skip malformed trade rows
                continue

        return build_portfolio_snapshot(raw_positions)

    def get_portfolio_depth(self, theses: Iterable[Any]) -> Dict[str, Any]:
        """
        Compute concentration + factor exposures + thesis weighting map.
        """
        from slice.intelligence.context.concentration import compute_concentration
        from slice.intelligence.context.factors import compute_factor_exposures
        from slice.intelligence.context.exposure_map import build_exposure_map

        snapshot = self.get_current_portfolio()

        concentration = compute_concentration(snapshot)
        factor_exposures = compute_factor_exposures(snapshot)
        exposure_map = build_exposure_map(theses, snapshot)

        return {
            "concentration": concentration,
            "factors": factor_exposures,
            "thesis_exposures": exposure_map,
        }

    def get_macro_snapshot(self) -> Dict[str, Any]:
        """
        Deterministic macro snapshot.
        Later will load from DB or external macro feeds.
        For now returns {} which compute_regimes can handle.
        """
        from slice.intelligence.context.macro_adapter import build_macro_snapshot

        # TEMP STUB: full integration done later
        latest_values: Dict[str, float] = {}
        return build_macro_snapshot(latest_values)

    def get_regimes(self) -> Dict[str, str]:
        """
        Regime classification from macro snapshot.
        """
        from slice.intelligence.context.macro_adapter import compute_regimes

        try:
            snapshot = self.get_macro_snapshot()
            return compute_regimes(snapshot)
        except Exception:
            return {"growth": "unknown", "inflation": "unknown",
                    "liquidity": "unknown", "usd": "unknown"}

    def get_quant_summaries(self) -> Dict[str, Any]:
        """
        Deterministic placeholder until quant backtests are wired.
        """
        return {
            "strategies": [],
            "scenarios": [],
            "risk_flags": [],
        }
