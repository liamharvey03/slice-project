from typing import Optional, List, Any, Dict, Iterable
from slice.repositories.thesis_repo import ThesisRepository
from slice.repositories.observation_repo import ObservationRepository
from slice.repositories.trade_repo import TradeRepository
from slice.risk.interface import get_snapshot
from slice.models.thesis import Thesis
from slice.models.observation import Observation
from slice.models.portfolio import (
    Position,
    PortfolioTotals,
    PortfolioSnapshot,
    PortfolioDepthSnapshot,
)


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
        scenario_repo=None,
        price_source=None,
    ):
        self.thesis_repo = thesis_repo
        self.obs_repo = obs_repo
        self.trade_repo = trade_repo
        self.scenario_repo = scenario_repo
        self.price_source = price_source

    def get_thesis(self, thesis_id: int | str) -> Optional[Thesis]:
        repo = self.thesis_repo

        if hasattr(repo, "get_by_id"):
            try:
                return repo.get_by_id(thesis_id)
            except Exception:
                pass
        if hasattr(repo, "get"):
            try:
                return repo.get(thesis_id)
            except Exception:
                return None
        if hasattr(repo, "_theses"):
            try:
                return repo._theses.get(thesis_id)
            except Exception:
                return None
        return None

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
            return repo.list_recent(limit=100)
        return []

    def get_observations_for_thesis(self, thesis_id: int | str) -> List[Observation]:
        repo = self.obs_repo

        if hasattr(repo, "list_for_thesis"):
            try:
                return list(repo.list_for_thesis(thesis_id))
            except Exception:
                pass

        if hasattr(repo, "list_all"):
            try:
                all_obs = list(repo.list_all())
            except Exception:
                return []

            result: List[Observation] = []
            for o in all_obs:
                ref = getattr(o, "thesis_ref", None)
                if ref is None:
                    continue
                if isinstance(ref, (list, tuple, set)):
                    if thesis_id in ref:
                        result.append(o)
                else:
                    if ref == thesis_id:
                        result.append(o)
            return result

        return []

    def get_recent_observations(self, limit: int = 10) -> List[Observation]:
        repo = self.obs_repo

        if hasattr(repo, "list_recent"):
            return repo.list_recent(limit)

        if hasattr(repo, "list_all"):
            try:
                obs = list(repo.list_all())
                obs.sort(key=lambda o: getattr(o, "timestamp", None), reverse=True)
                return obs[:limit]
            except Exception:
                return []

        return []

    def get_risk_snapshot(self) -> Optional[Any]:
        return get_snapshot()
    # -------------------------------------------------------------------------
    # PHASE 8 EXTENSIONS
    # -------------------------------------------------------------------------

    def get_current_portfolio(self) -> PortfolioSnapshot:
        """
        Return a deterministic portfolio snapshot by reading all trades.
        Uses PortfolioAdapter to build an end-to-end snapshot.
        """
        snapshot = self._build_portfolio_snapshot_dict()

        positions_dto = [
            Position(
                asset=p.get("asset") or p.get("symbol") or "",
                quantity=p.get("quantity", 0.0),
                value=p.get("value", p.get("market_value", 0.0)),
            )
            for p in snapshot.get("positions", [])
        ]

        totals_dict = snapshot.get("totals", {}) or {}
        totals_dto = PortfolioTotals(
            portfolio_value=totals_dict.get("portfolio_value", 0.0),
            gross_exposure=totals_dict.get("gross_exposure", 0.0),
            net_exposure=totals_dict.get("net_exposure", 0.0),
        )

        return PortfolioSnapshot(positions=positions_dto, totals=totals_dto)

    def _build_portfolio_snapshot_dict(self) -> Dict[str, Any]:
        """
        Internal helper to build the raw dict snapshot using the existing adapter.
        """
        from slice.intelligence.context.portfolio_adapter import build_portfolio_snapshot

        trades = []
        try:
            if hasattr(self.trade_repo, "list_all"):
                trades = list(self.trade_repo.list_all())
            else:
                trades = []
        except Exception:
            trades = []

        raw_positions = []
        for t in trades:
            try:
                symbol = getattr(t, "symbol", None) or getattr(t, "asset", None)
                quantity = getattr(t, "quantity", None)
                price = getattr(t, "price", None)
                if symbol is None or quantity is None or price is None:
                    continue
                raw_positions.append(
                    {
                        "symbol": symbol,
                        "quantity": quantity,
                        "price": price,
                        "thesis_id": getattr(t, "thesis_ref", None),
                    }
                )
            except Exception:
                continue

        return build_portfolio_snapshot(raw_positions)

    def get_portfolio_depth(self, theses: Iterable[Any]) -> PortfolioDepthSnapshot:
        """
        Compute concentration + factor exposures + thesis weighting map.
        """
        from slice.intelligence.context.concentration import compute_concentration
        from slice.intelligence.context.factors import compute_factor_exposures
        from slice.intelligence.context.exposure_map import build_exposure_map

        snapshot_dict = self._build_portfolio_snapshot_dict()

        concentration = compute_concentration(snapshot_dict)
        factor_exposures = compute_factor_exposures(snapshot_dict)
        exposure_map = build_exposure_map(theses, snapshot_dict)

        concentration_payload: Dict[str, float] = {}
        if isinstance(concentration, dict):
            for k, v in concentration.items():
                if isinstance(v, (int, float)):
                    concentration_payload[k] = float(v)

        factors_payload: Dict[str, float] = {}
        if isinstance(factor_exposures, dict):
            agg = factor_exposures.get("aggregate")
            if isinstance(agg, dict):
                for k, v in agg.items():
                    if isinstance(v, (int, float)):
                        factors_payload[k] = float(v)

        thesis_payload: Dict[str, float] = {}
        if isinstance(exposure_map, dict):
            theses_list = exposure_map.get("theses", [])
            if isinstance(theses_list, list):
                for t in theses_list:
                    if not isinstance(t, dict):
                        continue
                    tid = t.get("id")
                    weight = t.get("weight", 0.0)
                    if tid is None:
                        continue
                    try:
                        thesis_payload[str(tid)] = float(weight)
                    except Exception:
                        continue
            unassigned = exposure_map.get("unassigned")
            if isinstance(unassigned, dict):
                try:
                    thesis_payload["unassigned"] = float(unassigned.get("weight", 0.0))
                except Exception:
                    pass

        return PortfolioDepthSnapshot(
            concentration=concentration_payload,
            factors=factors_payload,
            thesis_exposures=thesis_payload,
        )

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
