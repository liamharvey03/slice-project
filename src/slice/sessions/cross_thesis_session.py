"""
E4: CrossThesisSession - Optional cross-thesis analysis workflow.
"""
from typing import List

from slice.intelligence.context.data_access import DataAccess
from slice.llm.llm_tools import LLMTools
from slice.sessions.exceptions import ThesisNotFoundError
from slice.models.session_results import CrossThesisSessionResult
from slice.models.thesis import Thesis


class CrossThesisSession:
    """
    Thin wrapper over E3 llm_cross_theses tool.
    
    Optional session for analyzing relationships between multiple theses.
    """

    def __init__(self, data_access: DataAccess, llm_tools: LLMTools) -> None:
        """
        Initialize the session.
        
        Args:
            data_access: Data access layer
            llm_tools: E3 LLM tools wrapper
        """
        self.data = data_access
        self.llm = llm_tools

    async def run(self, thesis_ids: List[str]) -> CrossThesisSessionResult:
        """
        Run cross-thesis analysis.
        
        Args:
            thesis_ids: List of thesis IDs to analyze
            
        Returns:
            CrossThesisSessionResult with analysis report
            
        Raises:
            ValueError: If any thesis ID is not found
        """
        # Load all theses
        theses: List[Thesis] = []
        for thesis_id in thesis_ids:
            thesis = self.data.get_thesis(thesis_id)
            if thesis is None:
                raise ValueError(f"Unknown thesis id: {thesis_id}")
            theses.append(thesis)

        # Run E3 cross-thesis analysis
        report = await self.llm.cross_theses(theses)

        return CrossThesisSessionResult(thesis_ids=thesis_ids, report=report)

