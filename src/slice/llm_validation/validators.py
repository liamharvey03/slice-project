from __future__ import annotations

from typing import Any, Dict

from pydantic import ValidationError

from slice.models.thesis import Thesis
from slice.models.observation import Observation
from slice.models.trade import Trade
from slice.models.scenario import Scenario

from .errors import ValidationIssue, ValidationResult
from .normalization import (
    normalize_thesis_payload,
    normalize_observation_payload,
    normalize_trade_payload,
    normalize_scenario_payload,
)


def _from_pydantic_error(err: Dict[str, Any]) -> ValidationIssue:
    loc = err.get("loc", [])
    field = loc[-1] if loc else "<root>"
    msg = err.get("msg", "Validation error")
    etype = err.get("type", "value_error")
    return ValidationIssue(field=str(field), code=str(etype), message=msg, context=err)


def validate_thesis(raw: Dict[str, Any]) -> ValidationResult:
    norm = normalize_thesis_payload(raw)
    try:
        model = Thesis(**norm)
        return ValidationResult(ok=True, model=model, errors=[])
    except ValidationError as e:
        issues = [_from_pydantic_error(err) for err in e.errors()]
        return ValidationResult(ok=False, model=None, errors=issues)


def validate_observation(raw: Dict[str, Any]) -> ValidationResult:
    norm = normalize_observation_payload(raw)
    try:
        model = Observation(**norm)
        return ValidationResult(ok=True, model=model, errors=[])
    except ValidationError as e:
        issues = [_from_pydantic_error(err) for err in e.errors()]
        return ValidationResult(ok=False, model=None, errors=issues)


def validate_trade(raw: Dict[str, Any]) -> ValidationResult:
    norm = normalize_trade_payload(raw)
    try:
        model = Trade(**norm)
        return ValidationResult(ok=True, model=model, errors=[])
    except ValidationError as e:
        issues = [_from_pydantic_error(err) for err in e.errors()]
        return ValidationResult(ok=False, model=None, errors=issues)


def validate_scenario(raw: Dict[str, Any]) -> ValidationResult:
    norm = normalize_scenario_payload(raw)
    try:
        model = Scenario(**norm)
        return ValidationResult(ok=True, model=model, errors=[])
    except ValidationError as e:
        issues = [_from_pydantic_error(err) for err in e.errors()]
        return ValidationResult(ok=False, model=None, errors=issues)