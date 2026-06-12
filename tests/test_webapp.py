"""The web UI layer — every endpoint wraps the proven engine, the live path is gated.

The API must serve the UI page, expose the deterministic views (report/spec/capstone/
assess/eval/ratification) with the same honest content the CLI shows, and REFUSE the live
ask with an honest reason while the owner gate is closed (never a fabricated answer).
fastapi is an optional dependency — the test skips without it. Offline, no LLM.

Run:  pytest tests/test_webapp.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

pytest.importorskip("fastapi", reason="the web UI needs the optional fastapi package")

from fastapi.testclient import TestClient  # noqa: E402

from gen.web.app import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_index_serves_the_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "GEN" in r.text and "ESIS" in r.text
    assert "Halluzination" in r.text                       # the honesty promise is on the page


def test_status_reports_the_closed_live_gate(client, monkeypatch):
    monkeypatch.delenv("GENESIS_ALLOW_LIVE", raising=False)
    s = client.get("/api/status").json()
    assert s["live_enabled"] is False
    assert "deaktiviert" in s["note"]


def test_demo_report_maps_every_statement_to_a_sourced_claim(client):
    r = client.get("/api/report/demo").json()
    assert r["statement_to_claim"]                          # something was verified
    for cid in r["statement_to_claim"].values():
        claim = r["claims"][cid]                            # mapping resolves...
        assert claim["sources"]                             # ...to a sourced claim


def test_demo_spec_carries_origins_and_the_honest_assessment(client):
    r = client.get("/api/spec/demo").json()
    origins = {q["origin"] for q in r["spec"]["quantities"]}
    assert origins <= {"grounded", "derived", "decision"}
    assert r["assessment"]["overall"] == "no_physics_indicated"   # honest, not a fake pass


def test_capstone_passes_all_gates(client):
    r = client.get("/api/capstone").json()
    assert [g["passed"] for g in r["gates"]] == [True, True, True, True]
    assert r["spec"]["gaps"]                                # the honest gaps are SERVED


def test_assess_shows_verified_shaft_and_unchecked_bracket(client):
    r = client.get("/api/assess").json()
    overall = {s["assessment"]["overall"] for s in r["specs"]}
    assert overall == {"physics_verified", "no_physics_indicated"}
    shaft = next(s for s in r["specs"] if s["assessment"]["overall"] == "physics_verified")
    factors = [c["safety_factor"] for c in shaft["assessment"]["check_results"]]
    assert all(f is not None and f > 1.0 for f in factors)  # computed margins served


def test_printability_endpoint_is_honest_in_both_worlds(client):
    # with the CAD kernel: the bracket is judged (mesh proven, advisories served);
    # without it: an explicit "unavailable" — never a silent pass. The geometry-less
    # shaft is "no_geometry" either way.
    r = client.get("/api/printability").json()
    by_id = {s["run_id"]: s for s in r["specs"]}
    shaft = by_id["drive_shaft"]
    assert shaft["status"] == "no_geometry" and shaft["mesh"] is None

    cap = by_id["capstone"]
    try:
        import cadquery  # noqa: F401
        has_kernel = True
    except ImportError:
        has_kernel = False
    if has_kernel:
        assert cap["status"] == "needs_attention" and cap["ok"]
        assert cap["mesh"]["watertight"] and cap["mesh"]["genus"] == 1
        (comp,) = cap["components"]
        assert comp["plate_contact"] and comp["unsupported_overhang_area"] == 0.0
        assert any("elephant-foot" in a for a in cap["advisories"])
        assert cap["blockers"] == []
    else:
        assert cap["status"] == "unavailable" and cap["mesh"] is None
        assert any("not judged" in a for a in cap["advisories"])


def test_eval_endpoint_reports_zero_leaks(client):
    r = client.get("/api/eval").json()
    assert r["leaks"] == [] and r["leak_rate"] == 0.0
    assert r["correct"] == r["total"]


def test_ratification_flow_no_auto_approval(client):
    items = client.get("/api/ratification").json()["items"]
    blocking = [it["ref"] for it in items if it["blocking"]]
    assert blocking                                          # there is something to sign off
    empty = client.post("/api/ratification/check", json={"approved": []}).json()
    assert empty["ratified"] is False                        # nothing approved by default
    assert len(empty["unratified"]) == len(blocking)
    full = client.post("/api/ratification/check", json={"approved": blocking}).json()
    assert full["ratified"] is True and full["unratified"] == []


def test_clarify_dialog_closes_the_loop(client):
    demo = client.get("/api/clarify/demo").json()
    assert demo["assessment"]["overall"] == "needs_clarification"
    qs = demo["questions"]
    assert len(qs) == 1 and qs[0]["measurand"] == "material.shear_strength"
    assert qs[0]["expected_unit"] == "MPa"
    answered = client.post("/api/clarify/answer", json={
        "answers": {"material.shear_strength": {"value": 260.0, "unit": "MPa"}}
    }).json()
    assert answered["assessment"]["overall"] == "physics_verified"   # yellow -> green


def test_clarify_answer_with_no_usable_answers_stays_unverified(client):
    r = client.post("/api/clarify/answer", json={"answers": {}}).json()
    assert r["assessment"]["overall"] == "needs_clarification"       # honest: nothing changed


def test_live_ask_is_refused_honestly_while_gated(client, monkeypatch):
    monkeypatch.delenv("GENESIS_ALLOW_LIVE", raising=False)
    r = client.post("/api/ask", json={"question": "irgendeine Frage", "mode": "report"})
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "live_disabled"
    assert "Owner-Gate" in body["message"]                   # the honest reason, not a fake answer
