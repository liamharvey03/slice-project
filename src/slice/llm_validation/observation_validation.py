from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from slice.models.observation import Observation


@dataclass
class ValidationIssue:
    field: str
    code: str
    message: str
    context: Dict[str, Any]


@dataclass
class ValidationResult:
    ok: bool
    errors: List[ValidationIssue]
    model: Optional[Observation]


def _normalize_categories(raw_categories: Any) -> List[str]:
    """
    Accepts:
      - comma/semicolon separated string: "fed, inflation"
      - list/tuple of strings
      - None / empty
    Returns list[str].
    """
    if raw_categories is None:
        return []

    if isinstance(raw_categories, (list, tuple)):
        return [str(c).strip() for c in raw_categories if str(c).strip()]

    if isinstance(raw_categories, str):
        parts = [p.strip() for p in raw_categories.replace(";", ",").split(",")]
        return [p for p in parts if p]

    return []


def _normalize_thesis_ref(raw_ref: Any) -> List[str]:
    """
    thesis_ref can be:
      - a single string: "fed_rates"
      - a list/tuple of strings
      - None
    Returns list[str].
    """
    if raw_ref is None:
        return []

    if isinstance(raw_ref, (list, tuple)):
        return [str(r).strip() for r in raw_ref if str(r).strip()]

    if isinstance(raw_ref, str):
        v = raw_ref.strip()
        return [v] if v else []

    return []


def validate_observation(raw: Dict[str, Any]) -> ValidationResult:
    """
    Pure-Pydantic observation validation with light normalization.

    It does NOT call any LLM – it just:
      - normalizes categories and thesis_ref
      - instantiates slice.models.Observation
      - returns ValidationResult(ok, errors, model)
    """
    payload = dict(raw)

    # Normalize categories / thesis_ref into shapes the model expects
    payload["categories"] = _normalize_categories(payload.get("categories"))
    payload["thesis_ref"] = _normalize_thesis_ref(payload.get("thesis_ref"))

    try:
        model = Observation(**payload)
        return ValidationResult(ok=True, errors=[], model=model)
    except ValidationError as e:
        issues: List[ValidationIssue] = []
        for err in e.errors():
            loc = err.get("loc", ())
            field = ".".join(str(x) for x in loc) if loc else ""
            issues.append(
                ValidationIssue(
                    field=field,
                    code=err.get("type", ""),
                    message=err.get("msg", ""),
                    context=err,
                )
            )
        return ValidationResult(ok=False, errors=issues, model=None)