from __future__ import annotations
from pydantic import BaseModel
from typing import Dict


class Scenario(BaseModel):
    scenario_id: str
    name: str
    assumptions: Dict[str, str]
    expected_impact: Dict[str, float]
    description: str