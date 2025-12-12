"""
E3: Tests for extract_json helper.

Verifies:
- Valid JSON + trailing garbage → returns just JSON
- No {/} → raises LLMOutputError
- Multiple JSON objects → extracts first to last (expects exactly one)
"""
import pytest

from voyager.llm.tools import extract_json, LLMOutputError


def test_extract_json_valid_json_only():
    """Pure JSON returns unchanged."""
    json_str = '{"answer": "test", "references": []}'
    result = extract_json(json_str)
    assert result == json_str


def test_extract_json_with_trailing_garbage():
    """JSON with trailing text returns just the JSON."""
    raw = '{"answer": "test", "references": []} extra text here'
    result = extract_json(raw)
    assert result == '{"answer": "test", "references": []}'


def test_extract_json_with_leading_garbage():
    """JSON with leading text returns just the JSON."""
    raw = 'Here is the response: {"answer": "test", "references": []}'
    result = extract_json(raw)
    assert result == '{"answer": "test", "references": []}'


def test_extract_json_with_both_leading_and_trailing():
    """JSON with text on both sides returns just the JSON."""
    raw = 'The answer is: {"answer": "test", "references": []} That is all.'
    result = extract_json(raw)
    assert result == '{"answer": "test", "references": []}'


def test_extract_json_no_braces_raises():
    """No braces raises LLMOutputError."""
    with pytest.raises(LLMOutputError, match="No JSON object found"):
        extract_json("This is not JSON at all")


def test_extract_json_only_opening_brace_raises():
    """Only opening brace raises LLMOutputError."""
    with pytest.raises(LLMOutputError, match="No JSON object found"):
        extract_json('{"incomplete": ')


def test_extract_json_only_closing_brace_raises():
    """Only closing brace raises LLMOutputError."""
    with pytest.raises(LLMOutputError, match="No JSON object found"):
        extract_json('"incomplete": "value"}')


def test_extract_json_wrong_order_raises():
    """If } comes before {, raises LLMOutputError."""
    with pytest.raises(LLMOutputError, match="Malformed JSON"):
        extract_json("} wrong order {")


def test_extract_json_multiple_objects():
    """
    Multiple JSON objects: extracts from first { to last }.

    Note: This expects exactly one JSON object in practice, but we handle
    multiple by taking the outer span. The caller should validate the result.
    """
    raw = 'First: {"a": 1} Second: {"b": 2}'
    result = extract_json(raw)
    # Should extract from first { to last }
    assert result == '{"a": 1} Second: {"b": 2}'


def test_extract_json_nested_objects():
    """Nested JSON objects work correctly."""
    raw = 'Response: {"outer": {"inner": "value"}}'
    result = extract_json(raw)
    assert result == '{"outer": {"inner": "value"}}'


def test_extract_json_empty_object():
    """Empty JSON object works."""
    raw = '{}'
    result = extract_json(raw)
    assert result == '{}'

