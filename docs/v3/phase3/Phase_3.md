# V3 Phase 3: LLM Layer

## Overview

This phase implements the LLM components for V3:
- **QueryTranslator**: Extracts causal links from thesis text, resolves concepts to series
- **CritiqueEngine**: Runs 6-dimension critique with summary + drill-down

These power Screens 1 (Draft & Validate) and 2 (Critique).

## Prerequisites

- Phase 0 complete (models, series registry)
- Phase 1 complete (QuantService)
- Existing OpenAI integration (`OpenAILLMClient`, `extract_json`)

---

## Task 1: Query Translator

**File:** `src/voyager/llm/query_translator.py` (NEW FILE)

```python
"""
Query Translator for V3 thesis validation.

Extracts causal claims from thesis text and resolves concepts to data series.
"""
from typing import Protocol, List, Optional
import json

from voyager.models.v3 import CausalLink, ResolvedLink, Ambiguity, QueryTranslatorOutput
from voyager.models.thesis import ThesisV3
from voyager.data.series_registry import SeriesRegistry
from voyager.llm.tools import extract_json


class LLMClientProtocol(Protocol):
    """Protocol for LLM client"""
    async def chat(self, messages: List[dict]) -> str:
        ...


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
    
    async def extract_and_resolve(self, thesis: ThesisV3) -> QueryTranslatorOutput:
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
                    query_type=self._determine_query_type(link)
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
        thesis: ThesisV3,
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
            series_a = self._get_series_for_concept(link.concept_a, clarifications)
            series_b = self._get_series_for_concept(link.concept_b, clarifications)
            
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
                        query_type=self._determine_query_type(link)
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
        clarifications: dict
    ) -> Optional[str]:
        """Get series ID for concept, using clarifications if needed"""
        # Check clarifications first
        if concept in clarifications:
            return clarifications[concept]
        
        # Try registry resolution
        resolution = self._resolve_concept(concept)
        if resolution["status"] == "resolved":
            return resolution["series_id"]
        
        return None
    
    async def _extract_links(self, thesis: ThesisV3) -> List[CausalLink]:
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
        
        response = await self._llm.chat(messages)
        parsed = extract_json(response)
        
        if not parsed or "links" not in parsed:
            return []
        
        return [CausalLink(**link) for link in parsed["links"]]
    
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
        elif len(candidates) == 1:
            return {"status": "resolved", "series_id": candidates[0].id}
        else:
            return {
                "status": "ambiguous",
                "candidates": [
                    {"id": c.id, "name": c.name, "source": c.source}
                    for c in candidates
                ]
            }
    
    def _determine_query_type(self, link: CausalLink) -> str:
        """Determine what quant query to run for this link"""
        # For now, default to correlation
        # Could be extended to detect conditional relationships
        return "correlation"
```

---

## Task 2: Critique Engine

**File:** `src/voyager/llm/critique_engine.py` (NEW FILE)

```python
"""
Critique Engine for V3 thesis review.

Runs structured critique across 6 dimensions with summary + drill-down.
"""
from typing import List, Optional
import json

from voyager.models.v3 import CritiqueSummary, Concern, CritiqueResponse
from voyager.models.thesis import ThesisV3, LogicValidation, LogicLink
from voyager.models.v3 import BacktestResult
from voyager.llm.tools import extract_json


# ===========================================
# Prompts
# ===========================================

CRITIQUE_SYSTEM = """You are a senior macro investment analyst conducting a structured critique of an investment thesis.

Your critique must be:
- Specific and actionable
- Based on evidence (data provided, logical analysis)
- Balanced (acknowledge strengths, highlight weaknesses)
- Helpful (aim to improve the thesis, not just criticize)

You are critiquing across 6 dimensions:
1. logical_coherence: Does the argument follow logically? Are there gaps?
2. causal_mechanism: Is the causal chain clearly specified? How does A lead to B?
3. hidden_assumptions: What's being taken for granted that might not hold?
4. empirical_grounding: Does the data support the claimed relationships?
5. historical_precedent: Has this type of thesis worked before? Relevant analogs?
6. expression_fit: Does the proposed expression capture the thesis? Is it optimal?

IMPORTANT:
- For dimensions 4, 5, 6: Reference the provided data. Don't make up numbers.
- If data is missing for a dimension, note it as "insufficient_data" rather than guessing.
- Be direct. Don't hedge excessively."""


CRITIQUE_SUMMARY_USER = """Critique this investment thesis across all 6 dimensions.

THESIS:
Title: {title}
Hypothesis: {hypothesis}
Drivers: {drivers}
Disconfirmers: {disconfirmers}
Expression: {expression}

LOGIC VALIDATION DATA:
{validation_data}

{backtest_section}

Respond with JSON:
{{
  "concerns": [
    {{
      "dimension": "one of: logical_coherence, causal_mechanism, hidden_assumptions, empirical_grounding, historical_precedent, expression_fit",
      "severity": "high" | "medium" | "low",
      "summary": "one sentence describing the specific concern"
    }}
  ],
  "opening_message": "2-3 sentences summarizing which areas need attention and offering to drill down. Be conversational."
}}

Only include dimensions where you have genuine concerns. A good thesis might have 0-2 concerns.
If you have no concerns, return empty concerns array and say so in opening_message."""


DRILLDOWN_SYSTEM = """You are continuing a critique conversation about an investment thesis.

You are focused on the "{dimension}" dimension.

Your responses should:
- Be specific and reference provided data
- Engage with what the PM said
- Acknowledge if their response resolves your concern
- Suggest concrete thesis edits if appropriate
- Stay focused on this dimension (don't drift to others)

If you think the thesis should be edited, suggest it explicitly."""


DRILLDOWN_USER = """THESIS CONTEXT:
Title: {title}
Hypothesis: {hypothesis}
Drivers: {drivers}
Disconfirmers: {disconfirmers}
Expression: {expression}

VALIDATION DATA:
{validation_data}

Continue the conversation. The PM just said:
"{user_message}"

Respond with JSON:
{{
  "message": "your response to the PM",
  "thesis_edit_suggestion": null or {{
    "field": "hypothesis" | "drivers" | "disconfirmers" | "expression",
    "action": "replace" | "add" | "remove",
    "value": "the suggested content"
  }}
}}"""


# ===========================================
# Critique Engine
# ===========================================

class CritiqueEngine:
    """
    Runs structured thesis critique.
    
    Two modes:
    1. Summary: Critique across all 6 dimensions, return summary of concerns
    2. Drill-down: Continue conversation on a specific dimension
    
    Usage:
        engine = CritiqueEngine(llm_client)
        
        # Get initial summary
        summary = await engine.critique(thesis, validation, backtest)
        
        # Drill down on a concern
        response = await engine.drill_down(
            thesis, "empirical_grounding", 
            user_message="I think the correlation is actually stronger...",
            conversation_history=[...],
            validation=validation
        )
    """
    
    DIMENSIONS = [
        "logical_coherence",
        "causal_mechanism",
        "hidden_assumptions",
        "empirical_grounding",
        "historical_precedent",
        "expression_fit"
    ]
    
    def __init__(self, llm_client):
        self._llm = llm_client
    
    async def critique(
        self,
        thesis: ThesisV3,
        validation: Optional[LogicValidation] = None,
        backtest: Optional[BacktestResult] = None
    ) -> CritiqueSummary:
        """
        Generate critique summary across all dimensions.
        
        Args:
            thesis: The thesis to critique
            validation: Logic validation results (from Screen 1)
            backtest: Backtest results (if available)
            
        Returns:
            CritiqueSummary with concerns and opening message
        """
        prompt = CRITIQUE_SUMMARY_USER.format(
            title=thesis.title,
            hypothesis=thesis.hypothesis,
            drivers=", ".join(thesis.drivers) if thesis.drivers else "None",
            disconfirmers=", ".join(thesis.disconfirmers) if thesis.disconfirmers else "None",
            expression=self._format_expression(thesis.expression),
            validation_data=self._format_validation(validation),
            backtest_section=self._format_backtest(backtest)
        )
        
        messages = [
            {"role": "system", "content": CRITIQUE_SYSTEM},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._llm.chat(messages)
        parsed = extract_json(response)
        
        if not parsed:
            return CritiqueSummary(
                concerns=[],
                opening_message="I encountered an issue analyzing this thesis. Please try again."
            )
        
        concerns = [
            Concern(**c) for c in parsed.get("concerns", [])
            if c.get("dimension") in self.DIMENSIONS
        ]
        
        return CritiqueSummary(
            concerns=concerns,
            opening_message=parsed.get("opening_message", "Ready to discuss this thesis.")
        )
    
    async def drill_down(
        self,
        thesis: ThesisV3,
        dimension: str,
        user_message: str,
        conversation_history: List[dict],
        validation: Optional[LogicValidation] = None
    ) -> CritiqueResponse:
        """
        Continue drill-down conversation on a specific dimension.
        
        Args:
            thesis: The thesis being discussed
            dimension: Which dimension to focus on
            user_message: PM's latest message
            conversation_history: Previous messages in this drill-down
            validation: Logic validation results
            
        Returns:
            CritiqueResponse with message and optional edit suggestion
        """
        if dimension not in self.DIMENSIONS:
            raise ValueError(f"Invalid dimension: {dimension}")
        
        system = DRILLDOWN_SYSTEM.format(dimension=dimension)
        
        user_prompt = DRILLDOWN_USER.format(
            title=thesis.title,
            hypothesis=thesis.hypothesis,
            drivers=", ".join(thesis.drivers) if thesis.drivers else "None",
            disconfirmers=", ".join(thesis.disconfirmers) if thesis.disconfirmers else "None",
            expression=self._format_expression(thesis.expression),
            validation_data=self._format_validation(validation),
            user_message=user_message
        )
        
        # Build message history
        messages = [{"role": "system", "content": system}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_prompt})
        
        response = await self._llm.chat(messages)
        parsed = extract_json(response)
        
        if not parsed:
            return CritiqueResponse(
                message="I'm having trouble formulating a response. Could you rephrase?",
                thesis_edit_suggestion=None
            )
        
        return CritiqueResponse(
            message=parsed.get("message", ""),
            thesis_edit_suggestion=parsed.get("thesis_edit_suggestion")
        )
    
    def _format_expression(self, expression: List) -> str:
        """Format expression legs for prompt"""
        if not expression:
            return "No expression defined"
        
        parts = []
        for leg in expression:
            if hasattr(leg, 'dict'):
                leg = leg.dict()
            direction = leg.get("direction", "LONG")
            asset = leg.get("asset", "?")
            size = leg.get("size_pct", 0)
            parts.append(f"{direction} {asset} ({size}%)")
        
        return ", ".join(parts)
    
    def _format_validation(self, validation: Optional[LogicValidation]) -> str:
        """Format validation results for prompt"""
        if not validation or not validation.links:
            return "No validation data available."
        
        lines = []
        for link in validation.links:
            interp = link.interpretation
            emoji = "✓" if interp == "supports" else "⚠" if interp == "weak" else "✗"
            lines.append(
                f"{emoji} {link.claim}\n"
                f"   {link.query_type}({link.series_a}, {link.series_b}) = {link.result:.3f} [{interp}]"
            )
        
        return "\n".join(lines)
    
    def _format_backtest(self, backtest: Optional[BacktestResult]) -> str:
        """Format backtest results for prompt"""
        if not backtest:
            return ""
        
        return f"""
BACKTEST RESULTS ({backtest.period_start} to {backtest.period_end}):
- Total Return: {backtest.metrics.total_return:.2%}
- CAGR: {backtest.metrics.cagr:.2%}
- Volatility: {backtest.metrics.volatility:.2%}
- Sharpe Ratio: {backtest.metrics.sharpe:.2f}
- Max Drawdown: {backtest.metrics.max_drawdown:.2%}
"""
```

---

## Task 3: Validation Service

**File:** `src/voyager/services/v3/validation_service.py` (NEW FILE)

```python
"""
Validation Service for V3 Screen 1.

Orchestrates the thesis logic validation flow:
1. Extract causal links via QueryTranslator
2. Resolve concepts to series (or return ambiguities)
3. Run quant queries on resolved links
4. Persist and return results
"""
from datetime import datetime
from typing import Optional
import uuid

from voyager.llm.query_translator import QueryTranslator
from voyager.quant.quant_service import QuantService
from voyager.models.v3 import ValidationResult, Ambiguity
from voyager.models.thesis import ThesisV3, LogicValidation, LogicLink
from voyager.repositories.logic_validation_repository import LogicValidationRepository
from voyager.repositories.thesis_repository import ThesisRepository


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
    
    async def validate(self, thesis: ThesisV3) -> ValidationResult:
        """
        Run logic validation on a thesis.
        
        Returns:
            ValidationResult with status and either links or ambiguities
        """
        # Step 1: Extract and resolve
        try:
            output = await self._translator.extract_and_resolve(thesis)
        except Exception as e:
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
            except Exception as e:
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
            created_at=datetime.utcnow().isoformat()
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
        thesis: ThesisV3,
        clarifications: dict  # {concept: series_id}
    ) -> ValidationResult:
        """
        Re-run validation with PM clarifications for ambiguous concepts.
        """
        # Re-extract with clarifications
        try:
            output = await self._translator.resolve_with_clarifications(thesis, clarifications)
        except Exception as e:
            return ValidationResult(
                status="parse_failed",
                error_message=f"Failed to resolve with clarifications: {str(e)}"
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
            except Exception as e:
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
            created_at=datetime.utcnow().isoformat()
        )
        self._validation_repo.insert(validation)
        
        self._thesis_repo.update_status(thesis.id, "VALIDATED")
        
        return ValidationResult(
            status="complete",
            links=links
        )
    
    async def _run_quant_query(self, resolved) -> LogicLink:
        """Run the appropriate quant query for a resolved link"""
        if resolved.query_type == "correlation":
            # Use relationship_strength for richer interpretation
            result = self._quant.relationship_strength(
                resolved.series_a,
                resolved.series_b,
                expected_direction="negative"  # Default, could be smarter
            )
            
            return LogicLink(
                claim=resolved.claim,
                series_a=resolved.series_a,
                series_b=resolved.series_b,
                query_type="correlation",
                result=result["correlation"],
                interpretation=result["interpretation"]
            )
        else:
            # Fallback to simple correlation
            result = self._quant.correlation(resolved.series_a, resolved.series_b)
            interpretation = self._interpret_correlation(result.correlation)
            
            return LogicLink(
                claim=resolved.claim,
                series_a=resolved.series_a,
                series_b=resolved.series_b,
                query_type=resolved.query_type,
                result=result.correlation,
                interpretation=interpretation
            )
    
    def _interpret_correlation(self, corr: float) -> str:
        """Simple correlation interpretation"""
        abs_corr = abs(corr)
        if abs_corr >= 0.6:
            return "supports"
        elif abs_corr >= 0.3:
            return "weak"
        else:
            return "contradicts"
    
    def get_latest_validation(self, thesis_id: str) -> Optional[LogicValidation]:
        """Get most recent validation for a thesis"""
        return self._validation_repo.get_by_thesis(thesis_id)
```

---

## Task 4: Critique Service

**File:** `src/voyager/services/v3/critique_service.py` (NEW FILE)

```python
"""
Critique Service for V3 Screen 2.

Orchestrates the thesis critique flow:
1. Generate initial critique summary
2. Handle drill-down conversations
3. Track conversation history
4. Apply thesis edits
"""
from datetime import datetime
from typing import List, Optional
import uuid
import json

from voyager.llm.critique_engine import CritiqueEngine
from voyager.models.v3 import CritiqueSummary, CritiqueResponse, BacktestResult
from voyager.models.thesis import ThesisV3, LogicValidation, ThesisSnapshot
from voyager.repositories.thesis_repository import ThesisRepository
from voyager.repositories.thesis_snapshot_repository import ThesisSnapshotRepository
from voyager.repositories.logic_validation_repository import LogicValidationRepository
from voyager.repositories.backtest_result_repository import BacktestResultRepository


class CritiqueService:
    """
    Orchestrates thesis critique workflow.
    
    Usage:
        # Start critique
        summary = await service.start(thesis_id)
        
        # Drill down on a concern
        response = await service.continue_conversation(
            thesis_id, 
            dimension="empirical_grounding",
            user_message="I think..."
        )
        
        # Complete critique
        thesis = await service.complete(thesis_id)
    """
    
    def __init__(
        self,
        critique_engine: CritiqueEngine,
        thesis_repo: ThesisRepository,
        snapshot_repo: ThesisSnapshotRepository,
        validation_repo: LogicValidationRepository,
        backtest_repo: BacktestResultRepository
    ):
        self._engine = critique_engine
        self._thesis_repo = thesis_repo
        self._snapshot_repo = snapshot_repo
        self._validation_repo = validation_repo
        self._backtest_repo = backtest_repo
        
        # In-memory conversation storage (could be moved to DB)
        self._conversations: dict = {}  # thesis_id -> {dimension -> [messages]}
    
    async def start(self, thesis_id: str) -> CritiqueSummary:
        """
        Start critique session for a thesis.
        
        Creates pre-critique snapshot and generates initial critique summary.
        """
        # Load thesis
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        # Create pre-critique snapshot
        self._create_snapshot(thesis, "pre_critique")
        
        # Load validation and backtest if available
        validation = self._validation_repo.get_by_thesis(thesis_id)
        backtest = self._backtest_repo.get_latest_by_thesis(thesis_id)
        
        # Generate critique
        summary = await self._engine.critique(
            thesis=thesis,
            validation=validation,
            backtest=backtest
        )
        
        # Initialize conversation storage
        self._conversations[thesis_id] = {}
        
        return summary
    
    async def continue_conversation(
        self,
        thesis_id: str,
        dimension: str,
        user_message: str
    ) -> CritiqueResponse:
        """
        Continue drill-down conversation on a specific dimension.
        """
        # Load thesis
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        # Get or initialize conversation history for this dimension
        if thesis_id not in self._conversations:
            self._conversations[thesis_id] = {}
        if dimension not in self._conversations[thesis_id]:
            self._conversations[thesis_id][dimension] = []
        
        history = self._conversations[thesis_id][dimension]
        
        # Load validation
        validation = self._validation_repo.get_by_thesis(thesis_id)
        
        # Get response
        response = await self._engine.drill_down(
            thesis=thesis,
            dimension=dimension,
            user_message=user_message,
            conversation_history=history,
            validation=validation
        )
        
        # Update history
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response.message})
        
        return response
    
    def apply_edit_suggestion(
        self,
        thesis_id: str,
        suggestion: dict
    ) -> ThesisV3:
        """
        Apply a suggested edit to the thesis.
        
        Args:
            thesis_id: Thesis to edit
            suggestion: {"field": "...", "action": "...", "value": "..."}
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        field = suggestion.get("field")
        action = suggestion.get("action", "replace")
        value = suggestion.get("value")
        
        if field not in ["hypothesis", "drivers", "disconfirmers", "expression"]:
            raise ValueError(f"Cannot edit field: {field}")
        
        # Apply edit based on field type
        if field == "hypothesis":
            # Direct replacement
            updates = {"hypothesis": value}
        elif field in ["drivers", "disconfirmers"]:
            current = getattr(thesis, field, [])
            if action == "replace":
                updates = {field: value if isinstance(value, list) else [value]}
            elif action == "add":
                updates = {field: current + [value]}
            elif action == "remove":
                updates = {field: [x for x in current if x != value]}
            else:
                updates = {field: value}
        else:
            # expression - more complex, just replace for now
            updates = {field: value}
        
        # Update via repo (you'd implement this)
        # For now, this is a placeholder
        return thesis
    
    async def complete(self, thesis_id: str) -> ThesisV3:
        """
        Complete critique session.
        
        Creates post-critique snapshot and transitions status.
        """
        thesis = self._thesis_repo.get_by_id(thesis_id)
        if thesis is None:
            raise ValueError(f"Thesis not found: {thesis_id}")
        
        # Create post-critique snapshot
        self._create_snapshot(thesis, "post_critique")
        
        # Update status
        self._thesis_repo.update_status(thesis_id, "CRITIQUED")
        
        # Clear conversation history
        if thesis_id in self._conversations:
            del self._conversations[thesis_id]
        
        return self._thesis_repo.get_by_id(thesis_id)
    
    def _create_snapshot(self, thesis: ThesisV3, snapshot_type: str) -> ThesisSnapshot:
        """Create a snapshot of the current thesis state"""
        # Convert thesis to dict for storage
        if hasattr(thesis, 'dict'):
            content = thesis.dict()
        else:
            content = {
                "id": thesis.id,
                "title": thesis.title,
                "hypothesis": thesis.hypothesis,
                "drivers": thesis.drivers,
                "disconfirmers": thesis.disconfirmers,
                "expression": [leg.dict() if hasattr(leg, 'dict') else leg for leg in thesis.expression],
                "status": thesis.status
            }
        
        snapshot = ThesisSnapshot(
            id=f"snap_{uuid.uuid4().hex[:12]}",
            thesis_id=thesis.id,
            snapshot_type=snapshot_type,
            content=content,
            created_at=datetime.utcnow().isoformat()
        )
        
        return self._snapshot_repo.insert(snapshot)
    
    def get_conversation_history(self, thesis_id: str, dimension: str) -> List[dict]:
        """Get conversation history for a dimension"""
        if thesis_id not in self._conversations:
            return []
        return self._conversations.get(thesis_id, {}).get(dimension, [])
```

---

## Task 5: Integration

**File:** `src/voyager/api/deps.py`

Add factory functions:

```python
# Add to existing deps.py

from voyager.llm.query_translator import QueryTranslator
from voyager.llm.critique_engine import CritiqueEngine
from voyager.services.v3.validation_service import ValidationService
from voyager.services.v3.critique_service import CritiqueService

_query_translator_instance: Optional[QueryTranslator] = None
_critique_engine_instance: Optional[CritiqueEngine] = None
_validation_service_instance: Optional[ValidationService] = None
_critique_service_instance: Optional[CritiqueService] = None


def get_query_translator_instance() -> QueryTranslator:
    global _query_translator_instance
    if _query_translator_instance is None:
        llm_client = get_orchestrator_client_instance()._llm_client  # Reuse existing
        registry = get_series_registry_instance()
        _query_translator_instance = QueryTranslator(llm_client, registry)
    return _query_translator_instance


def get_critique_engine_instance() -> CritiqueEngine:
    global _critique_engine_instance
    if _critique_engine_instance is None:
        llm_client = get_orchestrator_client_instance()._llm_client
        _critique_engine_instance = CritiqueEngine(llm_client)
    return _critique_engine_instance


def get_validation_service_instance() -> ValidationService:
    global _validation_service_instance
    if _validation_service_instance is None:
        from voyager.db import get_engine
        engine = get_engine()
        
        _validation_service_instance = ValidationService(
            query_translator=get_query_translator_instance(),
            quant_service=get_quant_service_instance(),
            validation_repo=LogicValidationRepository(engine),
            thesis_repo=get_data_access_instance().thesis_repo
        )
    return _validation_service_instance


def get_critique_service_instance() -> CritiqueService:
    global _critique_service_instance
    if _critique_service_instance is None:
        from voyager.db import get_engine
        engine = get_engine()
        
        _critique_service_instance = CritiqueService(
            critique_engine=get_critique_engine_instance(),
            thesis_repo=get_data_access_instance().thesis_repo,
            snapshot_repo=ThesisSnapshotRepository(engine),
            validation_repo=LogicValidationRepository(engine),
            backtest_repo=BacktestResultRepository(engine)
        )
    return _critique_service_instance
```

---

## Verification

After completing this phase:

1. Test QueryTranslator:
   ```python
   # Manual test
   thesis = ThesisV3(
       id="test",
       title="Gold vs Real Yields",
       hypothesis="Rising real yields will pressure gold prices",
       drivers=["Fed tightening", "Inflation falling"],
       disconfirmers=["Flight to safety"],
       expression=[{"asset": "GLD", "direction": "SHORT", "size_pct": 100}],
       # ... other fields
   )
   output = await translator.extract_and_resolve(thesis)
   print(output.links)
   print(output.resolved)
   print(output.ambiguities)
   ```

2. Test CritiqueEngine:
   ```python
   summary = await engine.critique(thesis, validation)
   print(summary.opening_message)
   for concern in summary.concerns:
       print(f"  [{concern.severity}] {concern.dimension}: {concern.summary}")
   ```

3. Run full validation flow:
   ```python
   result = await validation_service.validate(thesis)
   print(result.status)
   print(result.links)
   ```

---

## Dependencies

No new dependencies. Uses existing:
- OpenAI client
- `extract_json` from `voyager.llm.tools`

---

## Next Phase

Phase 4: Sizing Service — implements the sizing calculation and portfolio impact analysis for Screen 4.