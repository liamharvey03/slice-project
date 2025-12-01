"""
E4: Centralized dependency wiring for production app.

This module provides factory functions to create singleton instances of
all dependencies needed by E4 endpoints and related routes.
"""
import os
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI

from slice.db import get_engine
from slice.intelligence.context.data_access import DataAccess
from slice.intelligence.orchestrator_client import OrchestratorClient, LLMClientProtocol
from slice.evaluation.thesis_evaluation import ThesisEvaluationService
from slice.quant.price_source import PriceSource
from slice.repositories.thesis_repo import ThesisRepository
from slice.repositories.observation_repo import ObservationRepository
from slice.repositories.trade_repo import TradeRepository
from slice.repositories.evaluation_repo import EvaluationRepository
from slice.repositories.alert_repo import AlertRepository
from slice.repositories.daily_summary_repo import DailySummaryRepository


# Module-level cache for singletons
_data_access_instance: DataAccess | None = None
_price_source_instance: PriceSource | None = None
_llm_client_instance: LLMClientProtocol | None = None
_orchestrator_client_instance: OrchestratorClient | None = None


class StubPriceSource:
    """
    Stub PriceSource implementation for development/testing.
    
    Raises NotImplementedError when called, indicating that a real
    PriceSource implementation is needed for production use.
    """
    
    def get_history(self, asset: str, start, end):
        """Stub implementation that raises NotImplementedError."""
        raise NotImplementedError(
            "PriceSource not configured for production. "
            "Implement a concrete PriceSource (e.g., DBPriceSource or TwelveDataPriceSource)."
        )
    
    def get_current_price(self, asset: str) -> float:
        """Stub implementation that raises NotImplementedError."""
        raise NotImplementedError(
            "PriceSource not configured for production. "
            "Implement a concrete PriceSource (e.g., DBPriceSource or TwelveDataPriceSource)."
        )


class SimpleMockPriceSource:
    """
    Simple mock PriceSource for testing/verification.
    
    Returns deterministic fake price data: linear trend from 100 to 110 over 1 year.
    """
    
    def get_history(self, asset: str, start, end):
        """Return fake historical prices with linear trend."""
        import pandas as pd
        dates = pd.date_range(start, end, freq='D')
        # Linear trend from 100 to 110 over the period
        num_days = len(dates)
        prices = [100.0 + (i * 10.0 / max(num_days - 1, 1)) for i in range(num_days)]
        return pd.Series(prices, index=dates)
    
    def get_current_price(self, asset: str) -> float:
        """Return fake current price."""
        return 110.0


class OpenAILLMClient:
    """
    Wrapper around OpenAI AsyncOpenAI client to implement LLMClientProtocol.
    
    This adapter makes the OpenAI client compatible with the protocol
    expected by SessionOrchestrator.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize the OpenAI LLM client wrapper.
        
        Args:
            api_key: OpenAI API key
            model: Model name to use (default: gpt-4)
        """
        self._client = AsyncOpenAI(api_key=api_key)
        self.model_name = model
    
    async def chat(self, messages: list[dict]) -> dict:
        """
        Send chat messages to OpenAI and return response.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            
        Returns:
            Dict with 'content' and 'usage' keys matching LLMClientProtocol
        """
        response = await self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
        )
        
        # Extract content and usage from OpenAI response
        content = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
            "completion_tokens": response.usage.completion_tokens if response.usage else None,
            "total_tokens": response.usage.total_tokens if response.usage else None,
        }
        
        return {
            "content": content,
            "usage": usage,
        }


def get_data_access_instance() -> DataAccess:
    """
    Create and return a singleton DataAccess instance with all repositories.
    
    Includes E4 repositories (evaluation, alert, daily_summary) in addition
    to core repositories (thesis, observation, trade).
    
    Returns:
        Fully wired DataAccess instance
    """
    global _data_access_instance
    
    if _data_access_instance is None:
        engine = get_engine()
        
        thesis_repo = ThesisRepository(engine=engine)
        obs_repo = ObservationRepository(engine=engine)
        trade_repo = TradeRepository(engine=engine)
        eval_repo = EvaluationRepository(engine=engine)
        alert_repo = AlertRepository(engine=engine)
        daily_summary_repo = DailySummaryRepository(engine=engine)
        
        _data_access_instance = DataAccess(
            thesis_repo=thesis_repo,
            obs_repo=obs_repo,
            trade_repo=trade_repo,
            evaluation_repo=eval_repo,
            alert_repo=alert_repo,
            daily_summary_repo=daily_summary_repo,
        )
    
    return _data_access_instance


def get_price_source_instance() -> PriceSource:
    """
    Create and return a singleton PriceSource instance.
    
    Currently returns a simple mock for testing/verification.
    For production, this should be replaced with a concrete implementation
    (e.g., DBPriceSource or TwelveDataPriceSource).
    
    Returns:
        PriceSource instance (currently a mock for testing)
    """
    global _price_source_instance
    
    if _price_source_instance is None:
        # Use mock for testing - replace with real implementation for production
        _price_source_instance = SimpleMockPriceSource()
    
    return _price_source_instance


def get_llm_client_instance() -> LLMClientProtocol:
    """
    Create and return a singleton LLM client instance.
    
    Uses OpenAI API with API key from OPENAI_API_KEY environment variable.
    Model can be configured via OPENAI_MODEL env var (default: gpt-4).
    
    Returns:
        LLMClientProtocol instance wrapping OpenAI client
        
    Raises:
        RuntimeError: If OPENAI_API_KEY is not set
    """
    global _llm_client_instance
    
    if _llm_client_instance is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set. "
                "Set it to your OpenAI API key to enable LLM functionality."
            )
        
        model = os.getenv("OPENAI_MODEL", "gpt-4")
        _llm_client_instance = OpenAILLMClient(api_key=api_key, model=model)
    
    return _llm_client_instance


def get_orchestrator_client_instance() -> OrchestratorClient:
    """
    Create and return a singleton OrchestratorClient instance.
    
    Wires the OrchestratorClient with an LLM client.
    
    Returns:
        Fully wired OrchestratorClient instance
    """
    global _orchestrator_client_instance
    
    if _orchestrator_client_instance is None:
        llm_client = get_llm_client_instance()
        _orchestrator_client_instance = OrchestratorClient(llm_client=llm_client)
    
    return _orchestrator_client_instance

