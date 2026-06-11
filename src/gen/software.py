"""Software-domain validator — correctness proven by EXECUTION (the ε software arc).

Every other GENESIS layer re-checks a declared value (the gate recomputes a
formula, an AABB, a netlist). Software has the strongest possible deterministic
validator: run it. A code deliverable is `source` plus a `check` that exercises
it; if the process exits non-zero (a failed assertion, a syntax error), the
deliverable is broken — no model judgement, the machine decides.

The runner executes the combined script in an ISOLATED subprocess of the same
interpreter (`python -I`: ignore environment and user site-packages) with a hard
timeout. Deterministic and offline (no network, no LLM).

Honest boundary: only Python runs here (it has a guaranteed local runtime). Other
languages need their toolchain and are reported as unsupported rather than faked.
Security note: executing spec-supplied code is a sandbox concern; the isolated
subprocess + timeout is a pragmatic boundary, not a hardened sandbox — a production
deployment should run untrusted code in a real sandbox (see rules/95).
"""

from __future__ import annotations

import subprocess
import sys

#: Languages with a deterministic local runtime in this environment.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("python",)

#: Hard wall-clock limit for a single code check.
DEFAULT_TIMEOUT_S = 15


def run_python_artifact(
    source: str, check: str, *, timeout: float = DEFAULT_TIMEOUT_S
) -> tuple[bool, str]:
    """Execute ``source`` + ``check`` in an isolated Python subprocess.

    Returns ``(passed, output)``: passed is True iff the process exits 0 (all
    assertions held), output is the captured stdout+stderr (tail-useful on
    failure). Raises ``subprocess.TimeoutExpired`` if the check exceeds `timeout`
    — the caller (GATE CODE) turns that into an explicit failure, never a silent
    pass.
    """
    script = f"{source}\n\n{check}\n"
    proc = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr)
