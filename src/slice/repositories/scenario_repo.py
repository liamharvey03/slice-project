import json
from typing import Optional
from sqlalchemy import text

from slice.db import get_engine
from slice.models.scenario import Scenario


class ScenarioRepository:

    @staticmethod
    def insert(scenario: Scenario) -> None:
        engine = get_engine()

        params = scenario.dict()
        # Serialize JSON fields
        params["assumptions"] = json.dumps(params["assumptions"])
        params["expected_impact"] = json.dumps(params["expected_impact"])

        sql = text("""
            INSERT INTO scenario (
                scenario_id, name, assumptions,
                expected_impact, description
            )
            VALUES (
                :scenario_id, :name, :assumptions,
                :expected_impact, :description
            )
            ON CONFLICT (scenario_id) DO UPDATE SET
                name = EXCLUDED.name,
                assumptions = EXCLUDED.assumptions,
                expected_impact = EXCLUDED.expected_impact,
                description = EXCLUDED.description;
        """)

        with engine.begin() as conn:
            conn.execute(sql, params)

    @staticmethod
    def get(scenario_id: str) -> Optional[Scenario]:
        engine = get_engine()
        sql = text("SELECT * FROM scenario WHERE scenario_id = :sid")

        with engine.connect() as conn:
            row = conn.execute(sql, {"sid": scenario_id}).mappings().fetchone()

        if row is None:
            return None

        # Deserialize JSON fields
        row = dict(row)
        row["assumptions"] = json.loads(row["assumptions"])
        row["expected_impact"] = json.loads(row["expected_impact"])

        return Scenario(**row)