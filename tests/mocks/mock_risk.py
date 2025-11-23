def fake_risk_snapshot():
    return {
        "book_gross": 100.0,
        "book_net": 20.0,
        "duration": 1.2,
        "dv01": 4500,
        "exposures": [
            {"asset": "SPY", "direction": "LONG", "size": 50},
            {"asset": "TLT", "direction": "SHORT", "size": 30},
        ],
        "backtests": [
            {"strategy": "trend", "win_rate": 0.57, "max_drawdown": -0.08},
            {"strategy": "carry", "win_rate": 0.61, "max_drawdown": -0.05},
        ],
    }


def mock_get_snapshot(*args, **kwargs):
    return fake_risk_snapshot()