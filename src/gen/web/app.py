"""The GENESIS web app — a local, honest UI layer over the engine (no new behavior).

Every endpoint wraps the SAME functions the CLI and the tests exercise: the scripted demo
runs, the capstone, the assessment pipeline, the eval harness, and the ratification
contract. The UI's job is to make the engine's honesty VISIBLE — gaps prominent,
abstention a first-class outcome, every claim with its sources, verdicts with reasons —
never to smooth it into a chatbot answer.

The live LLM path is HARD-GATED: ``POST /api/ask`` refuses with an honest explanation
unless the environment explicitly sets ``GENESIS_ALLOW_LIVE=1`` (the owner's live-run
decision). Everything else is deterministic and offline. Run locally with
``python -m gen.web`` — nothing leaves the machine.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ..core.interfaces import GateResult
from ..core.state import Claim, Report, Specification
from ..pipeline import Assessment, assess_specification
from ..ratification import RatificationItem, SignOff, is_ratified, ratification_packet

_STATIC = Path(__file__).parent / "static"


def _live_enabled() -> bool:
    return os.environ.get("GENESIS_ALLOW_LIVE") == "1"


# --- serializers (dataclasses -> JSON-friendly dicts) ----------------------------

def _claim_dict(c: Claim) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "status": c.status.value,
        "confidence": c.confidence,
        "sources": [s.url_or_id for s in c.sources],
        "verification": [s.url_or_id for s in c.verification],
    }


def _report_dict(r: Report, claims: list[Claim]) -> dict:
    return {
        "question": r.question,
        "body": r.body,
        "statement_to_claim": r.statement_to_claim,
        "gaps": r.gaps,
        "sources_used": r.sources_used,
        "claims": {c.id: _claim_dict(c) for c in claims},
    }


def _spec_dict(spec: Specification) -> dict:
    return {
        "run_id": spec.run_id,
        "idea": spec.idea,
        "quantities": [
            {
                "id": q.id, "name": q.name, "value": q.value, "unit": q.unit,
                "origin": q.origin.value, "grounding": q.grounding,
                "formula": q.derivation.formula if q.derivation else None,
                "rationale": q.rationale or None, "measurand": q.measurand,
                "uncertainty": q.uncertainty,
            }
            for q in spec.quantities
        ],
        "bom": [
            {"id": b.id, "name": b.name, "role": b.role.value, "count": b.count,
             "domain": b.domain.value,
             "sourcing": (f"{b.sourcing.supplier} {b.sourcing.part_number}"
                          if b.sourcing else None)}
            for b in spec.bom
        ],
        "steps": [
            {"index": s.index, "action": s.action, "check": s.check, "tool": s.tool or None}
            for s in sorted(spec.steps, key=lambda s: s.index)
        ],
        "constraints": [
            {"id": k.id, "kind": k.kind, "left": k.left, "right": k.right, "reason": k.reason}
            for k in spec.constraints
        ],
        "decisions": [
            {"id": d.id, "title": d.title, "choice": d.choice, "rationale": d.rationale}
            for d in spec.decisions
        ],
        "gaps": spec.gaps,
    }


def _gate_dict(name: str, g: GateResult) -> dict:
    return {
        "name": name, "passed": g.passed,
        "failures": [{"code": f.code, "detail": f.detail} for f in g.failures],
    }


def _assessment_dict(a: Assessment) -> dict:
    return {
        "overall": a.overall,
        "physics_checked": a.physics_checked,
        "physics_complete": a.physics_complete,
        "physics_ok": a.physics_ok,
        "checks": [
            {"name": c.name, "validator": c.validator} for c in a.physics_checks
        ],
        "check_results": [
            {"name": r["name"], "validator": r["validator"], "ok": r["ok"],
             "safety_factor": (r["result"] or {}).get(
                 "safety_factor", (r["result"] or {}).get("ratio"))}
            for r in _run_checks(a)
        ],
        "gaps": a.physics_gaps,
        "constraints_consistent": a.constraints_consistent,
        "clarification_questions": [
            {"measurand": q.measurand, "question": q.question,
             "unblocks": list(q.unblocks), "priority": q.priority}
            for q in a.clarification_questions
        ],
        "corroboration_ok": a.corroboration.ok if a.corroboration else None,
    }


def _run_checks(a: Assessment) -> list[dict]:
    from ..physics_validation import run_physics_checks
    return run_physics_checks(a.physics_checks)


def _ratification_dict(items: list[RatificationItem]) -> list[dict]:
    return [
        {"kind": it.kind, "ref": it.ref, "summary": it.summary, "blocking": it.blocking}
        for it in items
    ]


# --- request bodies ---------------------------------------------------------------

class SignOffBody(BaseModel):
    approved: list[str] = []
    approver: str = ""


class AskBody(BaseModel):
    question: str
    mode: str = "report"           # report | solution | spec


# --- the app ------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(title="GENESIS", docs_url=None, redoc_url=None)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/api/status")
    def status() -> dict:
        return {
            "engine": "GENESIS",
            "live_enabled": _live_enabled(),
            "offline_modes": ["report", "spec", "capstone", "assess", "eval", "ratification"],
            "note": ("Live-Läufe sind deaktiviert (Owner-Gate). Alle anderen Ansichten "
                     "sind deterministisch und offline."),
        }

    @app.get("/api/report/demo")
    async def report_demo() -> dict:
        from ..cli import build_demo
        from ..runner import run as run_alpha

        question, deps, cfg = build_demo()
        report = await run_alpha(question, deps, config=cfg, run_id="web-demo")
        claims = await deps.ledger.get_claims("web-demo")
        return _report_dict(report, claims)

    @app.get("/api/spec/demo")
    async def spec_demo() -> dict:
        from ..cli import build_spec_demo
        from ..runner import run_specification

        idea, deps, cfg = build_spec_demo()
        spec = await run_specification(idea, deps, config=cfg, run_id="web-demo-spec")
        return {"spec": _spec_dict(spec),
                "assessment": _assessment_dict(assess_specification(spec))}

    @app.get("/api/capstone")
    def capstone() -> dict:
        from ..demo import capstone_spec, capstone_state
        from ..verification.gates import gate_code, gate_delta, gate_erc, gate_gamma

        spec = capstone_spec()
        state = capstone_state()
        gates = [
            _gate_dict("γ", gate_gamma(state)),
            _gate_dict("δ", gate_delta(state)),
            _gate_dict("ERC", gate_erc(state)),
            _gate_dict("CODE", gate_code(state)),
        ]
        return {"spec": _spec_dict(spec), "gates": gates,
                "assessment": _assessment_dict(assess_specification(spec))}

    @app.get("/api/assess")
    def assess() -> dict:
        from ..demo import (
            capstone_claims, capstone_spec, drive_shaft_spec, drive_shaft_state,
        )

        out = []
        for label, spec, claims in (
            ("Antriebswelle (Physik greift)", drive_shaft_spec(), drive_shaft_state().claims),
            ("LED-Halter (statisch, keine Physik-Tags)", capstone_spec(), capstone_claims()),
        ):
            out.append({"label": label,
                        "assessment": _assessment_dict(
                            assess_specification(spec, claims=claims))})
        return {"specs": out}

    @app.get("/api/eval")
    def eval_harness() -> dict:
        from ..evaluation import all_cases, evaluate

        rep = evaluate(all_cases())
        return {
            "total": rep.total, "correct": rep.correct,
            "leaks": rep.leaks, "false_alarms": rep.false_alarms,
            "leak_rate": rep.leak_rate, "false_alarm_rate": rep.false_alarm_rate,
            "verdicts": [
                {"name": n, "expected_pass": e, "actual_pass": a, "ok": e == a}
                for n, e, a in rep.verdicts
            ],
        }

    @app.get("/api/ratification")
    def ratification() -> dict:
        from ..demo import capstone_spec, capstone_state
        from ..verification.gates import gate_gamma

        state = capstone_state()
        packet = ratification_packet(
            capstone_spec(), {"γ": gate_gamma(state)})
        return {"items": _ratification_dict(packet)}

    @app.post("/api/ratification/check")
    def ratification_check(body: SignOffBody) -> dict:
        from ..demo import capstone_spec, capstone_state
        from ..verification.gates import gate_gamma

        state = capstone_state()
        packet = ratification_packet(capstone_spec(), {"γ": gate_gamma(state)})
        signoff = SignOff(approved=frozenset(body.approved), approver=body.approver)
        from ..ratification import unratified_items
        missing = unratified_items(packet, signoff)
        return {
            "ratified": is_ratified(packet, signoff),
            "unratified": _ratification_dict(missing),
        }

    @app.post("/api/ask")
    async def ask(body: AskBody):
        if not _live_enabled():
            # The honest gate: the button exists, the engine refuses with the reason —
            # never a fabricated offline answer pretending to be research.
            return JSONResponse(status_code=403, content={
                "error": "live_disabled",
                "message": (
                    "Live-Läufe sind deaktiviert (Owner-Gate: kein Live-Run, bis die "
                    "Real-Use-Ready-Messung abgeschlossen ist). GENESIS erfindet keine "
                    "Antwort ohne echte Recherche — setze GENESIS_ALLOW_LIVE=1 und "
                    "starte Ollama (qwen2.5:14b + gemma4), um den Live-Pfad zu öffnen."
                ),
            })
        from ..cli import build_live
        from ..runner import run as run_alpha, run_solution, run_specification

        deps, cfg = build_live(
            os.environ.get("GENESIS_GENERATOR", "qwen2.5:14b"),
            os.environ.get("GENESIS_VERIFIER", "gemma4:latest"),
        )
        if body.mode == "spec":
            spec = await run_specification(body.question, deps, config=cfg)
            return {"spec": _spec_dict(spec),
                    "assessment": _assessment_dict(assess_specification(spec))}
        if body.mode == "solution":
            sr = await run_solution(body.question, deps, config=cfg)
            return {"solution": {
                "problem": sr.problem,
                "approaches": [{"name": ap.name, "grounding": ap.grounding}
                               for ap in sr.approaches],
                "gaps": sr.gaps,
            }}
        report = await run_alpha(body.question, deps, config=cfg)
        claims = await deps.ledger.get_claims(report.run_id)
        return _report_dict(report, claims)

    return app
