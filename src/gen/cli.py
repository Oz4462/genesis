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
from .core.state import Report, SourceCandidate
from .llm.base import ScriptedLLM
from .llm.ollama import OllamaLLM
from .ledger.store import InMemoryLedgerStore
from .runner import Dependencies, run
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
        {"phase_alpha": {"models": models}, "phase_beta": {"models": models}}
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
        prog="gen", description="GENESIS — anti-hallucination research engine (Phase α)."
    )
    parser.add_argument("question", nargs="?", help="the research question")
    parser.add_argument("--demo", action="store_true", help="run the offline deterministic demo")
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

    try:
        deps, cfg = build_live(args.generator, args.verifier)
        report = asyncio.run(
            run(args.question, deps, config=cfg, checkpoint_dir=args.checkpoint_dir)
        )
    except GenesisError as exc:
        # Honest abort: misconfiguration (same family), dead Ollama server, or a
        # systemically failing backend — never a fabricated or empty "success".
        print(f"GENESIS aborted: {exc}", file=sys.stderr)
        return 3
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
