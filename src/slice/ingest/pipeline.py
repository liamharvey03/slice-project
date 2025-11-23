from __future__ import annotations

from typing import Any, Dict

from slice.embeddings import embed_observation_text

from slice.llm_validation import (
    validate_thesis,
    validate_observation,
    validate_trade,
    validate_scenario,
    ValidationResult
)

from slice.repositories.thesis_repo import ThesisRepository
from slice.repositories.observation_repo import ObservationRepository
from slice.repositories.trade_repo import TradeRepository
from slice.repositories.scenario_repo import ScenarioRepository


class IngestionPipeline:

    # -----------------------------
    # Thesis
    # -----------------------------
    @staticmethod
    def ingest_thesis(raw: Dict[str, Any]) -> ValidationResult:
        result = validate_thesis(raw)
        if not result.ok:
            return result  # do not insert

        ThesisRepository.insert(result.model)
        return result

        # -----------------------------
    # Observation (core)
    # -----------------------------
    @staticmethod
    def ingest_observation(raw: Dict[str, Any], embedding_vector=None) -> ValidationResult:
        """
        Base ingestion path:
          - validate observation
          - write to DB
        embedding_vector may be None (plain write) or list[float] (vector)
        """
        result = validate_observation(raw)
        if not result.ok:
            return result

        ObservationRepository.insert(result.model, embedding_vector=embedding_vector)
        return result

    # -----------------------------
    # Observation
    # -----------------------------
    @staticmethod
    def ingest_observation_with_embedding(raw: Dict[str, Any]) -> ValidationResult:
        """
        Full pipeline for observations:
          - validate + normalize payload
          - compute OpenAI embedding on the validated text
          - insert into DB with embedding

        If validation fails, no embedding call is made and nothing is written.
        """
        # First pass: validate
        prelim = validate_observation(raw)
        if not prelim.ok:
            return prelim

        text = prelim.model.text  # already stripped/validated by Pydantic
        embedding = embed_observation_text(text)

        # Reuse the core ingestion path, but supply the embedding vector
        return IngestionPipeline.ingest_observation(raw, embedding_vector=embedding)

    # -----------------------------
    # Trade
    # -----------------------------
    @staticmethod
    def ingest_trade(raw: Dict[str, Any]) -> ValidationResult:
        result = validate_trade(raw)
        if not result.ok:
            return result

        TradeRepository.insert(result.model)
        return result

    # -----------------------------
    # Scenario
    # -----------------------------
    @staticmethod
    def ingest_scenario(raw: Dict[str, Any]) -> ValidationResult:
        result = validate_scenario(raw)
        if not result.ok:
            return result

        ScenarioRepository.insert(result.model)
        return result