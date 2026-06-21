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
import os
import shutil
import subprocess
import sys
from typing import Awaitable, Callable

from ..core.errors import LLMTransportError

# An injectable async runner: argv -> (returncode, stdout, stderr). The real runner and the
# test fakes both satisfy this — the mockable seam, exactly like ``ollama.HttpPostJson``.
CliRunner = Callable[[list[str]], Awaitable[tuple[int, str, str]]]

#: Sentinel return code used when the child is killed for exceeding the timeout (so the adapter
#: raises an honest LLMTransportError instead of a hang looking like an empty answer).
TIMEOUT_RETURNCODE = 124


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


# --- Windows command-line quoting for the .cmd/.bat route ----------------------------------------
# A native .exe and every POSIX binary are launched from an argv LIST: subprocess builds the command
# line itself (CreateProcess/execvp), no shell — safe. A Windows .cmd/.bat shim (npm's claude.CMD)
# cannot be launched by CreateProcess directly; it must go through the command processor (cmd /c).
#
# The decisive subtlety, confirmed against the real npm claude.CMD (it forwards `"<exe>" %*`) and by
# scripts/verify_cli_launch.py: the argument list is parsed by cmd.exe TWICE — once to invoke the
# .cmd, then AGAIN when the shim re-expands %* to call the underlying .exe. Caret-escaping (^&, ^^)
# only survives the FIRST parse; the %* re-expansion leaves the metacharacters naked for the SECOND
# parse, which then splits on a stray & or eats a ^. DOUBLE QUOTES, by contrast, are preserved by %*
# and keep protecting across both parses. So we FORCE-QUOTE every argument (always wrap in "...", with
# the backslash/quote escaping the child .exe's MSVCRT parser needs) and do NOT caret-escape. A prompt
# holding ^ & | < > ( ) and spaces then survives the shim's %* double-parse intact — the silent-
# corruption class that plain list2cmdline (quotes only on spaces) and a naive caret pass both leave
# open. Residual (documented): an embedded " immediately followed by a cmd metacharacter can still
# expose it; GENESIS prompts don't contain that adjacency (JSON quotes are followed by :{letters).


def _msvcrt_quote(arg: str, *, force: bool = False) -> str:
    """Quote one argument for the MSVCRT / CommandLineToArgvW parser the child re-parses with. With
    ``force`` the argument is ALWAYS wrapped in double quotes — required on the cmd.exe route so the
    quotes survive a shim's ``%*`` re-parse; without it, a space/quote-free arg is left bare."""
    if not force and arg and not any(c in arg for c in ' \t\n\v"'):
        return arg
    out = ['"']
    backslashes = 0
    for ch in arg:
        if ch == '\\':
            backslashes += 1
            continue
        if ch == '"':
            out.append('\\' * (2 * backslashes + 1))   # escape the backslash run + this literal quote
            out.append('"')
        else:
            out.append('\\' * backslashes)
            out.append(ch)
        backslashes = 0
    out.append('\\' * (2 * backslashes))               # backslashes immediately before the closing quote
    out.append('"')
    return ''.join(out)


def _launch_spec(argv: list[str]) -> list[str] | str:
    """What to hand ``subprocess.run``: a STRING command line on the Windows .cmd/.bat route (every
    argument force-quoted so it survives cmd.exe — including a shim's ``%*`` double-parse, see above),
    else the argv LIST unchanged (no shell, no injection surface). The .exe / POSIX path stays a LIST,
    so the single MSVCRT layer subprocess applies is already correct."""
    if sys.platform == "win32" and argv and argv[0].lower().endswith((".cmd", ".bat")):
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        inner = ' '.join(_msvcrt_quote(a, force=True) for a in argv)
        # /s + the outer quotes: cmd strips exactly the first and last char, then runs <inner> verbatim.
        return f'"{comspec}" /d /s /c "{inner}"'
    return argv


async def default_cli_run(argv: list[str], *, timeout: float = 300.0) -> tuple[int, str, str]:
    """Launch the CLI and capture stdout/stderr — hardened for a native Windows terminal.

    Robustness fixes over the bare ``asyncio.create_subprocess_exec`` path (which is flaky launching
    subscription CLIs on Windows):
      * runs a SYNCHRONOUS ``subprocess.run`` in a worker thread — sidesteps the ProactorEventLoop
        pipe issues that hang on Windows;
      * ``stdin=DEVNULL`` so a CLI that probes for an interactive terminal gets EOF instead of
        blocking forever waiting on input;
      * a ``.cmd``/``.bat`` shim is launched as a force-quoted ``cmd /d /s /c "<line>"`` STRING
        (see ``_launch_spec``) — else Windows cannot launch it at all, and force-quoting every argument
        stops cmd.exe silently mangling a prompt that holds ``^``/``"``/``&`` even across the shim's
        ``%*`` double-parse (proven end-to-end by ``scripts/verify_cli_launch.py``);
      * a hard timeout that kills the child and returns a sentinel code, so a stuck CLI surfaces as a
        loud ``LLMTransportError`` (the adapter raises on non-zero), never a silent empty answer;
      * stdout/stderr decoded UTF-8 with ``errors="replace"`` — a stray non-UTF-8 byte from a Windows
        console never crashes the decode (which would look like a transport failure).
    It deliberately does NOT detach the child's console (no ``CREATE_NO_WINDOW``): the subscription
    CLIs authenticate against the inherited terminal, exactly as the working direct-shell call does —
    giving the child its own hidden console would re-break the OAuth path. The .exe path stays
    execFile-style (argv list, no shell string). The runner stays injectable, so unit tests never
    launch a real binary."""
    launch = _launch_spec(argv)

    def _run() -> tuple[int, str, str]:
        try:
            proc = subprocess.run(
                launch,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            err = (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return (TIMEOUT_RETURNCODE, out, f"{err}\n[CLI timed out after {timeout:g}s]")
        return (
            proc.returncode or 0,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"),
        )

    return await asyncio.to_thread(_run)


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
