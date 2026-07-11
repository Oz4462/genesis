"""CLI mode matrix (REWORK 2026-07-11).

Pins: every advertised --mode is registered; offline demos that must not need
live LLMs exit 0 (or honest usage exit without crash).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

# All modes advertised in gen.cli argparse choices (keep in sync with cli.py).
CLI_MODES = (
    "report",
    "solution",
    "spec",
    "capstone",
    "eval",
    "protocol",
    "assess",
    "print",
    "bundle",
    "ideas",
    "dream",
    "humanoid",
    "aethon",
    "humanoid-research",
    "humanoid-chat",
    "council",
    "feynman",
    "campaign",
    "section",
    "topology",
    "structural",
    "training",
    "chip",
    "realize",
    "breakthrough",
    "horizon-full",
    "goldset",
    "divergence",
    "frontier",
    "fach",
    "architekt",
    "ingenieur",
    "physiker",
    "techniker",
    "elektriker",
    "fertigungs",
    "regulatorik",
    "software",
    "designer",
    "wirtschaft",
    "research",
    "discover-ode",
    "invent",
    "solve",
)


def _run(args: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PY, "-m", "gen", *args],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_all_modes_listed_in_help():
    r = _run(["--help"], timeout=30)
    assert r.returncode == 0
    for mode in CLI_MODES:
        assert mode in r.stdout, f"mode {mode!r} missing from --help"


@pytest.mark.parametrize(
    "args,ok_codes",
    [
        (["--mode", "assess", "--demo"], {0}),
        # print exits 3 when optional CAD kernel/geometry absent — honest, not a crash
        (["--mode", "print", "--demo"], {0, 3}),
        # α/β/γ offline demos (scripted LLMs — fully deterministic)
        (["--mode", "report", "--demo"], {0}),
        (["--mode", "solution", "--demo"], {0}),
        (["--mode", "spec", "--demo"], {0}),
        (["--mode", "capstone", "--demo"], {0}),
        (["--mode", "protocol", "--demo"], {0}),
        (["--mode", "eval", "--demo"], {0}),
        (["--mode", "bundle", "--demo"], {0}),
        (["--mode", "section", "--demo"], {0}),
        (["--mode", "training", "--demo"], {0}),
        (["--mode", "chip", "--demo"], {0}),
        (["--mode", "invent", "--demo"], {0}),
        (["--mode", "goldset", "--demo"], {0}),
        (["--mode", "divergence", "--demo"], {0}),
        (["--mode", "frontier", "--demo"], {0}),
        (["--mode", "fach", "steel shelf bracket"], {0}),
        (["--mode", "architekt", "steel shelf bracket"], {0}),
        (["--mode", "designer", "steel shelf bracket"], {0}),
        (["--mode", "wirtschaft", "steel shelf bracket"], {0}),
        (["--mode", "research", "(x+1)**2|x**2+2*x+1"], {0}),
    ],
)
def test_offline_demo_modes_exit_clean(args: list[str], ok_codes: set[int]):
    r = _run(args, timeout=90)
    assert r.returncode in ok_codes, (
        r.returncode,
        r.stdout[-800:],
        r.stderr[-800:],
    )
    # Never a Python traceback on stdout/stderr for these offline demos
    combined = (r.stdout or "") + (r.stderr or "")
    assert "Traceback (most recent call last)" not in combined
