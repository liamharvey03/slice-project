from typing import Optional, List, Any
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
        return self.thesis_repo.list_all()

    def get_observations_for_thesis(self, thesis_id: int) -> List[Observation]:
        return self.obs_repo.list_for_thesis(thesis_id)

    def get_recent_observations(self, limit: int = 10) -> List[Observation]:
        return self.obs_repo.list_recent(limit)

    def get_risk_snapshot(self) -> Optional[Any]:
        return get_snapshot()