"""
Validation Service for V3 Screen 1.

Orchestrates the thesis logic validation flow:
1. Extract causal links via QueryTranslator
2. Resolve concepts to series (or return ambiguities)
3. Run quant queries on resolved links
4. Persist and return results
"""
from datetime import datetime, UTC
from typing import Optional
import uuid
import logging

from voyager.llm.query_translator import QueryTranslator
from voyager.quant.quant_service import QuantService
from voyager.models.thesis import Thesis, LogicValidation, LogicLink
from voyager.models.v3 import ValidationResult
from voyager.repositories.logic_validation_repository import LogicValidationRepository
from voyager.repositories.thesis_repo import ThesisRepository

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Orchestrates thesis logic validation.

    Usage:
        result = await service.validate(thesis)

        if result.status == "needs_clarification":
            # Show ambiguities to PM
            clarifications = get_pm_input(result.ambiguities)
            result = await service.validate_with_clarifications(thesis, clarifications)

        if result.status == "complete":
            # Validation done, links available
            for link in result.links:
                print(f"{link.claim}: {link.interpretation}")
    """

    def __init__(
        self,
        query_translator: QueryTranslator,
        quant_service: QuantService,
        validation_repo: LogicValidationRepository,
        thesis_repo: ThesisRepository
    ):
        self._translator = query_translator
        self._quant = quant_service
        self._validation_repo = validation_repo
        self._thesis_repo = thesis_repo

    async def validate(self, thesis: Thesis) -> ValidationResult:
        """
        Run logic validation on a thesis.

        Returns:
            ValidationResult with status and either links or ambiguities
        """
        # Step 1: Extract and resolve
        try:
            output = await self._translator.extract_and_resolve(thesis)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to parse thesis %s: %s", thesis.id, e, exc_info=True)
            return ValidationResult(
                status="parse_failed",
                error_message=f"Failed to parse thesis: {str(e)}"
            )

        # Step 2: Check for ambiguities
        if output.ambiguities:
            return ValidationResult(
                status="needs_clarification",
                ambiguities=output.ambiguities
            )

        # Step 3: Check for no links
        if not output.resolved:
            # Still persist an empty validation record
            validation = LogicValidation(
                id=f"val_{uuid.uuid4().hex[:12]}",
                thesis_id=thesis.id,
                links=[],
                created_at=datetime.now(UTC).isoformat()
            )
            self._validation_repo.insert(validation)
            self._thesis_repo.update_status(thesis.id, "VALIDATED")
            
            return ValidationResult(
                status="complete",
                links=[],
                error_message="No testable causal claims found in thesis."
            )

        # Step 4: Run quant queries
        links = []
        for resolved in output.resolved:
            try:
                link = await self._run_quant_query(resolved)
                links.append(link)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Query failed for %s: %s", resolved.claim, e)
                # Query failed, but continue with others
                links.append(LogicLink(
                    claim=resolved.claim,
                    series_a=resolved.series_a,
                    series_b=resolved.series_b,
                    query_type=resolved.query_type,
                    result=0.0,
                    interpretation=f"error: {str(e)}"
                ))

        # Step 5: Persist validation
        validation = LogicValidation(
            id=f"val_{uuid.uuid4().hex[:12]}",
            thesis_id=thesis.id,
            links=links,
            created_at=datetime.now(UTC).isoformat()
        )
        self._validation_repo.insert(validation)

        # Step 6: Update thesis status
        self._thesis_repo.update_status(thesis.id, "VALIDATED")

        return ValidationResult(
            status="complete",
            links=links
        )

    async def validate_with_clarifications(
        self,
        thesis: Thesis,
        clarifications: dict  # {concept: series_id}
    ) -> ValidationResult:
        """
        Re-run validation with PM clarifications for ambiguous concepts.
        """
        # Re-extract with clarifications
        try:
            output = await self._translator.resolve_with_clarifications(thesis, clarifications)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to resolve with clarifications for %s: %s",
                thesis.id, e, exc_info=True
            )
            return ValidationResult(
                status="parse_failed",
                error_message=(
                    f"Failed to resolve with clarifications: {str(e)}"
                )
            )

        # Still ambiguous?
        if output.ambiguities:
            return ValidationResult(
                status="needs_clarification",
                ambiguities=output.ambiguities
            )

        # Run quant queries
        links = []
        for resolved in output.resolved:
            try:
                link = await self._run_quant_query(resolved)
                links.append(link)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Query failed for %s: %s", resolved.claim, e)
                links.append(LogicLink(
                    claim=resolved.claim,
                    series_a=resolved.series_a,
                    series_b=resolved.series_b,
                    query_type=resolved.query_type,
                    result=0.0,
                    interpretation=f"error: {str(e)}"
                ))

        # Persist
        validation = LogicValidation(
            id=f"val_{uuid.uuid4().hex[:12]}",
            thesis_id=thesis.id,
            links=links,
            created_at=datetime.now(UTC).isoformat()
        )
        self._validation_repo.insert(validation)

        self._thesis_repo.update_status(thesis.id, "VALIDATED")

        return ValidationResult(
            status="complete",
            links=links
        )

    async def _run_quant_query(self, resolved) -> LogicLink:
        """Run the appropriate quant query for a resolved link"""
        # Map direction from ResolvedLink to QuantService format
        expected_direction = resolved.direction  # "positive" or "negative"

        if resolved.query_type == "correlation":
            # Use relationship_strength for richer interpretation
            try:
                result = self._quant.relationship_strength(
                    resolved.series_a,
                    resolved.series_b,
                    expected_direction=expected_direction
                )

                return LogicLink(
                    claim=resolved.claim,
                    series_a=resolved.series_a,
                    series_b=resolved.series_b,
                    query_type="correlation",
                    result=result.correlation,
                    interpretation=result.interpretation
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "relationship_strength failed, falling back to correlation: %s", e
                )
                # Fallback to simple correlation
                result = self._quant.correlation(resolved.series_a, resolved.series_b)
                interpretation = self._interpret_correlation(result.correlation, expected_direction)

                return LogicLink(
                    claim=resolved.claim,
                    series_a=resolved.series_a,
                    series_b=resolved.series_b,
                    query_type="correlation",
                    result=result.correlation,
                    interpretation=interpretation
                )
        else:
            # Fallback to simple correlation for unknown query types
            result = self._quant.correlation(resolved.series_a, resolved.series_b)
            interpretation = self._interpret_correlation(result.correlation, expected_direction)

            return LogicLink(
                claim=resolved.claim,
                series_a=resolved.series_a,
                series_b=resolved.series_b,
                query_type=resolved.query_type,
                result=result.correlation,
                interpretation=interpretation
            )

    def _interpret_correlation(self, corr: float, expected_direction: str) -> str:
        """Simple correlation interpretation"""
        abs_corr = abs(corr)

        # Check if direction matches
        actual_direction = "positive" if corr > 0 else "negative"
        direction_matches = actual_direction == expected_direction

        if abs_corr >= 0.6:
            return "supports" if direction_matches else "contradicts"
        if abs_corr >= 0.3:
            return "weak"
        return "contradicts" if direction_matches else "weak"

    def get_latest_validation(self, thesis_id: str) -> Optional[LogicValidation]:
        """Get most recent validation for a thesis"""
        return self._validation_repo.get_by_thesis(thesis_id)
