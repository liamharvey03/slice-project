from datetime import datetime

from slice.models.thesis import Thesis
from slice.models.observation import Observation
from slice.models.trade import Trade
from slice.models.scenario import Scenario


def test_thesis_model_valid():
    data = {
        "id": "thesis_1",
        "title": "Gold on falling real yields",
        "hypothesis": "Real yields fall -> gold rises",
        "drivers": ["real yields fall"],
        "disconfirmers": ["real yields rise"],
        "expression": [
            {"asset": "GLD", "direction": "LONG", "size_pct": 20},
        ],
        "start_date": "2025-01-01",
        "review_date": None,
        "status": "ACTIVE",
        "tags": ["gold"],
        "monitor_indices": ["US10Y_REAL"],
        "notes": None,
    }
    t = Thesis(**data)
    assert t.id == "thesis_1"


def test_observation_model_valid():
    obs = Observation(
        id="obs1",
        timestamp=datetime.utcnow(),
        text="Strong CPI print.",
        thesis_ref=["thesis_1"],
        sentiment="BEARISH",
        categories=["inflation"],
        actionable="NO",
    )
    assert obs.text == "Strong CPI print."


def test_trade_model_valid():
    trade = Trade(
        trade_id="t1",
        timestamp=datetime.utcnow(),
        asset="GLD",
        action="BUY",
        quantity=10,
        price=190.5,
        type="SIMULATED",
        thesis_ref="thesis_1",
    )
    assert trade.asset == "GLD"


def test_scenario_model_valid():
    sc = Scenario(
        scenario_id="s1",
        name="Soft landing",
        assumptions={"US_CPI_YOY": "2.5%"},
        expected_impact={"GLD": 0.10},
        description="Soft landing with easing real yields",
    )
    assert sc.name == "Soft landing"