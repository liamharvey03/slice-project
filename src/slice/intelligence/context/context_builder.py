from typing import Dict, Any, List
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