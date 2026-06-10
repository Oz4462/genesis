"""GENESIS command-line entry — `python -m gen` (PHASE_ALPHA §8 / Aufgabe 5).

For Phase α a CLI suffices (PHASE_ALPHA §1: "CLI/MCP genügt für α"). A FastMCP
wrapper can wrap ``runner.run`` later without changing the core; CLI was chosen to
avoid adding a server dependency for α.

``--demo`` runs a fully offline, deterministic end-to-end pipeline (scripted
models + canned sources) so the wiring is demonstrable without API keys or
network. Real-model runs require LLMClient adapters injected into
``Dependencies`` — a thin, non-blocking step (PHASE_ALPHA §9).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import Config, default_config
from .core.state import Report, SourceCandidate
from .llm.base import ScriptedLLM
from .ledger.store import InMemoryLedgerStore
from .runner import Dependencies, run
from .tools.http import HttpResponse

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gen", description="GENESIS — anti-hallucination research engine (Phase α)."
    )
    parser.add_argument("question", nargs="?", help="the research question")
    parser.add_argument("--demo", action="store_true", help="run the offline deterministic demo")
    parser.add_argument("--checkpoint-dir", default=None, help="write a run checkpoint here")
    args = parser.parse_args(argv)

    if args.demo:
        question, deps, cfg = build_demo()
        report = asyncio.run(
            run(question, deps, config=cfg, run_id="demo-build123d",
                checkpoint_dir=args.checkpoint_dir)
        )
        print(format_report(report))
        return 0

    if not args.question:
        parser.print_help()
        return 2

    print(
        "Real LLM adapters are not configured in this build. Phase α ships the "
        "full pipeline and a deterministic offline demo. Run:\n"
        "    python -m gen --demo\n"
        "To answer arbitrary questions, inject LLMClient adapters into "
        "Dependencies (PHASE_ALPHA §9: model choice is non-blocking, behind adapters).",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
