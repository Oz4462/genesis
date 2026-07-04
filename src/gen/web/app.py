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

from fastapi import FastAPI, HTTPException
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
        # BREP-vs-analytic geometry cross-check: "unavailable" (no CAD kernel) stays
        # visible as an honest skip — never folded into a pass.
        "geometry_status": a.geometry_status,
        "geometry_ok": a.geometry_ok,
    }


def _run_checks(a: Assessment) -> list[dict]:
    from ..physics_validation import run_physics_checks
    return run_physics_checks(a.physics_checks)


def _ratification_dict(items: list[RatificationItem]) -> list[dict]:
    return [
        {"kind": it.kind, "ref": it.ref, "summary": it.summary, "blocking": it.blocking}
        for it in items
    ]


def _research_dict(art, variables: list[str], relation: str) -> dict:
    """JSON-safe view of a math-research IdentityArtifact. Mirrors the CLI's honest badges:
    a SURVIVED status is NOT a universal proof — only the proof certificate (cas/z3) plus a
    human sign-off makes an ESTABLISHED anchor. Witness/novelty are surfaced verbatim."""
    proof = None
    if art.proof is not None:
        proof = {
            "method": art.proof.method,
            "lean_status": art.proof.lean_status,
            "deductively_proved": art.proof.deductively_proved,
            "tier": art.proof_tier,
        }
    falsify = None
    if art.falsify is not None:
        f = art.falsify
        falsify = {
            "samples_tested": f.samples_tested, "passed": f.passed,
            "refutation_mode": f.refutation_mode, "witness": f.witness,
            "witness_residual": f.witness_residual, "coverage_claim": f.coverage_claim,
        }
    novelty = None
    if art.search is not None:
        s = art.search
        novelty = {
            "match_kind": s.match_kind, "hits": s.hits,
            "nearest_distance": s.nearest_distance, "corpora_checked": list(s.corpora_checked),
        }
    return {
        "lhs": art.claim.lhs, "rhs": art.claim.rhs, "relation": relation,
        "domain_id": art.claim.manifest.domain_id, "variables": variables,
        "status": art.status, "promotion": art.promotion, "severity": art.severity,
        "proof": proof, "falsify": falsify, "novelty": novelty, "note": art.note,
        "honesty_note": ("SURVIVED is finite-grid only, never a universal proof; an "
                         "ESTABLISHED anchor needs a cas/z3-certified proof AND a human sign-off."),
    }


def _files_dict(spec: Specification) -> dict:
    """Render the spec's deliverable files inline (strings), one honest entry each.

    Uses the SAME render paths as the CLI (including the mesh-integrity-gated STL).
    A format that cannot be rendered yields an explanatory note instead of being
    silently dropped — the UI shows every deliverable or the reason it is absent."""
    from ..cli import render_spec

    out: dict[str, str] = {}
    for key, fmt in (("bauanleitung.md", "md"), ("modell.scad", "scad"),
                     ("modell_build123d.py", "b123d"), ("modell.stl", "stl")):
        try:
            out[key] = render_spec(spec, fmt)
        except Exception as exc:  # noqa: BLE001 - surfaced per file, never a crash
            out[key] = f"# Export nicht möglich: {type(exc).__name__}: {exc}"
    return out


def _printability_dict(spec: Specification) -> dict:
    """One spec's printability verdict, JSON-safe (the shared serializer for the
    printability endpoint and the result payloads)."""
    from ..pipeline import assess_printability

    p = assess_printability(spec)
    return {
        "status": p.status,
        "ok": p.ok,
        "mesh": ({
            "watertight": p.mesh["watertight"],
            "consistent_winding": p.mesh["consistent_winding"],
            "genus": p.mesh["genus"], "n_facets": p.mesh["n_facets"],
            "volume": p.mesh["volume"], "issues": p.mesh["issues"],
        } if p.mesh is not None else None),
        "components": [
            {
                "component": c["component"],
                "plate_contact": c["first_layer"]["plate_contact"],
                "footprint": list(c["first_layer"]["footprint"]),
                "height": c["first_layer"]["height"],
                "elephant_foot_risk": c["first_layer"]["elephant_foot_risk"],
                "recommended_base_chamfer": c["first_layer"]["recommended_base_chamfer"],
                "overhang_area": c["overhang"]["overhang_area"],
                "unsupported_overhang_area": c["unsupported_overhang_area"],
                # JSON has no Infinity: an unbridgeable span is surfaced as
                # null + the blocker text, never as a fake number.
                "worst_bridge_span": (
                    None if c["bridges"]["worst_span"] in (None, float("inf"))
                    else c["bridges"]["worst_span"]),
            }
            for c in p.components
        ],
        "blockers": p.blockers,
        "advisories": p.advisories,
    }


# --- invention loop serializers (INVENTOR §3: concept -> grounded spec -> Pareto front) ------

def _possibility_dict(p) -> dict:
    """A proposed concept (core.state.Possibility): a direction + the real mechanism it leans on +
    the grounding claim ids. Asserts no new fact — the substance lives in the grounding."""
    return {"id": p.id, "statement": p.statement, "mechanism": p.mechanism,
            "grounding": list(p.grounding)}


def _invention_dict(inv) -> dict:
    """One concept carried through the loop, JSON-safe. A GROUNDED invention carries its spec +
    δ-physics assessment + renderable artifact files; an honest gap (specification is None) carries
    only the concept + the reasons it did not ground — never a fabricated pass."""
    spec = inv.specification
    if spec is not None:
        try:
            assessment = _assessment_dict(assess_specification(spec))
        except Exception as exc:  # noqa: BLE001 - surface the gate failure, never crash the route
            assessment = {"error": f"{type(exc).__name__}: {exc}"}
        try:
            printability = _printability_dict(spec) if inv.grounded else None
        except Exception:  # noqa: BLE001 - printability is advisory; never crash the route
            printability = None
    else:
        assessment = None
        printability = None
    return {
        "concept": _possibility_dict(inv.concept),
        "grounded": inv.grounded,
        "physics_verified": inv.physics_verified,
        "novelty_verdict": inv.novelty_verdict,
        "safety_ok": inv.safety_ok,
        "score": list(inv.score) if inv.score is not None else None,
        "gaps": list(inv.gaps),
        "prior_art": list(inv.prior_art),
        "spec": _spec_dict(spec) if spec is not None else None,
        "assessment": assessment,
        "printability": printability,
        "files": _files_dict(spec) if (spec is not None and inv.grounded) else None,
    }


def _invent_run_dict(run, framing: str, field: str, goal: str, source: str) -> dict:
    return {
        "framing": framing, "field": field, "goal": goal, "source": source,
        "refused": run.refused,
        "n_concepts": len(run.concepts),
        "grounded_count": run.grounded_count,
        "concepts": [_possibility_dict(c) for c in run.concepts],
        "inventions": [_invention_dict(i) for i in run.inventions],
        "front": [_invention_dict(i) for i in run.front],
    }


#: The concepts the offline (scripted) council replays — identical to the CLI's invent path, so a browser
#: run is byte-for-byte the same deterministic invention the CLI produces (an honest demo of the loop, not live).
_INVENT_DEMO_CONCEPTS = [
    {"statement": "Resonanter Sehnen-Greifer-Halter",
     "mechanism": "gedruckte Flexuren speichern elastische Energie",
     "grounding": ["https://openalex.org/W-actuator-mount"]},
    {"statement": "Elektroadhäsions-Greifpad", "mechanism": "elektrostatisches Klemmen",
     "grounding": ["patentsview:US-electroadhesion"]},
]


async def _run_invent(field: str, goal: str, constraints: list[str], mode: str) -> dict:
    """Run the invention loop OFFLINE-DETERMINISTIC (scripted council + architect + δ-physics gate) — the same
    path the CLI ``invent``/``solve`` default to. Safety screens FIRST: a weapons/biosecurity brief is refused
    BEFORE any concept is generated. Live council generation stays CLI-only (``--live``) so a browser run never
    hangs on a model call and never fabricates an answer — the web layer is deterministic by construction."""
    from ..inventor import InventionBrief
    from ..inventor.domains import MechatronicsDomain, scripted_mechatronics_architect
    from ..inventor.generate import scripted_council
    from ..inventor.loop import run_invention
    from ..inventor.safety import safety_gate, screen_brief

    framing = "Problem" if mode == "solve" else "Feld"
    brief = InventionBrief(field=field, run_id=f"web-{mode}", goal=goal,
                           constraints=tuple(constraints), max_concepts=3)
    verdict = screen_brief(brief)
    if verdict.refused:
        return {"framing": framing, "field": field, "goal": goal, "refused": True,
                "refused_reason": verdict.reason, "refused_category": verdict.category,
                "source": "Safety-Gate (deterministisch, vor jeder Konzept-Erzeugung)",
                "n_concepts": 0, "grounded_count": 0, "concepts": [], "inventions": [], "front": []}

    council = scripted_council(_INVENT_DEMO_CONCEPTS)
    architect = scripted_mechatronics_architect(first_natural_hz=150.0)
    domain = MechatronicsDomain()
    run = await run_invention(brief, domain=domain, council=council, architect=architect,
                              safety_screen=safety_gate)
    out = _invent_run_dict(run, framing, field, goal,
                           "offline-deterministisch (scripted council + δ-Physik-Gate)")
    out["live_note"] = ("Live-Erzeugung (echter Claude/Grok-Council) läuft über die CLI "
                        "`genesis --mode invent --live` auf der Owner-Maschine; die Web-Schicht "
                        "bleibt deterministisch.")
    return out


# --- request bodies ---------------------------------------------------------------

class SignOffBody(BaseModel):
    approved: list[str] = []
    approver: str = ""


class AnswerBody(BaseModel):
    answers: dict[str, dict] = {}      # measurand -> {"value": float, "unit": str}


def _underspecified_shaft():
    """The clarification-demo spec: the drive shaft with its shear strength removed —
    torsion is indicated but cannot run until the human answers."""
    from ..demo import drive_shaft_spec

    spec = drive_shaft_spec()
    spec.quantities = [q for q in spec.quantities
                       if q.measurand != "material.shear_strength"]
    return spec


class AskBody(BaseModel):
    question: str
    mode: str = "report"           # report | solution | spec


_MAX_EXPR_LEN = 500  # hard cap for lhs/rhs BEFORE any SymPy parsing (parser-DoS guard)


class ResearchBody(BaseModel):
    lhs: str
    rhs: str
    relation: str = "eq"           # eq | ge | gt | le | lt (structured input only — no NL parser)
    domain_id: str = "R"


class InventBody(BaseModel):
    field: str                     # the field to invent in (mode=invent) or the problem to solve (mode=solve)
    goal: str = ""                 # optional explicit goal/success property
    constraints: list[str] = []    # hard constraints the result must respect


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
            "models": {
                "generator": os.environ.get("GENESIS_GENERATOR", "qwen3.5:9b"),
                "verifier": os.environ.get("GENESIS_VERIFIER", "gemma4:12b"),
            },
            "wiring_note": (
                "Modelle werden über die Umgebungsvariablen GENESIS_GENERATOR und "
                "GENESIS_VERIFIER verdrahtet (lokales Ollama); der Live-Modus öffnet "
                "sich nur mit GENESIS_ALLOW_LIVE=1. Generator und Verifizierer müssen "
                "verschiedene Modellfamilien sein — das erzwingt der Code."
            ),
            "offline_modes": ["report", "spec", "capstone", "assess", "eval", "ratification", "research", "invent", "solve"],
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
                "assessment": _assessment_dict(assess_specification(spec)),
                "printability": _printability_dict(spec),
                "files": _files_dict(spec)}

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
                "assessment": _assessment_dict(assess_specification(spec)),
                "printability": _printability_dict(spec),
                "files": _files_dict(spec)}

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

    @app.get("/api/printability")
    def printability() -> dict:
        from ..demo import capstone_spec, drive_shaft_spec

        out = []
        for label, spec in (
            ("LED-Halter (Geometrie vorhanden)", capstone_spec()),
            ("Antriebswelle (keine Geometrie deklariert)", drive_shaft_spec()),
        ):
            out.append({"label": label, "run_id": spec.run_id,
                        **_printability_dict(spec)})
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

    @app.get("/api/clarify/demo")
    def clarify_demo() -> dict:
        from ..clarification import expected_unit

        spec = _underspecified_shaft()
        a = assess_specification(spec)
        return {
            "idea": spec.idea,
            "assessment": _assessment_dict(a),
            "questions": [
                {"measurand": q.measurand, "question": q.question,
                 "unblocks": list(q.unblocks), "priority": q.priority,
                 "expected_unit": expected_unit(q.measurand)}
                for q in a.clarification_questions
            ],
        }

    @app.post("/api/clarify/answer")
    def clarify_answer(body: AnswerBody) -> dict:
        from ..clarification import apply_answers

        answers = {
            m: (float(v["value"]), str(v["unit"]))
            for m, v in body.answers.items()
            if isinstance(v, dict) and "value" in v and "unit" in v
        }
        answered = apply_answers(_underspecified_shaft(), answers)
        return {"assessment": _assessment_dict(assess_specification(answered))}

    @app.post("/api/research/assess")
    def research_assess(body: ResearchBody) -> dict:
        # Math-research branch over the honest deterministic gates. Structured input only
        # (lhs/rhs/relation/domain) — no freetext NL->math parser. Offline + deterministic.
        #
        # Hardening (defense in depth; the primary mitigation is that the server binds
        # loopback-only, see web/__main__.py): the expression strings come straight from
        # the HTTP body and reach SymPy's eval-based parser, so BEFORE parsing we
        #   1. cap the length (parser-DoS guard),
        #   2. reject dunder tokens ('__' — the classic sympify attribute-chain escape),
        #   3. parse with evaluate=False, so no arithmetic (e.g. integer power towers)
        #      is evaluated at the web layer. Only the free-symbol NAMES are needed here;
        #      assess_identity/-inequality re-parse against the manifest symbols
        #      themselves, so valid expressions behave exactly as before.
        import sympy as sp

        from .. import identity_research as ir

        relation = (body.relation or "eq").lower()
        if relation not in ("eq", "ge", "gt", "le", "lt"):
            raise HTTPException(status_code=400, detail=f"unknown relation {relation!r} (eq|ge|gt|le|lt)")
        if body.domain_id not in ("R", "R+", "N", "Z", "C"):
            raise HTTPException(status_code=400, detail=f"unknown domain_id {body.domain_id!r}")
        for label, expr_s in (("lhs", body.lhs), ("rhs", body.rhs)):
            if len(expr_s) > _MAX_EXPR_LEN:
                raise HTTPException(
                    status_code=400,
                    detail=f"{label} too long ({len(expr_s)} > {_MAX_EXPR_LEN} chars)")
            if "__" in expr_s:
                raise HTTPException(
                    status_code=400, detail=f"{label} contains the forbidden token '__'")
        try:
            free = sorted({s.name for s in (sp.parse_expr(body.lhs, evaluate=False).free_symbols
                                            | sp.parse_expr(body.rhs, evaluate=False).free_symbols)})
        except (sp.SympifyError, SyntaxError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"could not parse expressions: {exc}")
        manifest = ir.AssumptionManifest(domain_id=body.domain_id,
                                         variables={n: "real" for n in free})
        try:
            if relation == "eq":
                art = ir.assess_identity("web-research", body.lhs, body.rhs, manifest, register=False)
            else:
                art = ir.assess_inequality("web-research", body.lhs, body.rhs, relation, manifest,
                                           register=False)
        except Exception as exc:  # noqa: BLE001 - surface the gate failure honestly, never a fake pass
            raise HTTPException(status_code=422, detail=f"assessment failed: {exc}")
        return _research_dict(art, free, relation)

    @app.post("/api/invent")
    async def invent(body: InventBody) -> dict:
        # Open-topic invention (INVENTOR §3/§5): a field in, ranked grounded inventions out. Offline-
        # deterministic (scripted council + δ-gate); a weapons brief is refused before generation.
        if not body.field.strip():
            raise HTTPException(status_code=400, detail="field darf nicht leer sein")
        return await _run_invent(body.field, body.goal, list(body.constraints), "invent")

    @app.post("/api/solve")
    async def solve(body: InventBody) -> dict:
        # Problem-driven invention: the SAME loop, framed as "solve P under constraints R".
        if not body.field.strip():
            raise HTTPException(status_code=400, detail="field (das Problem) darf nicht leer sein")
        return await _run_invent(body.field, body.goal, list(body.constraints), "solve")

    @app.get("/api/invent/eval")
    async def invent_eval() -> dict:
        # M6 integrity harness: safety refusal + grounding honesty + determinism, offline-deterministic.
        from ..inventor.eval import default_eval_cases, evaluate_inventions

        rep = await evaluate_inventions(default_eval_cases())
        return {
            "total": rep.total, "safety_correct": rep.safety_correct,
            "grounding_correct": rep.grounding_correct, "deterministic": rep.deterministic_count,
            "all_ok": rep.all_ok,
            "note": ("Integritaets-Eval (Sicherheit / Erdungs-Ehrlichkeit / Determinismus) — "
                     "offline-deterministisch. Neuheits-/Wert-Qualitaet braucht den Live-Council (CLI --live)."),
            "verdicts": [
                {"name": v.name, "refused": v.refused, "n_concepts": v.n_concepts,
                 "grounded_count": v.grounded_count, "deterministic": v.deterministic,
                 "safety_ok": v.safety_ok, "grounding_ok": v.grounding_ok, "ok": v.ok}
                for v in rep.verdicts
            ],
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
                    "starte Ollama (qwen3.5:9b + gemma4:12b), um den Live-Pfad zu öffnen."
                ),
            })
        from ..cli import build_live
        from ..runner import run as run_alpha, run_solution, run_specification

        deps, cfg = build_live(
            os.environ.get("GENESIS_GENERATOR", "qwen3.5:9b"),
            os.environ.get("GENESIS_VERIFIER", "gemma4:12b"),
        )
        if body.mode == "spec":
            spec = await run_specification(body.question, deps, config=cfg)
            return {"spec": _spec_dict(spec),
                    "assessment": _assessment_dict(assess_specification(spec)),
                    "printability": _printability_dict(spec),
                    "files": _files_dict(spec)}
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
