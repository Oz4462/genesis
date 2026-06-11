"""GENESIS command-line entry — `python -m gen` (PHASE_ALPHA §8 / Aufgabe 5).

For Phase α a CLI suffices (PHASE_ALPHA §1: "CLI/MCP genügt für α"). A FastMCP
wrapper can wrap ``runner.run`` later without changing the core; CLI was chosen to
avoid adding a server dependency for α.

Two modes:
  * ``--demo`` — fully offline, deterministic end-to-end pipeline (scripted
    models + canned sources): the wiring is demonstrable without keys or network.
  * real mode (``python -m gen "question"``) — live run against a local Ollama
    server (generator and verifier from DIFFERENT model families, enforced
    before any call) and the Semantic Scholar backend. No cloud keys required.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import Config, default_config
from .core.errors import GenesisError
from .core.state import (
    Report,
    SolutionReport,
    SourceCandidate,
    Specification,
    ValueOrigin,
)
from .llm.base import ScriptedLLM
from .llm.ollama import OllamaLLM
from .ledger.store import InMemoryLedgerStore
from .runner import Dependencies, run, run_solution, run_specification
from .tools.http import HttpResponse, default_http_get
from .tools.search import SemanticScholarBackend, WikipediaBackend
from .verification.cross_model import assert_different_families

# --- offline demo world (deterministic) --------------------------------------

_DOC = "https://build123d.readthedocs.io/"
_I1 = "https://dev.example/occt-confirm-1"
_I2 = "https://dev.example/occt-confirm-2"
_DOC_CONTENT = (
    "build123d is built on the Open Cascade (OCCT) kernel for boundary "
    "representation (B-rep) solid modeling."
)
_CLAIM_TEXT = "build123d is built on the Open Cascade (OCCT) kernel for boundary representation (B-rep) solid modeling."


def _demo_http():
    pages = {
        _DOC: _DOC_CONTENT,
        _I1: "SUPPORT: build123d relies on the Open Cascade (OCCT) geometry kernel.",
        _I2: "SUPPORT: OCCT is the kernel underlying build123d.",
    }

    async def _get(url: str) -> HttpResponse:
        return HttpResponse(status=200, body=pages.get(url, ""), final_url=url)

    return _get


class _DemoBackend:
    name = "demo"

    async def search(self, query: str, limit: int):
        # skeptic verifies with the claim text ("built on"); scout uses a shorter query.
        if "built on" in query.lower():
            urls = [_I1, _I2]                 # independent corroboration for skeptic
        else:
            urls = [_DOC]                     # the primary doc for scout/scholar
        return [
            SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="demo")
            for u in urls
        ][:limit]


def _demo_generator() -> ScriptedLLM:
    import json

    def responder(system: str, user: str) -> str:
        if "sub-questions" in system:
            return json.dumps(["What CAD kernel does build123d use?"])
        if "SEARCH QUERIES" in system:
            return json.dumps(["build123d Open Cascade kernel"])
        if "extract ATOMIC" in system:
            if "build123d" in user:
                return json.dumps([
                    {"text": _CLAIM_TEXT, "quote": "built on the Open Cascade"}
                ])
            return "[]"
        return "[]"

    return ScriptedLLM("claude-opus-4-8", responder)


def _demo_verifier() -> ScriptedLLM:
    import json

    def responder(system: str, user: str) -> str:
        if "SUPPORT" in user:
            return json.dumps({"relation": "supports", "confidence": 0.85})
        return json.dumps({"relation": "irrelevant", "confidence": 0.0})

    return ScriptedLLM("gpt-4o", responder)


def build_demo() -> tuple[str, Dependencies, Config]:
    deps = Dependencies(
        backends=[_DemoBackend()],
        http_get=_demo_http(),
        generator_llm=_demo_generator(),
        verifier_llm=_demo_verifier(),
        ledger=InMemoryLedgerStore(),
    )
    question = "What CAD kernel does build123d use?"
    return question, deps, default_config()


# --- offline γ demo world (deterministic wall-bracket specification) ----------

_G_LOAD = "https://demo.example/shelf-load"
_G_SCREW = "https://demo.example/m4-screw"
_G_BRACKET = "https://demo.example/cantilever"
_G_I1 = "https://independent.example/corroborate-1"
_G_I2 = "https://independent.example/corroborate-2"

_G_DOCS = {
    _G_LOAD: "A typical wall shelf must carry a load of 12 kg.",
    _G_SCREW: "An M4 screw has a nominal diameter of 4 mm.",
    _G_BRACKET: "Cantilever brackets are used for wall-mounted shelves.",
}


def _spec_demo_http():
    pages = {
        **_G_DOCS,
        _G_I1: "SUPPORT: independent engineering source corroborating the statement.",
        _G_I2: "SUPPORT: second independent source corroborating the statement.",
    }

    async def _get(url: str) -> HttpResponse:
        return HttpResponse(status=200, body=pages.get(url, ""), final_url=url)

    return _get


class _SpecDemoBackend:
    name = "demo-spec"

    async def search(self, query: str, limit: int):
        # The scout's scripted query contains "parts"; every other search comes
        # from the skeptic verifying a claim -> serve independent corroboration.
        urls = list(_G_DOCS) if "parts" in query.lower() else [_G_I1, _G_I2]
        return [
            SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="demo")
            for u in urls
        ][:limit]


def _parse_id_lines(block: str) -> dict[str, str]:
    """'<id>: <text>' lines -> {id: text} (used to read ids from agent prompts)."""
    out: dict[str, str] = {}
    for line in block.strip().splitlines():
        if ": " in line:
            cid, text = line.split(": ", 1)
            out[cid.strip()] = text.strip()
    return out


def _spec_demo_generator() -> ScriptedLLM:
    import json

    def responder(system: str, user: str) -> str:
        if "sub-questions" in system:
            return json.dumps(["What are the verified facts for a wall shelf bracket?"])
        if "SEARCH QUERIES" in system:
            return json.dumps(["wall bracket parts"])
        if "extract ATOMIC" in system:
            content = user.split("SOURCE TEXT:", 1)[-1]
            for text in _G_DOCS.values():
                if text in content:
                    # the claim IS the doc sentence; the quote is verbatim
                    return json.dumps([{"text": text, "quote": text}])
            return "[]"
        if "group VERIFIED" in system:
            claims = _parse_id_lines(user.split("VERIFIED CLAIMS:", 1)[-1])
            anchor = [cid for cid, text in claims.items() if "Cantilever" in text]
            if not anchor:
                return "[]"
            return json.dumps(
                [{"name": "Cantilever bracket", "grounding": anchor, "tradeoffs": []}]
            )
        if "build SPECIFICATION" in system:
            approaches = _parse_id_lines(user.split("GROUNDED APPROACHES:", 1)[-1].split("VERIFIED CLAIMS:", 1)[0])
            claims = _parse_id_lines(user.split("VERIFIED CLAIMS:", 1)[-1])
            ap_id = next(iter(approaches), None)
            c_load = next((cid for cid, t in claims.items() if "12 kg" in t), None)
            c_screw = next((cid for cid, t in claims.items() if "4 mm" in t), None)
            if not (ap_id and c_load and c_screw):
                return "{}"
            return json.dumps(
                {
                    "approach_id": ap_id,
                    "quantities": [
                        {"id": "q_load", "name": "verified shelf load", "unit": "kg",
                         "origin": "grounded", "value": 12, "grounding": [c_load]},
                        {"id": "q_screw_d", "name": "screw diameter", "unit": "mm",
                         "origin": "grounded", "value": 4, "grounding": [c_screw]},
                        {"id": "q_sf", "name": "safety factor", "unit": "1",
                         "origin": "decision", "value": 2,
                         "rationale": "conservative for static indoor load; 1.5 and 3 considered"},
                        {"id": "q_design", "name": "design load", "unit": "kg",
                         "origin": "derived", "formula": "q_load * q_sf",
                         "inputs": ["q_load", "q_sf"]},
                        {"id": "q_hole_d", "name": "screw hole diameter", "unit": "mm",
                         "origin": "decision", "value": 4.5,
                         "rationale": "clearance fit for an M4 screw"},
                        {"id": "q_hole_r", "name": "screw hole radius", "unit": "mm",
                         "origin": "derived", "formula": "q_hole_d / 2",
                         "inputs": ["q_hole_d"]},
                        {"id": "q_w", "name": "bracket width", "unit": "mm",
                         "origin": "decision", "value": 60,
                         "rationale": "fits a standard shelf depth"},
                        {"id": "q_h", "name": "bracket height", "unit": "mm",
                         "origin": "decision", "value": 80,
                         "rationale": "lever arm for the design load"},
                        {"id": "q_t", "name": "bracket thickness", "unit": "mm",
                         "origin": "decision", "value": 6,
                         "rationale": "printable wall thickness"},
                    ],
                    "components": [
                        {"id": "c_bracket", "name": "bracket",
                         "quantity_ids": ["q_w", "q_h", "q_t", "q_hole_d", "q_hole_r"],
                         "geometry": {
                             "kind": "difference",
                             "children": [
                                 {"kind": "box", "params": {"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"}},
                                 {"kind": "cylinder", "params": {"radius": "q_hole_r", "height": "q_t"}},
                             ],
                         }},
                    ],
                    "bom": [
                        {"id": "b_bracket", "name": "bracket", "role": "part",
                         "count": 1, "component_id": "c_bracket"},
                        {"id": "b_screw", "name": "M4 screw", "role": "part",
                         "count": 2, "grounding": [c_screw]},
                        {"id": "b_printer", "name": "3D printer", "role": "tool", "count": 1},
                        {"id": "b_driver", "name": "screwdriver", "role": "tool", "count": 1},
                    ],
                    "steps": [
                        {"id": "s1", "index": 1,
                         "action": "3D-print the bracket per its CSG geometry.",
                         "uses": ["b_printer"], "inputs": ["b_bracket"],
                         "outputs": ["a_printed"],
                         "check": "Printed part measures q_w x q_h x q_t within printer tolerance.",
                         "quantity_refs": ["q_w", "q_h", "q_t"]},
                        {"id": "s2", "index": 2,
                         "action": "Mount the printed bracket to the wall with both screws.",
                         "uses": ["b_driver", "b_screw"], "inputs": ["a_printed"],
                         "outputs": ["a_mounted"],
                         "check": "Bracket carries the design load q_design without movement.",
                         "quantity_refs": ["q_design"]},
                    ],
                    "constraints": [
                        {"id": "k1", "kind": "ge", "left": "q_hole_d",
                         "right": "q_screw_d",
                         "reason": "screw must pass through the hole"},
                    ],
                    "decisions": [
                        {"id": "d_mat", "title": "Material", "choice": "PLA, 3D-printed",
                         "rationale": "locally available; sufficient for static indoor load"},
                    ],
                }
            )
        return "[]"

    return ScriptedLLM("claude-opus-4-8", responder)


def build_spec_demo() -> tuple[str, Dependencies, Config]:
    deps = Dependencies(
        backends=[_SpecDemoBackend()],
        http_get=_spec_demo_http(),
        generator_llm=_spec_demo_generator(),
        verifier_llm=_demo_verifier(),
        ledger=InMemoryLedgerStore(),
    )
    idea = "A wall-mounted shelf bracket that carries the verified shelf load"
    return idea, deps, default_config()


# --- live wiring (local Ollama + Semantic Scholar) ----------------------------

def build_live(generator: str, verifier: str) -> tuple[Dependencies, Config]:
    """Wire real adapters: local Ollama models + Semantic Scholar + real HTTP.

    Pure wiring — performs no network call itself. The cross-model rule is
    enforced HERE, before any model is contacted: a misconfigured pair must
    fail closed at the edge, not after the generator has already produced
    claims. The returned config carries the same model ids the dependencies
    run on, so the skeptic's audit (against config) and config_hash (A5) stay
    consistent with reality.
    """
    assert_different_families(generator, verifier)
    deps = Dependencies(
        # Wikipedia first: keyless and reliable. Semantic Scholar second: academic
        # depth, but 429s without a key — it degrades visibly (logged) rather than
        # blocking the run, so a missing key never fabricates or empties a result.
        backends=[
            WikipediaBackend(default_http_get),
            SemanticScholarBackend(default_http_get),
        ],
        http_get=default_http_get,
        generator_llm=OllamaLLM(generator),
        verifier_llm=OllamaLLM(verifier),
        ledger=InMemoryLedgerStore(),
    )
    models = {"generator": generator, "verifier": verifier}
    config = Config.from_dict(
        {
            "phase_alpha": {"models": models},
            "phase_beta": {"models": models},
            "phase_gamma": {"models": models},
        }
    )
    return deps, config


# --- presentation ------------------------------------------------------------

def format_report(report: Report) -> str:
    lines = []
    lines.append("=" * 64)
    lines.append("GENESIS — Phase α verified research report")
    lines.append("=" * 64)
    lines.append(f"Question: {report.question}")
    lines.append("")
    if report.statement_to_claim:
        lines.append("Verified findings (each line is backed by a ledger claim):")
        for sentence in report.body.splitlines():
            lines.append(f"  • {sentence}")
    else:
        lines.append("Verified findings: none — nothing could be independently verified.")
    if report.gaps:
        lines.append("")
        lines.append("Gaps / explicitly NOT asserted as fact:")
        for gap in report.gaps:
            lines.append(f"  - {gap}")
    if report.sources_used:
        lines.append("")
        lines.append("Sources used:")
        for src in report.sources_used:
            lines.append(f"    {src}")
    lines.append("=" * 64)
    return "\n".join(lines)


def format_solution(sr: SolutionReport) -> str:
    lines = []
    lines.append("=" * 64)
    lines.append("GENESIS — Phase β grounded solution space")
    lines.append("=" * 64)
    lines.append(f"Problem: {sr.problem}")
    lines.append("")
    if sr.approaches:
        lines.append("Grounded approaches (each anchored in VERIFIED claims):")
        for ap in sr.approaches:
            lines.append(f"  • {ap.name}")
            lines.append(f"      grounding: {', '.join(ap.grounding)}")
            if ap.tradeoffs:
                lines.append(f"      tradeoffs: {', '.join(ap.tradeoffs)}")
    else:
        lines.append("Grounded approaches: none — nothing could be anchored.")
    if sr.gaps:
        lines.append("")
        lines.append("Gaps / explicitly NOT asserted:")
        for gap in sr.gaps:
            lines.append(f"  - {gap}")
    lines.append("=" * 64)
    return "\n".join(lines)


def _format_geometry(node, indent: int) -> list[str]:
    pad = "  " * indent
    if node.params:
        params = ", ".join(f"{k}={v}" for k, v in sorted(node.params.items()))
        lines = [f"{pad}{node.kind}({params})"]
    else:
        lines = [f"{pad}{node.kind}:"]
    for child in node.children:
        lines.extend(_format_geometry(child, indent + 1))
    return lines


def format_specification(spec: Specification) -> str:
    """Render the complete, gated build instruction (the γ deliverable)."""
    lines = []
    lines.append("=" * 64)
    lines.append("GENESIS — Phase γ verified build specification")
    lines.append("=" * 64)
    lines.append(f"Idea: {spec.idea}")
    if spec.approach_id:
        lines.append(f"Anchored in approach: {spec.approach_id}")
    lines.append("")

    if spec.quantities:
        lines.append("Quantities (every value grounded, derived, or a declared decision):")
        for q in spec.quantities:
            if q.origin is ValueOrigin.GROUNDED:
                origin = f"GROUNDED in {', '.join(q.grounding)}"
            elif q.origin is ValueOrigin.DERIVED:
                origin = f"DERIVED = {q.derivation.formula}" if q.derivation else "DERIVED"
            else:
                origin = f"DECISION — {q.rationale}"
            lines.append(f"  • {q.id}: {q.name} = {q.value:g} {q.unit}   [{origin}]")
        lines.append("")

    if spec.components:
        lines.append("Components (parametric CSG geometry; params are quantity ids):")
        for comp in spec.components:
            lines.append(f"  • {comp.id}: {comp.name}")
            if comp.geometry is not None:
                lines.extend(_format_geometry(comp.geometry, 3))
        lines.append("")

    if spec.bom:
        lines.append("Bill of materials:")
        for item in spec.bom:
            extra = f" -> {item.component_id}" if item.component_id else ""
            lines.append(f"  • {item.count}x {item.name} ({item.role.value}{extra})")
        lines.append("")

    if spec.steps:
        lines.append("Build steps (each with a human-verifiable check):")
        for step in sorted(spec.steps, key=lambda s: s.index):
            lines.append(f"  {step.index}. {step.action}")
            if step.uses:
                lines.append(f"       uses:  {', '.join(step.uses)}")
            lines.append(f"       check: {step.check}")
        lines.append("")

    if spec.constraints:
        lines.append("Checked constraints:")
        for k in spec.constraints:
            lines.append(f"  • {k.left} {k.kind} {k.right} — {k.reason}")
        lines.append("")

    if spec.decisions:
        lines.append("Decision sheet (ratify or change these — they are choices, not facts):")
        for d in spec.decisions:
            lines.append(f"  • {d.title}: {d.choice} — {d.rationale}")
        lines.append("")

    if not spec.components and not spec.steps:
        lines.append("Specification: none asserted — nothing could be grounded.")
        lines.append("")

    if spec.gaps:
        lines.append("Gaps / explicitly NOT asserted:")
        for gap in spec.gaps:
            lines.append(f"  - {gap}")
        lines.append("")

    if spec.claim_ids_used:
        lines.append("Ledger claims referenced:")
        for cid in spec.claim_ids_used:
            lines.append(f"    {cid}")
    lines.append("=" * 64)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    # The report header contains 'α'; a default Windows console (cp1252) cannot
    # encode it and print() would crash. Make stdout UTF-8 so the CLI is robust
    # everywhere without dumbing down the output.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001 - never let console setup abort a run
            pass

    parser = argparse.ArgumentParser(
        prog="gen",
        description="GENESIS — anti-hallucination engine (α report, β solution space, γ specification).",
    )
    parser.add_argument("question", nargs="?", help="the research question / problem / idea")
    parser.add_argument("--demo", action="store_true", help="run the offline deterministic demo")
    parser.add_argument(
        "--mode", choices=("report", "solution", "spec"), default="report",
        help="report = Phase α facts; solution = Phase β solution space; "
             "spec = Phase γ build specification (default: report)",
    )
    parser.add_argument("--checkpoint-dir", default=None, help="write a run checkpoint here")
    parser.add_argument(
        "--generator", default="qwen2.5:14b",
        help="Ollama model for scout/scholar (default: qwen2.5:14b)",
    )
    parser.add_argument(
        "--verifier", default="gemma4:latest",
        help="Ollama model for skeptic — MUST be a different family (default: gemma4:latest)",
    )
    args = parser.parse_args(argv)

    if args.demo:
        if args.mode == "report":
            question, deps, cfg = build_demo()
            report = asyncio.run(
                run(question, deps, config=cfg, run_id="demo-build123d",
                    checkpoint_dir=args.checkpoint_dir)
            )
            print(format_report(report))
        elif args.mode == "solution":
            idea, deps, cfg = build_spec_demo()
            sr = asyncio.run(
                run_solution(idea, deps, config=cfg, run_id="demo-bracket-solution",
                             checkpoint_dir=args.checkpoint_dir)
            )
            print(format_solution(sr))
        else:
            idea, deps, cfg = build_spec_demo()
            spec = asyncio.run(
                run_specification(idea, deps, config=cfg, run_id="demo-bracket",
                                  checkpoint_dir=args.checkpoint_dir)
            )
            print(format_specification(spec))
        return 0

    if not args.question:
        parser.print_help()
        return 2

    try:
        deps, cfg = build_live(args.generator, args.verifier)
        if args.mode == "report":
            report = asyncio.run(
                run(args.question, deps, config=cfg, checkpoint_dir=args.checkpoint_dir)
            )
            output = format_report(report)
        elif args.mode == "solution":
            sr = asyncio.run(
                run_solution(args.question, deps, config=cfg,
                             checkpoint_dir=args.checkpoint_dir)
            )
            output = format_solution(sr)
        else:
            spec = asyncio.run(
                run_specification(args.question, deps, config=cfg,
                                  checkpoint_dir=args.checkpoint_dir)
            )
            output = format_specification(spec)
    except GenesisError as exc:
        # Honest abort: misconfiguration (same family), dead Ollama server, or a
        # systemically failing backend — never a fabricated or empty "success".
        print(f"GENESIS aborted: {exc}", file=sys.stderr)
        return 3
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
