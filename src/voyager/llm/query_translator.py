"""
Query Translator for V3 thesis validation.

Extracts causal claims from thesis text and resolves concepts to data series.
"""
from typing import Protocol, List, Optional
import json
import logging
import asyncio

from voyager.models.v3 import CausalLink, ResolvedLink, Ambiguity, QueryTranslatorOutput
from voyager.models.thesis import Thesis
from voyager.data.series_registry import SeriesRegistry
from voyager.llm.tools import extract_json

logger = logging.getLogger(__name__)


class LLMClientProtocol(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for LLM client chat interface."""

    async def chat(self, messages: List[dict]) -> dict:
        """Send messages to LLM and return response dict with 'content' key."""


# ===========================================
# Prompts
# ===========================================

EXTRACT_LINKS_SYSTEM = """You are a financial analyst extracting testable causal claims from investment theses.

Your job is to identify causal relationships that can be empirically validated with market or economic data.

A causal link has the form:
- "A leads to B" (positive relationship)
- "A causes B to decrease" (negative relationship)
- "When A happens, B follows"

Extract ONLY claims that are:
1. Empirically testable with financial data
2. Actually stated or strongly implied by the thesis
3. Specific enough to map to concrete data series

Do NOT invent relationships not present in the thesis."""

EXTRACT_LINKS_USER = """Analyze this investment thesis and extract testable causal links.

THESIS:
Title: {title}
Hypothesis: {hypothesis}
Drivers: {drivers}
Disconfirmers: {disconfirmers}

Respond with JSON only:
{{
  "links": [
    {{
      "claim": "human-readable description of the causal claim",
      "concept_a": "the cause (use common financial terms)",
      "concept_b": "the effect (use common financial terms)",
      "direction": "positive" or "negative"
    }}
  ]
}}

Examples of good concept names:
- "real yields", "fed funds rate", "10y yield", "gold", "dollar", "s&p 500", "oil"
- NOT: "market sentiment", "risk appetite", "uncertainty" (too vague)

Return an empty links array if no testable claims are found."""


CLARIFY_CONCEPT_USER = """The concept "{concept}" from the thesis could refer to multiple data series:

{candidates}

Based on the thesis context:
"{context}"

Which series is most likely intended? Respond with JSON:
{{
  "selected_id": "the series ID",
  "reasoning": "brief explanation"
}}

If genuinely ambiguous, respond:
{{
  "selected_id": null,
  "reasoning": "explanation of why it's ambiguous"
}}"""


# ===========================================
# Query Translator
# ===========================================

class QueryTranslator:
    """
    Translates thesis text into testable quantitative queries.

    Two-step process:
    1. LLM extracts causal links (concepts, not series IDs)
    2. Concepts are resolved to concrete series via registry

    If resolution is ambiguous, returns Ambiguity objects for PM clarification.

    Usage:
        translator = QueryTranslator(llm_client, registry)
        output = await translator.extract_and_resolve(thesis)

        if output.ambiguities:
            # Ask PM to clarify
            pass
        else:
            # All links resolved, ready for quant validation
            for link in output.resolved:
                result = quant.correlation(link.series_a, link.series_b)
    """

    def __init__(self, llm_client: LLMClientProtocol, registry: SeriesRegistry):
        self._llm = llm_client
        self._registry = registry

    async def extract_and_resolve(self, thesis: Thesis) -> QueryTranslatorOutput:
        """
        Extract causal links from thesis and resolve to series.

        Args:
            thesis: The thesis to analyze

        Returns:
            QueryTranslatorOutput with links, resolved, and ambiguities
        """
        # Step 1: Extract causal links via LLM
        links = await self._extract_links(thesis)

        if not links:
            return QueryTranslatorOutput(links=[], resolved=[], ambiguities=[])

        # Step 2: Resolve concepts to series
        resolved = []
        ambiguities = []

        for link in links:
            resolution_a = self._resolve_concept(link.concept_a)
            resolution_b = self._resolve_concept(link.concept_b)

            # Track ambiguities
            if resolution_a["status"] == "ambiguous":
                ambiguities.append(Ambiguity(
                    concept=link.concept_a,
                    candidates=resolution_a["candidates"]
                ))
            if resolution_b["status"] == "ambiguous":
                ambiguities.append(Ambiguity(
                    concept=link.concept_b,
                    candidates=resolution_b["candidates"]
                ))
            if resolution_a["status"] == "not_found":
                ambiguities.append(Ambiguity(
                    concept=link.concept_a,
                    candidates=[]  # Empty = not found
                ))
            if resolution_b["status"] == "not_found":
                ambiguities.append(Ambiguity(
                    concept=link.concept_b,
                    candidates=[]
                ))

            # If both resolved uniquely, add to resolved list
            if resolution_a["status"] == "resolved" and resolution_b["status"] == "resolved":
                resolved.append(ResolvedLink(
                    claim=link.claim,
                    series_a=resolution_a["series_id"],
                    series_b=resolution_b["series_id"],
                    query_type=self._determine_query_type(link),
                    direction=link.direction  # Preserve direction for ValidationService
                ))

        # Deduplicate ambiguities
        seen_concepts = set()
        unique_ambiguities = []
        for amb in ambiguities:
            if amb.concept not in seen_concepts:
                seen_concepts.add(amb.concept)
                unique_ambiguities.append(amb)

        return QueryTranslatorOutput(
            links=links,
            resolved=resolved,
            ambiguities=unique_ambiguities
        )

    async def resolve_with_clarifications(
        self,
        thesis: Thesis,
        clarifications: dict  # {concept: series_id}
    ) -> QueryTranslatorOutput:
        """
        Re-resolve links using PM clarifications.

        Args:
            thesis: Original thesis
            clarifications: Dict mapping ambiguous concepts to chosen series IDs

        Returns:
            Updated QueryTranslatorOutput
        """
        # Get original extraction
        output = await self.extract_and_resolve(thesis)

        # Apply clarifications to any remaining ambiguities
        new_resolved = list(output.resolved)
        remaining_ambiguities = []

        for link in output.links:
            # Check if this link has ambiguous concepts that are now clarified
            series_a = self._get_series_for_concept(link.concept_a, clarifications, output)
            series_b = self._get_series_for_concept(link.concept_b, clarifications, output)

            if series_a and series_b:
                # Check if not already in resolved
                already_resolved = any(
                    r.claim == link.claim for r in new_resolved
                )
                if not already_resolved:
                    new_resolved.append(ResolvedLink(
                        claim=link.claim,
                        series_a=series_a,
                        series_b=series_b,
                        query_type=self._determine_query_type(link),
                        direction=link.direction
                    ))
            else:
                # Still ambiguous
                if not series_a:
                    remaining_ambiguities.append(Ambiguity(
                        concept=link.concept_a,
                        candidates=[]
                    ))
                if not series_b:
                    remaining_ambiguities.append(Ambiguity(
                        concept=link.concept_b,
                        candidates=[]
                    ))

        return QueryTranslatorOutput(
            links=output.links,
            resolved=new_resolved,
            ambiguities=remaining_ambiguities
        )

    def _get_series_for_concept(
        self,
        concept: str,
        clarifications: dict,
        output: QueryTranslatorOutput
    ) -> Optional[str]:
        """Get series ID for concept, using clarifications if needed"""
        # Check clarifications first
        if concept in clarifications:
            return clarifications[concept]

        # Try registry resolution
        resolution = self._resolve_concept(concept)
        if resolution["status"] == "resolved":
            return resolution["series_id"]

        # Check if already resolved in output
        for resolved in output.resolved:
            if concept in [resolved.series_a, resolved.series_b]:
                # This shouldn't happen, but handle it
                pass

        return None

    async def _extract_links(self, thesis: Thesis) -> List[CausalLink]:
        """Extract causal links via LLM"""
        prompt = EXTRACT_LINKS_USER.format(
            title=thesis.title,
            hypothesis=thesis.hypothesis,
            drivers=", ".join(thesis.drivers) if thesis.drivers else "None specified",
            disconfirmers=", ".join(thesis.disconfirmers) if thesis.disconfirmers else "None specified"
        )

        messages = [
            {"role": "system", "content": EXTRACT_LINKS_SYSTEM},
            {"role": "user", "content": prompt}
        ]

        try:
            logger.debug("Extracting links for thesis: %s...", thesis.title[:50])
            response = await asyncio.wait_for(
                self._llm.chat(messages),
                timeout=30.0
            )

            # Extract content from dict response
            content = response.get("content", "")
            if not content:
                logger.warning("Empty LLM response for link extraction")
                return []

            logger.debug("LLM response length: %d chars", len(content))
            json_str = extract_json(content)
            parsed = json.loads(json_str)

            if not parsed or "links" not in parsed:
                logger.warning("No links found in LLM response")
                return []

            links = []
            for link_data in parsed["links"]:
                try:
                    links.append(CausalLink(**link_data))
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning("Failed to parse link: %s, data: %s", e, link_data)
                    continue

            return links

        except asyncio.TimeoutError:
            logger.error("LLM timeout during link extraction")
            return []
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error extracting links: %s", e, exc_info=True)
            return []

    def _resolve_concept(self, concept: str) -> dict:
        """
        Resolve a concept to a series.

        Returns:
            {"status": "resolved", "series_id": "..."} or
            {"status": "ambiguous", "candidates": [...]} or
            {"status": "not_found"}
        """
        candidates = self._registry.search_by_concept(concept)

        if len(candidates) == 0:
            return {"status": "not_found"}
        if len(candidates) == 1:
            return {"status": "resolved", "series_id": candidates[0].id}
        return {
            "status": "ambiguous",
            "candidates": [
                {"id": c.id, "name": c.name, "source": c.source}
                for c in candidates
            ]
        }

    def _determine_query_type(self, _link: CausalLink) -> str:
        """Determine what quant query to run for this link"""
        # For now, default to correlation
        # Could be extended to detect conditional relationships
        return "correlation"
