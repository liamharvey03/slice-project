"""
E3: LLM output DTOs for structured tool responses.

All fields are required (no Optional) to ensure missing keys blow up fast.
Empty lists and empty strings are valid values.
"""
from pydantic import BaseModel


class ThesisReview(BaseModel):
    """
    LLM review of a single thesis against its evaluation.

    Fields:
        critique: str - Critical analysis of the thesis structure/logic
        questions: list[str] - Clarifying questions about assumptions
        risk_flags: list[str] - Identified risk areas
        insufficient_context: bool - True if model couldn't answer from provided data
    """

    critique: str
    questions: list[str]
    risk_flags: list[str]
    insufficient_context: bool


class CrossThesisReport(BaseModel):
    """
    LLM analysis of relationships between multiple theses.

    Fields:
        overlaps: list[str] - Common themes/exposures across theses
        contradictions: list[str] - Directly opposing assumptions/exposures
        gaps: list[str] - Missing angles or blind spots
        insufficient_context: bool - True if model couldn't analyze from provided data
    """

    overlaps: list[str]
    contradictions: list[str]
    gaps: list[str]
    insufficient_context: bool


class IntuitionAnswer(BaseModel):
    """
    LLM answer to an intuition query based on observations.

    Fields:
        answer: str - Synthesized answer text
        references: list[str] - Observation IDs as strings that were cited
        insufficient_context: bool - True if answer not contained in observations
    """

    answer: str
    references: list[str]  # Observation IDs as strings
    insufficient_context: bool


class DailySummary(BaseModel):
    """
    LLM daily summary for portfolio manager.

    Fields:
        key_narratives: list[str] - 2-5 bullet-level storylines about what mattered
        risk_highlights: list[str] - Concrete risk items to watch
        thesis_references: list[str] - Thesis IDs as strings that were impacted
        insufficient_context: bool - True if model couldn't summarize from provided data
    """

    key_narratives: list[str]
    risk_highlights: list[str]
    thesis_references: list[str]  # Thesis IDs as strings
    insufficient_context: bool

