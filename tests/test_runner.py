"""Tests for end-to-end wiring (Aufgabe 5): reproducibility, checkpoint, CLI.

Uses the deterministic offline demo world (scripted models, canned sources) so
the full pipeline is exercised without network or API keys.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.cli import build_demo, main  # noqa: E402
from gen.config import Config, config_hash, default_config  # noqa: E402
from gen.core.state import ClaimStatus  # noqa: E402
from gen.runner import load_checkpoint, make_run_id, run  # noqa: E402


def run_sync(coro):
    return asyncio.run(coro)


# --- config / reproducibility anchors ----------------------------------------

def test_config_hash_stable_and_sensitive():
    a = config_hash(default_config())
    b = config_hash(Config.from_dict(default_config().to_dict()))
    c = config_hash(Config.from_dict({"phase_alpha": {"confidence_threshold": 0.95}}))
    assert a == b
    assert a != c


def test_make_run_id_deterministic():
    assert make_run_id("q", "h") == make_run_id("q", "h")
    assert make_run_id("q", "h", suffix="1") != make_run_id("q", "h", suffix="2")


# --- the demo runs end-to-end and verifies a real fact -----------------------

def test_demo_run_produces_verified_report():
    question, deps, cfg = build_demo()
    report = run_sync(run(question, deps, config=cfg, run_id="t-demo"))
    assert report.statement_to_claim  # something was verified
    assert "Open Cascade" in report.body
    assert report.gaps == []


# --- A5: reproducibility ------------------------------------------------------

def test_same_run_id_and_config_yield_identical_report():
    q1, d1, c1 = build_demo()
    q2, d2, c2 = build_demo()
    r1 = run_sync(run(q1, d1, config=c1, run_id="repro"))
    r2 = run_sync(run(q2, d2, config=c2, run_id="repro"))
    assert r1.body == r2.body
    assert r1.statement_to_claim == r2.statement_to_claim
    assert r1.gaps == r2.gaps
    assert r1.sources_used == r2.sources_used


# --- checkpoint + A6 (cross-model active, provable from the log) --------------

def test_checkpoint_written_and_proves_cross_model(tmp_path):
    question, deps, cfg = build_demo()
    run_sync(run(question, deps, config=cfg, run_id="ckpt", checkpoint_dir=str(tmp_path)))
    path = tmp_path / "ckpt" / "checkpoint.json"
    assert path.exists()
    data = load_checkpoint(str(path))
    assert data["run_id"] == "ckpt"
    assert data["config_hash"]
    # A6: the log proves verifier ran on a different family than the generator.
    log = "\n".join(data["log"])
    assert "generator=claude-opus-4-8" in log
    assert "verifier=gpt-4o" in log
    # gate passed at runner level
    assert "passed=True" in log
    # the verified claim is recorded with provenance
    assert any(c["status"] == "verified" and c["sources"] for c in data["claims"])


# --- CLI ----------------------------------------------------------------------

def test_cli_demo_returns_zero_and_prints_report(capsys):
    rc = main(["--demo"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Verified findings" in out
    assert "Open Cascade" in out


def test_cli_no_question_prints_help_returns_2(capsys):
    rc = main([])
    assert rc == 2


def test_cli_real_mode_without_adapter_returns_3(capsys):
    rc = main(["what is the capital of France?"])
    err = capsys.readouterr().err
    assert rc == 3
    assert "Real LLM adapters are not configured" in err
