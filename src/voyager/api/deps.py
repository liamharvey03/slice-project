"""
E4: Centralized dependency wiring for production app.

This module provides factory functions to create singleton instances of
all dependencies needed by E4 endpoints and related routes.
"""
import os
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI

from typing import Optional

from voyager.db import get_engine
from voyager.intelligence.context.data_access import DataAccess
from voyager.intelligence.orchestrator_client import OrchestratorClient, LLMClientProtocol
from voyager.evaluation.thesis_evaluation import ThesisEvaluationService
from voyager.quant.price_source import PriceSource
from voyager.quant.quant_service import QuantService
from voyager.quant.backtest_engine import BacktestEngine, BacktestConfig
from voyager.data.series_registry import SeriesRegistry
from voyager.repositories.thesis_repo import ThesisRepository
from voyager.repositories.observation_repo import ObservationRepository
from voyager.repositories.trade_repo import TradeRepository
from voyager.repositories.evaluation_repo import EvaluationRepository
from voyager.repositories.alert_repo import AlertRepository
from voyager.repositories.daily_summary_repo import DailySummaryRepository
from voyager.repositories.backtest_result_repository import BacktestResultRepository
from voyager.repositories.logic_validation_repository import LogicValidationRepository
from voyager.repositories.thesis_snapshot_repository import ThesisSnapshotRepository
from voyager.services.v3.backtest_service import BacktestService
from voyager.services.v3.sizing_service import SizingService
from voyager.services.v3.thesis_service import ThesisService
from voyager.llm.query_translator import QueryTranslator
from voyager.llm.critique_engine import CritiqueEngine
from voyager.services.v3.validation_service import ValidationService
from voyager.services.v3.critique_service import CritiqueService


# Module-level cache for singletons
_data_access_instance: DataAccess | None = None
_price_source_instance: PriceSource | None = None
_llm_client_instance: LLMClientProtocol | None = None
_orchestrator_client_instance: OrchestratorClient | None = None
_quant_service_instance: Optional[QuantService] = None
_series_registry_instance: Optional[SeriesRegistry] = None
_backtest_engine_instance: Optional[BacktestEngine] = None
_backtest_service_instance: Optional[BacktestService] = None
_sizing_service_instance: Optional[SizingService] = None
_thesis_service_instance: Optional[ThesisService] = None
_query_translator_instance: Optional[QueryTranslator] = None
_critique_engine_instance: Optional[CritiqueEngine] = None
_validation_service_instance: Optional[ValidationService] = None
_critique_service_instance: Optional[CritiqueService] = None


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


def get_series_registry_instance() -> SeriesRegistry:
    """
    Create and return a singleton SeriesRegistry instance.
    
    Returns:
        SeriesRegistry instance loaded from series_registry.json
    """
    global _series_registry_instance
    
    if _series_registry_instance is None:
        _series_registry_instance = SeriesRegistry()
    
    return _series_registry_instance


def get_quant_service_instance() -> QuantService:
    """
    Create and return a singleton QuantService instance.
    
    Wires QuantService with database engine and SeriesRegistry.
    
    Returns:
        Fully wired QuantService instance
    """
    global _quant_service_instance
    
    if _quant_service_instance is None:
        engine = get_engine()
        registry = get_series_registry_instance()
        _quant_service_instance = QuantService(engine, registry)
    
    return _quant_service_instance


def get_backtest_engine_instance() -> BacktestEngine:
    """
    Create and return a singleton BacktestEngine instance.
    
    Uses default BacktestConfig.
    
    Returns:
        Fully wired BacktestEngine instance
    """
    global _backtest_engine_instance
    
    if _backtest_engine_instance is None:
        engine = get_engine()
        config = BacktestConfig()  # Use defaults
        _backtest_engine_instance = BacktestEngine(engine, config)
    
    return _backtest_engine_instance


def get_backtest_service_instance() -> BacktestService:
    """
    Create and return a singleton BacktestService instance.
    
    Wires BacktestService with BacktestEngine, BacktestResultRepository, and ThesisRepository.
    
    Returns:
        Fully wired BacktestService instance
    """
    global _backtest_service_instance
    
    if _backtest_service_instance is None:
        engine = get_engine()
        
        backtest_engine = get_backtest_engine_instance()
        backtest_repo = BacktestResultRepository(engine)
        thesis_repo = get_data_access_instance().thesis_repo  # Reuse existing
        
        _backtest_service_instance = BacktestService(
            backtest_engine=backtest_engine,
            backtest_repo=backtest_repo,
            thesis_repo=thesis_repo
        )
    
    return _backtest_service_instance


def get_query_translator_instance() -> QueryTranslator:
    """
    Create and return a singleton QueryTranslator instance.
    
    Wires QueryTranslator with LLM client and SeriesRegistry.
    
    Returns:
        Fully wired QueryTranslator instance
    """
    global _query_translator_instance
    
    if _query_translator_instance is None:
        llm_client = get_llm_client_instance()
        registry = get_series_registry_instance()
        _query_translator_instance = QueryTranslator(llm_client, registry)
    
    return _query_translator_instance


def get_critique_engine_instance() -> CritiqueEngine:
    """
    Create and return a singleton CritiqueEngine instance.
    
    Wires CritiqueEngine with LLM client.
    
    Returns:
        Fully wired CritiqueEngine instance
    """
    global _critique_engine_instance
    
    if _critique_engine_instance is None:
        llm_client = get_llm_client_instance()
        _critique_engine_instance = CritiqueEngine(llm_client)
    
    return _critique_engine_instance


def get_validation_service_instance() -> ValidationService:
    """
    Create and return a singleton ValidationService instance.
    
    Wires ValidationService with QueryTranslator, QuantService, and repositories.
    
    Returns:
        Fully wired ValidationService instance
    """
    global _validation_service_instance
    
    if _validation_service_instance is None:
        engine = get_engine()
        
        _validation_service_instance = ValidationService(
            query_translator=get_query_translator_instance(),
            quant_service=get_quant_service_instance(),
            validation_repo=LogicValidationRepository(engine),
            thesis_repo=get_data_access_instance().thesis_repo
        )
    
    return _validation_service_instance


def get_critique_service_instance() -> CritiqueService:
    """
    Create and return a singleton CritiqueService instance.
    
    Wires CritiqueService with CritiqueEngine and all required repositories.
    
    Returns:
        Fully wired CritiqueService instance
    """
    global _critique_service_instance
    
    if _critique_service_instance is None:
        engine = get_engine()
        
        _critique_service_instance = CritiqueService(
            critique_engine=get_critique_engine_instance(),
            thesis_repo=get_data_access_instance().thesis_repo,
            snapshot_repo=ThesisSnapshotRepository(engine),
            validation_repo=LogicValidationRepository(engine),
            backtest_repo=BacktestResultRepository(engine),
            engine=engine
        )
    
    return _critique_service_instance


def get_sizing_service_instance() -> SizingService:
    """
    Create and return a singleton SizingService instance.

    Wires SizingService with engine, BacktestResultRepository, and TradeRepository.

    Returns:
        Fully wired SizingService instance
    """
    global _sizing_service_instance

    if _sizing_service_instance is None:
        engine = get_engine()
        _sizing_service_instance = SizingService(
            engine=engine,
            backtest_repo=BacktestResultRepository(engine),
            trade_repo=get_data_access_instance().trade_repo
        )

    return _sizing_service_instance


def get_thesis_service_instance() -> ThesisService:
    """
    Create and return a singleton ThesisService instance.

    Wires ThesisService with ThesisRepository and ThesisSnapshotRepository.

    Returns:
        Fully wired ThesisService instance
    """
    global _thesis_service_instance

    if _thesis_service_instance is None:
        engine = get_engine()
        _thesis_service_instance = ThesisService(
            thesis_repo=get_data_access_instance().thesis_repo,
            snapshot_repo=ThesisSnapshotRepository(engine)
        )

    return _thesis_service_instance

