"""Shared machinery for subscription-OAuth CLI LLM adapters (Claude Code, Grok).

Both adapters launch a vendor CLI that is ALREADY authenticated via the user's
SUBSCRIPTION (OAuth) — no API key, no per-token billing, and no secret in this repo (the
OAuth token lives in the CLI's own config dir, GENESIS never touches it). This is the same
keyless path the dual-agent build harness uses.

Safety: the child is launched with ``asyncio.create_subprocess_exec(*argv)`` — the execFile
pattern (an argv LIST, no shell, no string interpolation), so there is no command-injection
surface. ``create_subprocess_shell`` is deliberately NOT used.

Anti-hallucination posture (mirrors ``llm/ollama.py``):
  * the subprocess runner is INJECTABLE, so unit tests never launch the real binary;
  * a failed call raises ``LLMTransportError`` — a dead / re-auth-needed CLI must never look
    like a model that answered nothing, which downstream would honestly read as abstention
    and thereby mask an outage.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Awaitable, Callable

from ..core.errors import LLMTransportError

# An injectable async runner: argv -> (returncode, stdout, stderr). The real runner and the
# test fakes both satisfy this — the mockable seam, exactly like ``ollama.HttpPostJson``.
CliRunner = Callable[[list[str]], Awaitable[tuple[int, str, str]]]


def resolve_binary(name: str) -> str:
    """Absolute path to a CLI, or fail loud at CONSTRUCTION (not deep inside a run).

    A missing CLI is a configuration error the operator must see immediately; resolving it
    up front mirrors ``OllamaLLM``'s empty-model guard.
    """
    path = shutil.which(name)
    if not path:
        raise ValueError(
            f"CLI {name!r} not found on PATH; the {name} subscription adapter needs it installed."
        )
    return path


async def default_cli_run(argv: list[str], *, timeout: float = 300.0) -> tuple[int, str, str]:
    """Launch the CLI (execFile-style, argv list, no shell) and capture stdout/stderr.

    The generous default timeout covers an agentic CLI's first-token latency. A timeout kills
    the child and propagates — the adapter wraps it into ``LLMTransportError``.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return (
        proc.returncode or 0,
        out_b.decode("utf-8", "replace"),
        err_b.decode("utf-8", "replace"),
    )


# Keys the CLIs use for the final assistant text under ``--output-format json``.
_TEXT_KEYS = ("result", "response", "text", "content", "output")


def extract_cli_text(stdout: str, *, model: str) -> str:
    """Pull the assistant text out of a CLI's ``--output-format json`` stdout.

    Tolerant by design: parse the whole payload, else the last non-empty line (a CLI may
    stream event objects then a trailing result object), then read the first known text key
    or a ``{"message": {"content": ...}}`` chat envelope. Falls back to the trimmed raw
    stdout (the CLI ran in plain text mode). Empty output is an outage, never a silent "" —
    it raises ``LLMTransportError``.
    """
    s = stdout.strip()
    if not s:
        raise LLMTransportError(model, "CLI returned empty stdout")
    obj: object | None = None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        last = next((ln for ln in reversed(s.splitlines()) if ln.strip()), "")
        try:
            obj = json.loads(last)
        except json.JSONDecodeError:
            obj = None
    if isinstance(obj, dict):
        for key in _TEXT_KEYS:
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value
        message = obj.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return s
