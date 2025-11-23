from typing import List, Tuple

from slice.models.observation import Observation
from slice.memory.retrieval import search_similar_observations


class MemoryService:

    @staticmethod
    def recall_similar_text(text: str, k: int = 5) -> List[Tuple[Observation, float]]:
        """
        Free-text semantic recall (general memory query).
        """
        return search_similar_observations(query_text=text, k=k)

    @staticmethod
    def recall_for_observation(obs: Observation, k: int = 5) -> List[Tuple[Observation, float]]:
        """
        Given an Observation model, return the nearest neighbors excluding itself.
        """
        results = search_similar_observations(obs.text, k=k+1)
        return [(o, d) for (o, d) in results if o.id != obs.id][:k]

    @staticmethod
    def recall_for_thesis(thesis_id: str, k: int = 10) -> List[Tuple[Observation, float]]:
        """
        Recall observations semantically relevant to a thesis, based on its text.
        Uses the thesis hypothesis+title as the query.
        """
        from slice.repositories.thesis_repo import ThesisRepository

        thesis = ThesisRepository.get(thesis_id)
        if thesis is None:
            return []

        # Use both title and hypothesis to form a query prompt
        query = f"{thesis.title}. {thesis.hypothesis}"

        return search_similar_observations(query_text=query, k=k)