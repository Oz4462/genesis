"""Step 3 (consolidation): the math-research branch is reachable from the SAME surfaces the
rest of the engine uses — `import gen` lazy exports, the CLI (`--mode research`), and the web
(`POST /api/research/assess`). Each surface must stay HONEST: a SURVIVED status is finite-grid
only (never a universal proof), REFUTED carries a witness, and only a cas/z3-certified proof
plus a human sign-off makes an ESTABLISHED anchor. Offline, deterministic, no LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.cli import main  # noqa: E402


# --- lazy package exports -----------------------------------------------------------

def test_gen_exposes_the_research_surface_lazily():
    import gen

    for name in ("assess_identity", "assess_inequality", "explore_family",
                 "run_identity_research", "AssumptionManifest", "NoveltyIndex",
                 "autonomous_stage", "promote_to_established", "PromotionLedger"):
        assert callable(getattr(gen, name)) or isinstance(getattr(gen, name), type)


def test_gen_lazy_export_assesses_a_polynomial_identity():
    import gen

    art = gen.assess_identity(
        "exp-binom", "(x + 1)**2", "x**2 + 2*x + 1",
        gen.AssumptionManifest(domain_id="R", variables={"x": "real"}), register=False)
    assert art.status == "SURVIVED_NOVEL"
    assert art.proof is not None and art.proof.lean_status in ("cas_certified", "z3_certified")


# --- CLI ----------------------------------------------------------------------------

def test_cli_research_survives_true_identity(capsys):
    rc = main(["--mode", "research", "(x+1)**2|x**2+2*x+1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SURVIVED" in out
    assert "SURVIVED != proven universal" in out          # the honesty caveat is always printed


def test_cli_research_refutes_false_identity_with_witness(capsys):
    rc = main(["--mode", "research", "x**2|x**2+1"])
    out = capsys.readouterr().out
    assert rc == 3                                          # refuted -> non-zero
    assert "REFUTED" in out and "Witness" in out


def test_cli_research_inequality(capsys):
    rc = main(["--mode", "research", "x**2|0|ge"])
    out = capsys.readouterr().out
    assert rc == 0 and "SURVIVED" in out


def test_cli_research_bad_input_returns_2(capsys):
    rc = main(["--mode", "research", "oops"])
    out = capsys.readouterr().out
    assert rc == 2 and "lhs|rhs" in out


def test_cli_research_unknown_relation_returns_2(capsys):
    rc = main(["--mode", "research", "x|x|foo"])
    out = capsys.readouterr().out
    assert rc == 2 and "relation" in out.lower()


def test_cli_research_unparsable_expression_returns_2(capsys):
    rc = main(["--mode", "research", "x +* y|x"])
    out = capsys.readouterr().out
    assert rc == 2 and "parse" in out.lower()


# --- web ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi", reason="the web UI needs the optional fastapi package")
    from fastapi.testclient import TestClient

    from gen.web.app import create_app
    return TestClient(create_app())


def test_status_lists_research_as_offline(client):
    assert "research" in client.get("/api/status").json()["offline_modes"]


def test_web_research_survives_true_identity(client):
    r = client.post("/api/research/assess", json={"lhs": "(x+1)**2", "rhs": "x**2+2*x+1"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "SURVIVED_NOVEL"
    assert d["proof"]["lean_status"] in ("cas_certified", "z3_certified")
    assert "ESTABLISHED anchor" in d["honesty_note"]        # honesty surfaced in the payload


def test_web_research_refutes_false_identity_with_witness(client):
    r = client.post("/api/research/assess", json={"lhs": "x**2", "rhs": "x**2+1"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "REFUTED"
    assert d["falsify"]["passed"] is False and d["falsify"]["witness"] is not None


def test_web_research_inequality(client):
    r = client.post("/api/research/assess", json={"lhs": "x**2", "rhs": "0", "relation": "ge"})
    assert r.status_code == 200 and r.json()["status"].startswith("SURVIVED")


def test_web_research_rejects_bad_relation(client):
    r = client.post("/api/research/assess", json={"lhs": "x", "rhs": "x", "relation": "foo"})
    assert r.status_code == 400


def test_web_research_rejects_unparsable_expression(client):
    r = client.post("/api/research/assess", json={"lhs": "x +* y", "rhs": "x"})
    assert r.status_code == 400


def test_web_research_rejects_overlong_expression(client):
    # hardening: length cap BEFORE any SymPy parsing (DoS guard on the HTTP body)
    r = client.post("/api/research/assess", json={"lhs": "x+" * 300 + "x", "rhs": "x"})
    assert r.status_code == 400
    assert "500" in r.json()["detail"]


def test_web_research_rejects_dunder_payload(client):
    # hardening: dunder attribute chains (the classic sympify-eval escape) never reach the parser
    r = client.post("/api/research/assess", json={"lhs": "().__class__.__mro__", "rhs": "1"})
    assert r.status_code == 400


def test_web_research_valid_expression_behavior_unchanged_after_hardening(client):
    # the hardened parse path must keep valid expressions byte-identical in verdict + variables
    r = client.post("/api/research/assess",
                    json={"lhs": "sin(x)**2 + cos(x)**2", "rhs": "1"})
    assert r.status_code == 200
    d = r.json()
    assert d["variables"] == ["x"]
    assert d["status"].startswith(("SURVIVED", "KNOWN"))
