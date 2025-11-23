from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _normalize_str_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        # split on commas if present, else treat as single token
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    return None


def _normalize_upper(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v.upper() if v else None
    return None


def _normalize_date_field(value: Any) -> Any:
    """
    Leave ISO-ish strings alone (Pydantic will parse).
    Treat empty strings as None.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _normalize_numeric(value: Any) -> Any:
    """
    Light coercion: strings that look like numbers → float.
    Otherwise return as-is and let Pydantic decide.
    """
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return value
    return value


def normalize_thesis_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(raw)  # shallow copy

    # ID: allowed to auto-generate if missing
    if not data.get("id"):
        data["id"] = f"thesis_{uuid4().hex}"

    data["title"] = (data.get("title") or "").strip()
    data["hypothesis"] = (data.get("hypothesis") or "").strip()

    if "drivers" in data:
        data["drivers"] = _normalize_str_list(data.get("drivers"))
    if "disconfirmers" in data:
        data["disconfirmers"] = _normalize_str_list(data.get("disconfirmers"))
    if "tags" in data:
        data["tags"] = _normalize_str_list(data.get("tags"))
    if "monitor_indices" in data:
        data["monitor_indices"] = _normalize_str_list(data.get("monitor_indices"))

    # expression: ensure list
    expr = data.get("expression")
    if expr is not None and not isinstance(expr, list):
        data["expression"] = [expr]

    # dates
    if "start_date" in data:
        data["start_date"] = _normalize_date_field(data.get("start_date"))
    if "review_date" in data:
        data["review_date"] = _normalize_date_field(data.get("review_date"))

    # status: only normalize casing, do NOT default semantics
    if "status" in data:
        normalized = _normalize_upper(data.get("status"))
        if normalized is not None:
            data["status"] = normalized

    return data


def normalize_observation_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(raw)

    if not data.get("id"):
        # obs_<timestamp>_<uuid>
        ts_part = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        data["id"] = f"obs_{ts_part}_{uuid4().hex[:8]}"

    # timestamp left as-is; Pydantic will parse. Empty string → None.
    if "timestamp" in data:
        data["timestamp"] = _normalize_date_field(data.get("timestamp"))

    data["text"] = (data.get("text") or "").strip()

    # thesis_ref can be string or list
    tr = data.get("thesis_ref")
    if tr is not None and not isinstance(tr, list):
        data["thesis_ref"] = [str(tr)]
    elif isinstance(tr, list):
        data["thesis_ref"] = [str(x).strip() for x in tr if str(x).strip()]

    # categories
    if "categories" in data:
        data["categories"] = _normalize_str_list(data.get("categories")) or []

    # sentiment/actionable: only normalize casing
    if "sentiment" in data:
        sent = _normalize_upper(data.get("sentiment"))
        if sent is not None:
            data["sentiment"] = sent
    if "actionable" in data:
        act = _normalize_upper(data.get("actionable"))
        if act is not None:
            data["actionable"] = act

    return data


def normalize_trade_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(raw)

    if not data.get("trade_id"):
        data["trade_id"] = f"trade_{uuid4().hex}"

    if "timestamp" in data:
        data["timestamp"] = _normalize_date_field(data.get("timestamp"))

    data["asset"] = (data.get("asset") or "").strip()

    if "action" in data:
        act = _normalize_upper(data.get("action"))
        if act is not None:
            data["action"] = act

    if "type" in data:
        t = _normalize_upper(data.get("type"))
        if t is not None:
            data["type"] = t

    if "quantity" in data:
        data["quantity"] = _normalize_numeric(data.get("quantity"))
    if "price" in data:
        data["price"] = _normalize_numeric(data.get("price"))

    # thesis_ref: keep as simple string if present
    if "thesis_ref" in data and data["thesis_ref"] is not None:
        data["thesis_ref"] = str(data["thesis_ref"]).strip() or None

    return data


def normalize_scenario_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(raw)

    if not data.get("scenario_id"):
        data["scenario_id"] = f"scenario_{uuid4().hex}"

    data["name"] = (data.get("name") or "").strip()
    data["description"] = (data.get("description") or "").strip()

    # Leave assumptions/expected_impact mostly as-is; they should be dict-like.
    # Do not attempt semantic reconstruction.
    return data