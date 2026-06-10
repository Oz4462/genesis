"""Phase α acceptance suite (Aufgabe 6) — the four question classes vs A1-A6.

METHODOLOGY (honest): a real run needs LLM adapters + network, which α leaves
open (PHASE_ALPHA §9). What the acceptance criteria actually assert are the
SYSTEM'S GUARANTEES — no unsourced fact, traps caught, abstention works,
reproducibility, cross-model. Those are properties of the architecture, provable
deterministically. So each question is run through the REAL pipeline
(conductor→scout→scholar→skeptic→gate) inside a controlled, scripted world that
models its class. This is the gate-first philosophy: prove the guarantee with
honest agent inputs, independent of any model's real-world retrieval quality.

The most important criteria — A3 (trap caught) and A4 (abstention) — are tested
here directly.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.config import default_config  # noqa: E402
from gen.core.state import Question, RunState, SourceCandidate  # noqa: E402
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.runner import Dependencies, run  # noqa: E402
from gen.verification.cross_model import model_family  # noqa: E402
from gen.verification.gates import gate_alpha  # noqa: E402

FIXTURES = yaml.safe_load(
    (Path(__file__).parent / "fixtures" / "phase_alpha_questions.yaml").read_text()
)


def run_sync(coro):
    return asyncio.run(coro)


# --- scripted world per class ------------------------------------------------

class ClassBackend:
    """Returns the primary doc for scout queries, independent docs for skeptic.

    The skeptic searches with the claim text (== subject); the scout searches with
    the question. That lets one backend serve both roles deterministically.
    """

    name = "scripted"

    def __init__(self, subject, doc_urls, indep_urls):
        self._subject = subject.strip()
        self._doc = doc_urls
        self._indep = indep_urls

    async def search(self, query, limit):
        urls = self._indep if query.strip() == self._subject else self._doc
        return [
            SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="x")
            for u in urls
        ][:limit]


def _http(content_map):
    from gen.tools.http import HttpResponse

    async def _get(url):
        return HttpResponse(status=200, body=content_map.get(url, ""), final_url=url)

    return _get


def build_world(fix) -> tuple[str, Dependencies]:
    klass = fix["klass"]
    subject = fix["subject"]
    question = fix["question"]
    doc = f"https://doc.example/{fix['id']}"
    doc_content = f"According to the documentation: {subject} This is stated plainly."

    # independent sources + their verifier markers, per class
    if klass == "A":           # answerable/true -> two supporting sources
        indep = {f"https://i.example/{fix['id']}-1": "SUPPORT independent corroboration one",
                 f"https://i.example/{fix['id']}-2": "SUPPORT independent corroboration two"}
    elif klass == "B":         # trap/false premise -> a contradicting source
        indep = {f"https://i.example/{fix['id']}-1":
                 "CONTRADICT: other kernels (e.g. CGAL) are also usable from Python."}
    elif klass == "C":         # unverifiable -> sources exist but none establish it
        indep = {f"https://i.example/{fix['id']}-1": "IRRELEVANT unrelated material",
                 f"https://i.example/{fix['id']}-2": "IRRELEVANT also unrelated"}
    elif klass == "D":         # contested -> one supports, one contradicts
        indep = {f"https://i.example/{fix['id']}-1": "SUPPORT one study favors it",
                 f"https://i.example/{fix['id']}-2": "CONTRADICT another study disputes it"}
    else:  # pragma: no cover
        raise ValueError(klass)

    content_map = {doc: doc_content, **indep}

    def gen_responder(system, user):
        if "sub-questions" in system:
            return json.dumps([question])
        if "SEARCH QUERIES" in system:
            return json.dumps([question])
        if "extract ATOMIC" in system:
            # extract only from the primary doc (which contains the subject verbatim)
            if subject.lower() in user.lower():
                return json.dumps([{"text": subject, "quote": subject}])
            return "[]"
        return "[]"

    def ver_responder(system, user):
        if "SUPPORT" in user:
            return json.dumps({"relation": "supports", "confidence": 0.85})
        if "CONTRADICT" in user:
            return json.dumps({"relation": "contradicts", "confidence": 0.85})
        return json.dumps({"relation": "irrelevant", "confidence": 0.0})

    deps = Dependencies(
        backends=[ClassBackend(subject, [doc], list(indep.keys()))],
        http_get=_http(content_map),
        generator_llm=ScriptedLLM("claude-opus-4-8", gen_responder),
        verifier_llm=ScriptedLLM("gpt-4o", ver_responder),
        ledger=InMemoryLedgerStore(),
    )
    return question, deps


# --- the acceptance assertions -----------------------------------------------

@pytest.mark.parametrize("fix", FIXTURES, ids=[f["id"] for f in FIXTURES])
def test_phase_alpha_behaviour_per_class(fix):
    question, deps = build_world(fix)
    report = run_sync(run(question, deps, config=default_config(), run_id=fix["id"]))
    subject = fix["subject"]
    expected = fix["expected"]

    claims = run_sync(deps.ledger.get_claims(fix["id"]))

    # A1: every asserted sentence maps to a real ledger claim that HAS sources.
    by_id = {c.id: c for c in claims}
    for sentence, cid in report.statement_to_claim.items():
        assert cid in by_id, f"asserted sentence maps to unknown claim: {sentence!r}"
        assert by_id[cid].sources, "asserted claim has no source (A1 violated)"

    # A1/A2/conditions: the gate independently agrees the report is clean.
    state = RunState(question=Question(raw=question, run_id=fix["id"]))
    state.claims = claims
    state.report = report
    assert gate_alpha(state).passed, "GATE α must pass on the produced report"

    if expected == "verified":          # class A
        assert subject in report.statement_to_claim, "true claim should be asserted"
        assert subject in report.body
    elif expected == "trap_caught":     # class B — A3
        assert subject not in report.statement_to_claim, "false premise must NOT be asserted"
        assert any(subject in g for g in report.gaps), "trap should be surfaced as a gap"
    elif expected == "abstain":         # class C — A4
        assert report.statement_to_claim == {}, "nothing should be asserted"
        assert "No claim could be independently verified" in report.body
        assert any(subject in g for g in report.gaps)
    elif expected == "dissent":         # class D
        assert subject not in report.statement_to_claim, "contested claim must not be one-sided fact"
        assert any(subject in g for g in report.gaps)
    else:  # pragma: no cover
        raise AssertionError(f"unknown expected: {expected}")


def test_A2_no_fabricated_sources_in_any_class():
    """A2: every source on every claim was actually retrieved (no dead/fake cites)."""
    for fix in FIXTURES:
        question, deps = build_world(fix)
        run_sync(run(question, deps, run_id=fix["id"]))
        for c in run_sync(deps.ledger.get_claims(fix["id"])):
            for ref in (*c.sources, *c.verification):
                assert ref.retrieved is True, f"{fix['id']}: cited a non-retrieved source"


def test_A5_reproducibility_class_A():
    fix = next(f for f in FIXTURES if f["klass"] == "A")
    _, d1 = build_world(fix)
    _, d2 = build_world(fix)
    r1 = run_sync(run(fix["question"], d1, run_id="A-repro"))
    r2 = run_sync(run(fix["question"], d2, run_id="A-repro"))
    assert r1.body == r2.body
    assert r1.statement_to_claim == r2.statement_to_claim
    assert r1.gaps == r2.gaps
    assert r1.sources_used == r2.sources_used


def test_A6_cross_model_active():
    """A6: skeptic (verifier) ran on a different family than scholar (generator)."""
    fix = next(f for f in FIXTURES if f["klass"] == "A")
    question, deps = build_world(fix)
    run_sync(run(question, deps, run_id="A-xmodel"))
    assert model_family(deps.generator_llm.model) != model_family(deps.verifier_llm.model)
    # the verified claim carries independent skeptic verification sources
    verified = [c for c in run_sync(deps.ledger.get_claims("A-xmodel")) if c.verification]
    assert verified, "a verified claim must carry independent verification (cross-model)"
