"""Tests for end-to-end wiring (Aufgabe 5): reproducibility, checkpoint, CLI.

Uses the deterministic offline demo world (scripted models, canned sources) so
the full pipeline is exercised without network or API keys.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.cli import build_demo, build_live, main  # noqa: E402
from gen.config import Config, config_hash, default_config  # noqa: E402
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


# --- D2: run-start timestamp injection makes created_at reproducible ----------

def test_started_at_pins_ledger_created_at_end_to_end(monkeypatch):
    """A run with an injected ``started_at`` stamps every ledger claim's created_at
    with that instant — not wall-clock — proving the run clock reaches the ledger
    through the whole α pipeline (D2, Kernprinzip 5)."""
    from datetime import datetime, timezone

    import gen.core.state as state

    fixed = datetime(2020, 3, 14, 15, 9, 26, tzinfo=timezone.utc)
    sentinel = datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            return sentinel

    monkeypatch.setattr(state, "datetime", _FakeDatetime)

    question, deps, cfg = build_demo()
    run_sync(run(question, deps, config=cfg, run_id="d2", started_at=fixed))
    claims = run_sync(deps.ledger.get_claims("d2"))
    assert claims  # the demo verifies at least one fact
    assert all(c.created_at == fixed for c in claims)
    assert all(c.created_at != sentinel for c in claims)


def test_same_started_at_yields_byte_identical_checkpoint(tmp_path):
    q1, d1, c1 = build_demo()
    q2, d2, c2 = build_demo()
    from datetime import datetime, timezone

    fixed = datetime(2020, 3, 14, 15, 9, 26, tzinfo=timezone.utc)
    a = tmp_path / "a"
    b = tmp_path / "b"
    run_sync(run(q1, d1, config=c1, run_id="rep", checkpoint_dir=str(a), started_at=fixed))
    run_sync(run(q2, d2, config=c2, run_id="rep", checkpoint_dir=str(b), started_at=fixed))
    assert (a / "rep" / "checkpoint.json").read_bytes() == (b / "rep" / "checkpoint.json").read_bytes()


# --- CLI ----------------------------------------------------------------------

def test_cli_demo_returns_zero_and_prints_report(capsys):
    rc = main(["--demo"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Verifizierte Befunde" in out
    assert "Open Cascade" in out


def test_cli_no_question_prints_help_returns_2(capsys):
    rc = main([])
    assert rc == 2


def test_cli_assess_mode_prints_the_honest_verdict(capsys):
    # the wired quality engine is reachable from the CLI, offline: the drive shaft
    # verifies, the bracket (with BOM cost obligations) may report seams_failed when
    # no seam_certificate (honest); or no_physics_indicated. Never fake verified.
    rc = main(["--mode", "assess"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "physics_verified" in out          # drive shaft — physics validators fit
    # bracket: physics-vacuous or seams (cost) — both honest, never "physics_verified"
    assert ("no_physics_indicated" in out) or ("seams_failed" in out)
    assert "Anforderungen konsistent: True" in out


def test_cli_demo_spec_appends_the_quality_assessment(capsys):
    # a gamma spec run (the same code path as a live `--mode spec`) now surfaces the
    # wired engine's honest verdict as a footer, not just the raw spec.
    rc = main(["--demo", "--mode", "spec"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Qualitätsbewertung" in out and "Anforderungen konsistent:" in out


def test_cli_demo_spec_scad_format_stays_clean(capsys):
    # machine formats must NOT get the human assessment footer (it would corrupt the source)
    rc = main(["--demo", "--mode", "spec", "--format", "scad"])
    out = capsys.readouterr().out
    assert rc == 0 and "Qualitätsbewertung" not in out


def test_cli_real_mode_same_family_fails_closed_before_any_call(capsys):
    # Generator and verifier resolve to the same family -> the cross-model guard
    # must abort BEFORE any network/LLM call (build_live wires, it never calls).
    rc = main(["q", "--generator", "qwen2.5:14b", "--verifier", "qwen2.5:7b"])
    err = capsys.readouterr().err
    assert rc == 3
    assert "famil" in err.lower()  # honest reason, not a generic failure


def test_build_live_wires_models_into_config_and_deps():
    deps, cfg = build_live("qwen2.5:14b", "gemma4:latest")
    assert deps.generator_llm.model == "qwen2.5:14b"
    assert deps.verifier_llm.model == "gemma4:latest"
    # keyless Wikipedia first; materials registry offline second (self-improve loop);
    # Semantic Scholar 429s w/o key; formula-aware DLMF/CODATA follows.
    names = [b.name for b in deps.backends]
    assert names[:4] == [
        "wikipedia",
        "materials_registry",
        "wikidata_density",
        "semantic_scholar",
    ]
    assert "formula" in names and "arxiv" in names and "openalex" in names
    # The config must carry the SAME ids the deps run on: the skeptic asserts
    # cross-model against config.phase_alpha.models.generator, and config_hash
    # (reproducibility anchor A5) must change when the live models change.
    assert cfg.phase_alpha.models.generator == "qwen2.5:14b"
    assert cfg.phase_alpha.models.verifier == "gemma4:latest"
    assert config_hash(cfg) != config_hash(default_config())


def test_build_live_rejects_same_family():
    import pytest
    from gen.core.errors import ModelConflictError

    with pytest.raises(ModelConflictError):
        build_live("qwen2.5:14b", "qwen2.5:7b")
