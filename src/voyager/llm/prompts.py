"""
E3: Prompt builders for LLM tools.

Each builder creates a user prompt string that will be passed to SessionOrchestrator.
The orchestrator adds the system prompt, so these builders only create user content.
"""
import json
from typing import List

from voyager.models.thesis import Thesis
from voyager.models.evaluation import ThesisEvaluationResult
from voyager.models.observation import Observation
from voyager.models.llm_inputs import DailyContext


def build_thesis_review_prompt(thesis: Thesis, evaluation: ThesisEvaluationResult) -> str:
    """
    Build prompt for llm_review_thesis tool.

    Args:
        thesis: Thesis to review
        evaluation: E2 evaluation results

    Returns:
        User prompt string
    """
    # Summarize evaluation metrics (not full time series)
    perf = evaluation.performance
    risk = evaluation.risk_metrics
    scenarios_summary = ", ".join(
        [f"{s.name}: {s.pnl_pct:.1f}%" for s in evaluation.scenarios]
    )

    lines = [
        "You are a macro investment analyst reviewing an investment thesis against its quantified evaluation.",
        "",
        "Task:",
        "1) Critique the logical soundness and structure of the thesis.",
        "2) Pose clarifying questions about assumptions or missing information.",
        "3) Flag concrete risk areas based on the evaluation metrics.",
        "",
        "Rules:",
        "- Use ONLY the information explicitly provided below.",
        "- Do not use outside knowledge.",
        "- If you cannot answer from the provided data, set 'insufficient_context': true and keep your answer minimal.",
        "",
        "Respond with a single valid JSON object matching this schema and nothing else:",
        json.dumps({
            "critique": "string - critical analysis",
            "questions": ["string - clarifying questions"],
            "risk_flags": ["string - risk areas"],
            "insufficient_context": False,
        }, indent=2),
        "",
        "---",
        "",
        "THESIS:",
        f"Title: {thesis.title}",
        f"Hypothesis: {thesis.hypothesis}",
        f"Drivers: {', '.join(thesis.drivers)}",
        f"Disconfirmers: {', '.join(thesis.disconfirmers)}",
        "",
        "Expression Legs:",
    ]

    for leg in thesis.expression:
        lines.append(f"  - {leg.direction} {leg.asset} ({leg.size_pct}%)")

    lines.extend([
        "",
        "EVALUATION METRICS:",
        f"Total Return: {perf.get('total_return', 0):.2f}%",
        f"CAGR: {perf.get('cagr', 0):.2f}%",
        f"Volatility: {perf.get('volatility', 0):.2f}%",
        f"Sharpe: {perf.get('sharpe', 0):.2f}",
        f"Max Drawdown: {perf.get('max_drawdown', 0):.2f}%",
        f"Max Weight: {risk.get('max_weight_pct', 0):.2f}%",
        f"VaR 95: {risk.get('VaR_95', 0):.2f}%",
        "",
        "Scenario Impacts:",
        scenarios_summary,
    ])

    return "\n".join(lines)


def build_cross_theses_prompt(theses: List[Thesis]) -> str:
    """
    Build prompt for llm_cross_theses tool.

    Args:
        theses: List of theses to analyze

    Returns:
        User prompt string
    """
    lines = [
        "You analyze relationships between investment theses.",
        "",
        "Task:",
        "1) Identify overlaps: common themes, exposures, or assumptions.",
        "2) Identify contradictions: directly opposing assumptions or exposures.",
        "3) Identify gaps: missing angles, blind spots, or questions none address.",
        "",
        "Rules:",
        "- Use ONLY the information explicitly provided below.",
        "- Do not use outside knowledge.",
        "- If you cannot analyze from the provided data, set 'insufficient_context': true and keep your answer minimal.",
        "",
        "Respond with a single valid JSON object matching this schema and nothing else:",
        json.dumps({
            "overlaps": ["string - common themes"],
            "contradictions": ["string - opposing assumptions"],
            "gaps": ["string - missing angles"],
            "insufficient_context": False,
        }, indent=2),
        "",
        "---",
        "",
        "THESES:",
    ]

    for i, thesis in enumerate(theses, 1):
        legs_summary = ", ".join(
            [f"{leg.direction} {leg.asset}" for leg in thesis.expression]
        )
        lines.extend([
            f"",
            f"Thesis {i} (ID: {thesis.id}):",
            f"  Title: {thesis.title}",
            f"  Hypothesis: {thesis.hypothesis}",
            f"  Drivers: {', '.join(thesis.drivers)}",
            f"  Expression: {legs_summary}",
        ])

    return "\n".join(lines)


def build_intuition_prompt(question: str, observations: List[Observation]) -> str:
    """
    Build prompt for llm_query_intuition tool.

    Args:
        question: User question
        observations: Observations to use as context

    Returns:
        User prompt string
    """
    lines = [
        "You answer the user's question using only the provided observations.",
        "",
        "Task:",
        "1) If possible, synthesize an answer citing observation IDs.",
        "2) If the answer is not contained in the observations, you must set 'insufficient_context': true and provide minimal/empty answer.",
        "",
        "Rules:",
        "- Use ONLY the information in the observations below.",
        "- Do not use outside knowledge.",
        "- Cite observation IDs in the 'references' field (e.g., ['obs1', 'obs2']).",
        "- If you cannot answer, do not guess; set 'insufficient_context': true.",
        "",
        "Respond with a single valid JSON object matching this schema and nothing else:",
        json.dumps({
            "answer": "string - synthesized answer",
            "references": ["string - observation IDs"],
            "insufficient_context": False,
        }, indent=2),
        "",
        "---",
        "",
        "QUESTION:",
        question,
        "",
        "OBSERVATIONS:",
    ]

    for obs in observations:
        lines.append(f"[{obs.id}] {obs.timestamp.isoformat()}: {obs.text}")

    return "\n".join(lines)


def build_daily_summary_prompt(context: DailyContext) -> str:
    """
    Build prompt for llm_daily_summary tool.

    Args:
        context: Daily context snapshot

    Returns:
        User prompt string
    """
    lines = [
        "You write a concise daily summary for a portfolio manager, using only the provided daily context.",
        "",
        "Task:",
        "1) Identify 2-5 key narratives about what mattered today.",
        "2) Highlight concrete risk items to watch.",
        "3) Reference thesis IDs that were impacted (using IDs from the active_theses list).",
        "",
        "Rules:",
        "- Use ONLY the information explicitly provided below.",
        "- Do not use outside knowledge.",
        "- Reference thesis IDs in 'thesis_references' (e.g., ['thesis_1', 'thesis_3']).",
        "- If you cannot summarize from the provided data, set 'insufficient_context': true and keep your answer minimal.",
        "",
        "Respond with a single valid JSON object matching this schema and nothing else:",
        json.dumps({
            "key_narratives": ["string - storylines"],
            "risk_highlights": ["string - risk items"],
            "thesis_references": ["string - thesis IDs"],
            "insufficient_context": False,
        }, indent=2),
        "",
        "---",
        "",
        f"DATE: {context.date.isoformat()}",
        "",
        "PORTFOLIO SNAPSHOT:",
        f"Total Value: {context.portfolio_snapshot.totals.portfolio_value:.2f}",
        f"Positions: {len(context.portfolio_snapshot.positions)}",
    ]

    if context.alerts:
        lines.extend([
            "",
            "ALERTS:",
        ])
        for alert in context.alerts:
            lines.append(f"  [{alert.type}] {alert.message}")

    if context.observations:
        lines.extend([
            "",
            "OBSERVATIONS:",
        ])
        for obs in context.observations:
            lines.append(f"  [{obs.id}] {obs.text}")

    if context.active_theses:
        lines.extend([
            "",
            "ACTIVE THESES:",
        ])
        for thesis in context.active_theses:
            legs_summary = ", ".join(
                [f"{leg.direction} {leg.asset}" for leg in thesis.expression]
            )
            lines.append(f"  [{thesis.id}] {thesis.title}: {legs_summary}")

    return "\n".join(lines)

