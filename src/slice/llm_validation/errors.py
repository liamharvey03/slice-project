from dataclasses import dataclass
from typing import List, Optional, Any


@dataclass
class ValidationIssue:
    field: str
    code: str
    message: str
    context: Optional[Any] = None


@dataclass
class ValidationResult:
    ok: bool
    model: Optional[Any]
    errors: List[ValidationIssue]