"""Tolerant JSON extraction from LLM text output.

LLMs wrap JSON in prose or code fences. This pulls out the first top-level JSON
object or array. On failure it raises ``LLMOutputError`` — callers decide whether
to skip the item (agents do, per-source) but never silently accept garbage.
"""

from __future__ import annotations

import json

from ..core.errors import LLMOutputError


def extract_json(text: str, *, agent: str = "llm") -> object:
    """Return the first JSON object/array found in `text`.

    Handles ```json fences and leading/trailing prose. Raises LLMOutputError if
    no valid JSON value can be parsed.
    """
    if text is None:
        raise LLMOutputError(agent, "empty output")
    s = text.strip()
    if not s:
        # Whitespace-only is the empty case too — give the honest "empty output"
        # message rather than the misleading "no JSON value in: ''".
        raise LLMOutputError(agent, "empty output")

    # Strip a single fenced block if present.
    if "```" in s:
        start = s.find("```")
        # skip the fence line (``` or ```json)
        nl = s.find("\n", start)
        end = s.find("```", nl + 1) if nl != -1 else -1
        if nl != -1 and end != -1:
            s = s[nl + 1 : end].strip()

    # Fast path: the whole thing is JSON. On any trailing-junk / not-yet-JSON
    # decode error, fall back to scanning for the first balanced { } or [ ] span.
    try:
        value = json.loads(s)
    except json.JSONDecodeError:
        span = _first_balanced_span(s)
        if span is None:
            raise LLMOutputError(agent, f"no JSON value in: {s[:120]!r}") from None
        try:
            value = json.loads(span)
        except json.JSONDecodeError as exc:
            raise LLMOutputError(agent, f"{exc}") from exc

    # Contract (see docstring): agents consume a JSON object or array. A scalar
    # root (42, "x", null, true) is a malformed structured response — fail loud
    # here, otherwise it surfaces as a TypeError swallowed by a caller's
    # best-effort fallback, masking bad output as an honest empty result.
    if not isinstance(value, (dict, list)):
        raise LLMOutputError(
            agent, f"expected a JSON object or array, got {type(value).__name__}"
        )
    return value


def _first_balanced_span(s: str) -> str | None:
    opens = {"{": "}", "[": "]"}
    start = -1
    opener = ""
    for i, ch in enumerate(s):
        if ch in opens:
            start = i
            opener = ch
            break
    if start == -1:
        return None
    closer = opens[opener]
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        ch = s[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return s[start : j + 1]
    return None
