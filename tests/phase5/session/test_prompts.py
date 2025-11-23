from src.slice.session.prompts import build_prompt, SYSTEM_PROMPT
from src.slice.session.models import SessionOptions, SessionMode


def test_prompt_ordering():
    mem = {"items": [{"observation_id": 1, "text": "foo", "thesis_ref": "t", "similarity": 0.9}]}
    risk = {
        "book_gross": 10.0,
        "book_net": 5.0,
        "exposures": [],
        "backtests": [],
    }

    opts = SessionOptions()
    messages = build_prompt(mem, risk, "hello", opts)

    assert messages[0]["role"] == "system"
    user_content = messages[1]["content"]

    # Memory must appear before Risk, which appears before User text
    mem_idx = user_content.index("[MEMORY CONTEXT]")
    risk_idx = user_content.index("[RISK SNAPSHOT]")
    user_idx = user_content.index("[USER MESSAGE]")

    assert mem_idx < risk_idx < user_idx


def test_prompt_modes():
    opts = SessionOptions(mode=SessionMode.CONCISE)
    messages = build_prompt(None, None, "x", opts)
    assert "[MODE: CONCISE" in messages[1]["content"]