"""Tests for tolerant JSON extraction from (untrusted) LLM text output.

The LLM output is UNTRUSTED: the boundary must extract the first JSON object or
array even when it is wrapped in prose or code fences, but it must NEVER silently
accept garbage or a non-structured scalar. A malformed response has to surface as
``LLMOutputError`` so a caller's per-source skip is an honest "could not parse",
not a wrong value masquerading as data (CLAUDE.md: laut statt still).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import LLMOutputError  # noqa: E402
from gen.llm.parsing import extract_json  # noqa: E402


# --- happy path: structured values, however they are wrapped -------------------

def test_bare_object_parses():
    assert extract_json('{"a": 1, "b": [2, 3]}') == {"a": 1, "b": [2, 3]}


def test_bare_array_parses():
    assert extract_json("[1, 2, 3]") == [1, 2, 3]


def test_object_wrapped_in_prose_is_extracted():
    text = 'Sure, here you go:\n{"relation": "supports", "confidence": 0.9}\nHope that helps!'
    assert extract_json(text) == {"relation": "supports", "confidence": 0.9}


def test_fenced_json_block_is_extracted():
    text = 'Result:\n```json\n{"ok": true}\n```\n'
    assert extract_json(text) == {"ok": True}


def test_fenced_block_without_language_tag_is_extracted():
    text = "```\n[\"x\", \"y\"]\n```"
    assert extract_json(text) == ["x", "y"]


def test_brace_inside_string_does_not_break_balancing():
    # a "}" inside a JSON string must not be counted as a closer
    text = 'noise {"note": "a } brace and a { brace", "n": 1} trailing'
    assert extract_json(text) == {"note": "a } brace and a { brace", "n": 1}


def test_first_top_level_value_wins_on_concatenation():
    # documented contract: the FIRST top-level object/array is returned
    assert extract_json('{"first": 1}{"second": 2}') == {"first": 1}


# --- fail loud: never accept garbage or a non-structured scalar ----------------

@pytest.mark.parametrize("scalar", ["42", "3.14", '"just a string"', "true", "false", "null"])
def test_scalar_root_is_rejected(scalar):
    # the docstring contract is "object or array"; a scalar from a malformed
    # response would otherwise be swallowed by a caller's best-effort fallback.
    with pytest.raises(LLMOutputError):
        extract_json(scalar, agent="scout")


def test_empty_string_raises_empty_output():
    with pytest.raises(LLMOutputError) as exc:
        extract_json("", agent="scholar")
    assert "empty output" in str(exc.value)


def test_whitespace_only_raises_empty_output():
    with pytest.raises(LLMOutputError) as exc:
        extract_json("   \n\t ", agent="skeptic")
    assert "empty output" in str(exc.value)


def test_none_raises_empty_output():
    with pytest.raises(LLMOutputError) as exc:
        extract_json(None, agent="forge")  # type: ignore[arg-type]
    assert "empty output" in str(exc.value)


def test_prose_without_any_json_raises():
    with pytest.raises(LLMOutputError):
        extract_json("I cannot answer that.", agent="conductor")


def test_unbalanced_braces_raise():
    # an opener with no matching closer is not a JSON value
    with pytest.raises(LLMOutputError):
        extract_json('{"a": 1', agent="architect")


def test_agent_name_is_carried_into_the_error():
    with pytest.raises(LLMOutputError) as exc:
        extract_json("nope", agent="synthesizer")
    assert "synthesizer" in str(exc.value)


# --- untrusted JSON must not smuggle non-finite numbers (NaN/Inf) --------------

@pytest.mark.parametrize(
    "payload",
    [
        '{"confidence": NaN}',
        '{"confidence": Infinity}',
        '{"x": -Infinity}',
        "[NaN]",
        "[1, 2, Infinity]",
    ],
)
def test_non_finite_literal_is_rejected(payload):
    # json.loads accepts NaN/Infinity by default; a non-finite number from an
    # untrusted model would poison numeric consumers (e.g. skeptic confidence).
    with pytest.raises(LLMOutputError):
        extract_json(payload, agent="skeptic")


def test_finite_numbers_still_parse():
    assert extract_json('{"confidence": 0.83, "n": -5}') == {"confidence": 0.83, "n": -5}
