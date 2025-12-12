"""
Critique Engine for V3 thesis review.

Runs structured critique across 6 dimensions with summary + drill-down.
"""
from typing import List, Optional
import json
import logging
import asyncio

from voyager.models.v3 import CritiqueSummary, Concern, CritiqueResponse, BacktestResult
from voyager.models.thesis import Thesis, LogicValidation
from voyager.llm.tools import extract_json

logger = logging.getLogger(__name__)


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
        thesis: Thesis,
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

        try:
            logger.debug("Generating critique for thesis: %s...", thesis.title[:50])
            response = await asyncio.wait_for(
                self._llm.chat(messages),
                timeout=30.0
            )

            content = response.get("content", "")
            if not content:
                logger.warning("Empty LLM response for critique")
                return CritiqueSummary(
                    concerns=[],
                    opening_message="I encountered an issue analyzing this thesis. Please try again."
                )

            logger.debug("Critique response length: %d chars", len(content))
            json_str = extract_json(content)
            parsed = json.loads(json_str)

            if not parsed:
                logger.warning("Failed to parse critique response")
                return CritiqueSummary(
                    concerns=[],
                    opening_message="I had trouble analyzing this thesis. Could you rephrase?"
                )

            concerns = []
            for c in parsed.get("concerns", []):
                if c.get("dimension") in self.DIMENSIONS:
                    try:
                        concerns.append(Concern(**c))
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.warning("Failed to parse concern: %s, data: %s", e, c)
                        continue

            return CritiqueSummary(
                concerns=concerns,
                opening_message=parsed.get("opening_message", "Ready to discuss this thesis.")
            )

        except asyncio.TimeoutError:
            logger.error("LLM timeout during critique")
            return CritiqueSummary(
                concerns=[],
                opening_message="I encountered a timeout while analyzing this thesis. Please try again."
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error generating critique: %s", e, exc_info=True)
            
            # Check for common errors and provide specific messages
            error_str = str(e).lower()
            if "api_key" in error_str or "authentication" in error_str or "401" in error_str:
                message = "LLM authentication failed. Check OPENAI_API_KEY is set correctly."
            elif "rate_limit" in error_str or "429" in error_str:
                message = "LLM rate limit exceeded. Please try again in a moment."
            elif "timeout" in error_str:
                message = "LLM request timed out. Please try again."
            else:
                # Truncate long error messages but keep first 100 chars
                error_preview = str(e)[:100]
                message = f"Error analyzing thesis: {error_preview}"
            
            return CritiqueSummary(
                concerns=[],
                opening_message=message
            )

    async def drill_down(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        thesis: Thesis,
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

        try:
            logger.debug("Drill-down on %s for thesis: %s...", dimension, thesis.title[:50])
            response = await asyncio.wait_for(
                self._llm.chat(messages),
                timeout=30.0
            )

            content = response.get("content", "")
            if not content:
                logger.warning("Empty LLM response for drill-down")
                return CritiqueResponse(
                    message="I'm having trouble formulating a response. Could you rephrase?",
                    thesis_edit_suggestion=None
                )

            json_str = extract_json(content)
            parsed = json.loads(json_str)

            if not parsed:
                logger.warning("Failed to parse drill-down response")
                return CritiqueResponse(
                    message="I'm having trouble understanding your response. Could you rephrase?",
                    thesis_edit_suggestion=None
                )

            return CritiqueResponse(
                message=parsed.get("message", ""),
                thesis_edit_suggestion=parsed.get("thesis_edit_suggestion")
            )

        except asyncio.TimeoutError:
            logger.error("LLM timeout during drill-down")
            return CritiqueResponse(
                message="I encountered a timeout. Please try again.",
                thesis_edit_suggestion=None
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in drill-down: %s", e, exc_info=True)
            
            # Check for common errors and provide specific messages
            error_str = str(e).lower()
            if "api_key" in error_str or "authentication" in error_str or "401" in error_str:
                message = "LLM authentication failed. Check OPENAI_API_KEY is set correctly."
            elif "rate_limit" in error_str or "429" in error_str:
                message = "LLM rate limit exceeded. Please try again in a moment."
            elif "timeout" in error_str:
                message = "LLM request timed out. Please try again."
            else:
                # Truncate long error messages but keep first 100 chars
                error_preview = str(e)[:100]
                message = f"Error in conversation: {error_preview}"
            
            return CritiqueResponse(
                message=message,
                thesis_edit_suggestion=None
            )

    def _format_expression(self, expression: List) -> str:
        """Format expression legs for prompt"""
        if not expression:
            return "No expression defined"

        parts = []
        for leg in expression:
            if hasattr(leg, 'model_dump'):
                leg = leg.model_dump()
            elif hasattr(leg, 'dict'):
                leg = leg.dict()  # Fallback for older Pydantic
            elif hasattr(leg, '__dict__'):
                leg = leg.__dict__

            direction = leg.get("direction", "LONG")
            if isinstance(direction, str):
                direction_str = direction
            else:
                # Handle Direction enum
                direction_str = str(direction).rsplit('.', maxsplit=1)[-1] if '.' in str(direction) else "LONG"

            asset = leg.get("asset", "?")
            size = leg.get("size_pct", 0)
            parts.append(f"{direction_str} {asset} ({size}%)")

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
