"""
E4: Injectable LLMTools class that wraps E3 LLM tool functions.
"""
from typing import List

from voyager.llm.tools import (
    llm_review_thesis,
    llm_daily_summary,
    llm_cross_theses,
    llm_query_intuition,
    OrchestratorProtocol,
)
from voyager.models.thesis import Thesis
from voyager.models.evaluation import ThesisEvaluationResult
from voyager.models.llm_inputs import DailyContext
from voyager.models.observation import Observation
from voyager.models.llm_outputs import ThesisReview, DailySummary, CrossThesisReport, IntuitionAnswer


class LLMTools:
    """
    Injectable wrapper around E3 LLM tool functions.
    
    Sessions depend on this class, not on the orchestrator directly.
    """

    def __init__(self, orchestrator: OrchestratorProtocol):
        """
        Initialize with an orchestrator that implements OrchestratorProtocol.
        
        Args:
            orchestrator: Session orchestrator for LLM calls
        """
        self._orchestrator = orchestrator

    async def review_thesis(
        self, thesis: Thesis, evaluation: ThesisEvaluationResult
    ) -> ThesisReview:
        """
        Review a thesis against its evaluation results.
        
        Args:
            thesis: Thesis to review
            evaluation: E2 evaluation results
            
        Returns:
            ThesisReview DTO
        """
        return await llm_review_thesis(thesis, evaluation, self._orchestrator)

    async def daily_summary(self, context: DailyContext) -> DailySummary:
        """
        Generate a daily summary from context.
        
        Args:
            context: Daily context snapshot
            
        Returns:
            DailySummary DTO
        """
        return await llm_daily_summary(context, self._orchestrator)

    async def cross_theses(self, theses: List[Thesis]) -> CrossThesisReport:
        """
        Analyze relationships between multiple theses.
        
        Args:
            theses: List of theses to analyze
            
        Returns:
            CrossThesisReport DTO
        """
        return await llm_cross_theses(theses, self._orchestrator)

    async def query_intuition(
        self, question: str, observations: List[Observation]
    ) -> IntuitionAnswer:
        """
        Answer an intuition query based on observations.
        
        Args:
            question: User question
            observations: Observations to use as context
            
        Returns:
            IntuitionAnswer DTO
        """
        return await llm_query_intuition(question, observations, self._orchestrator)

