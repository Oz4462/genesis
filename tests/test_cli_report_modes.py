"""CLI product-wire modes: aero-report, humanoid-report, surface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "bin" / "python"
if not PY.is_file():
    PY = Path(sys.executable)


def _run_mode(mode: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PY), "-m", "gen", "--mode", mode],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": "src"},
    )


def test_aero_report_mode_exits_zero():
    proc = _run_mode("aero-report")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "REAL DRONES" in proc.stdout or "drones catalogued" in proc.stdout
    assert "HONESTY" in proc.stdout or "honest" in proc.stdout.lower()


def test_humanoid_report_mode_exits_zero():
    proc = _run_mode("humanoid-report")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "HUMANOID" in proc.stdout or "humanoid" in proc.stdout.lower()
    assert "HONESTY" in proc.stdout or "honest" in proc.stdout.lower()


def test_surface_mode_lists_product_modules():
    proc = _run_mode("surface")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "gen.export.drawing" in proc.stdout
    assert "anchored:" in proc.stdout
    # reachability line when find_islands is available
    assert "WIRED=" in proc.stdout or "reachability" in proc.stdout


def test_council_feynman_campaign_offline_green():
    """STATUS re-smoke: discovery sub-engines offline (no live LLM)."""
    for mode in ("council", "feynman", "campaign"):
        proc = _run_mode(mode, timeout=180.0)
        assert proc.returncode == 0, f"{mode}: {proc.stderr}\n{proc.stdout}"
