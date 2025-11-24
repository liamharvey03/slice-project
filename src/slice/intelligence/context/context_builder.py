from typing import Dict, Any, List, Optional
from slice.intelligence.context.data_access import DataAccess


class ContextBuilder:
    """
    Phase 6 deterministic context assembly.
    No LLM calls. No orchestrator calls. No async.
    """

    def __init__(self, data_access: DataAccess):
        self.data = data_access

    def build_thesis_context(self, thesis_id: int) -> Dict[str, Any]:
        thesis = self.data.get_thesis(thesis_id)
        if thesis is None:
            return {"error": "thesis_not_found"}

        observations = self.data.get_observations_for_thesis(thesis_id)
        risk = self.data.get_risk_snapshot()

        return {
            "thesis": thesis.dict(),
            "observations": [o.dict() for o in observations],
            "risk_snapshot": risk.dict() if risk else None,
        }

    def build_multi_thesis_context(self) -> Dict[str, Any]:
        theses = self.data.get_all_theses()
        return {"theses": [t.dict() for t in theses]}

    def build_intuition_context(self, question: str, recalled_obs: List[dict]) -> Dict[str, Any]:
        return {
            "question": question,
            "recalled_observations": recalled_obs,
        }

    def build_daily_context(self) -> Dict[str, Any]:
        recent_obs = self.data.get_recent_observations()
        risk = self.data.get_risk_snapshot()

        return {
            "recent_observations": [o.dict() for o in recent_obs],
            "risk_snapshot": risk.dict() if risk else None,
        }

    # -----------------------------
    # Phase 7: Long-horizon reasoning context
    # -----------------------------
    def build_long_horizon_context(
        self,
        *,
        primary_thesis: Dict[str, Any],
        supporting_theses: Optional[List[Dict[str, Any]]] = None,
        macro_view: Dict[str, Any],
        scenarios: Optional[List[Dict[str, Any]]] = None,
        horizon_months: int = 12,
    ) -> Dict[str, Any]:
        """
        Build a deterministic long-horizon macro context bundle.

        Notes:
        - This method is pure assembly: it does not hit the DB or orchestrator.
        - Callers are responsible for passing in already-fetched/sanitized data.
        - Output is shaped specifically for Phase-7 long-horizon engines.
        """
        return {
            "kind": "long_horizon_context",
            "horizon_months": horizon_months,
            "primary_thesis": primary_thesis,
            "supporting_theses": supporting_theses or [],
            "macro_view": macro_view,
            "scenarios": scenarios or [],
        }

    # -----------------------------
    # Phase 7: Strategy recommendation context
    # -----------------------------
    def build_strategy_context(
        self,
        *,
        active_theses: List[Dict[str, Any]],
        current_portfolio: Dict[str, Any],
        risk_profile: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
        macro_view: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build context for the strategy recommendation engine.
        """
        return {
            "kind": "strategy_context",
            "active_theses": active_theses,
            "current_portfolio": current_portfolio,
            "risk_profile": risk_profile,
            "constraints": constraints or {},
            "macro_view": macro_view or {},
        }

    # -----------------------------
    # Phase 7: Portfolio diagnostics context
    # -----------------------------
    def build_portfolio_diagnostics_context(
        self,
        *,
        current_portfolio: Dict[str, Any],
        risk_profile: Dict[str, Any],
        factor_exposures: Optional[Dict[str, Any]] = None,
        stress_tests: Optional[List[Dict[str, Any]]] = None,
        recent_performance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build context for the portfolio diagnostics engine.
        """
        return {
            "kind": "portfolio_diagnostics_context",
            "current_portfolio": current_portfolio,
            "risk_profile": risk_profile,
            "factor_exposures": factor_exposures or {},
            "stress_tests": stress_tests or [],
            "recent_performance": recent_performance or {},
        }

    # -----------------------------
    # Phase 7: Narrative coherence / multi-engine context
    # -----------------------------
    def build_narrative_coherence_context(
        self,
        *,
        theses: List[Dict[str, Any]],
        macro_view: Dict[str, Any],
        portfolio_snapshot: Dict[str, Any],
        recent_observations: Optional[List[Dict[str, Any]]] = None,
        quant_summaries: Optional[Dict[str, Any]] = None,
        commentary_window: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build context for the narrative coherence engine.

        This is the multi-engine glue: it provides a consistent view of
        theses, macro, portfolio, and intuition so the LLM can produce a
        coherent, non-contradictory narrative.
        """
        return {
            "kind": "narrative_coherence_context",
            "theses": theses,
            "macro_view": macro_view,
            "portfolio_snapshot": portfolio_snapshot,
            "recent_observations": recent_observations or [],
            "quant_summaries": quant_summaries or {},
            "commentary_window": commentary_window or {},
        }