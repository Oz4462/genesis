"""Tests for `conductor` — orchestration + honest assembly. No network/real LLM.

Integrated mini-runs through the real scout/scholar/skeptic with faked tools,
proving: VERIFIED claims are asserted (and the gate passes), while UNSUPPORTED
and REFUTED claims are surfaced as gaps and NEVER asserted as fact. Also proves
the conductor invents nothing: every report sentence maps to a real ledger claim.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.conductor import Conductor  # noqa: E402
from gen.agents.scholar import Scholar  # noqa: E402
from gen.agents.scout import Scout  # noqa: E402
from gen.agents.skeptic import Skeptic  # noqa: E402
from gen.core.state import Question, RunState, SourceCandidate  # noqa: E402
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.tools.fetch import WebFetchTool  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402
from gen.verification.gates import gate_alpha  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeBackend:
    def __init__(self, name, urls):
        self.name = name
        self._urls = urls

    async def search(self, query, limit):
        return [
            SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="r")
            for u in self._urls
        ][:limit]


DOC = "https://docs.example/build123d"
DOC_CONTENT = "build123d is built on the Open Cascade (OCCT) kernel."
CLAIM_TEXT = "build123d uses the Open Cascade kernel."
CLAIM_QUOTE = "built on the Open Cascade"


def scholar_llm():
    payload = json.dumps([{"text": CLAIM_TEXT, "quote": CLAIM_QUOTE}])
    def responder(system, user):
        return payload if "build123d" in user else "[]"
    return ScriptedLLM("claude-opus-4-8", responder)


def verifier_llm(relation: str):
    def responder(system, user):
        return json.dumps({"relation": relation, "confidence": 0.85})
    return ScriptedLLM("gpt-4o", responder)


def build_conductor(skeptic_urls, *, relation="supports", verifier_content="SUPPORT"):
    ledger = InMemoryLedgerStore()
    fetch = WebFetchTool(http_all({
        DOC: DOC_CONTENT,
        **{u: f"{verifier_content}: independent text" for u in skeptic_urls},
    }))
    scout = Scout([FakeBackend("scout", [DOC])])
    scholar = Scholar(fetch, scholar_llm(), ledger)
    skeptic = Skeptic(
        [FakeBackend("skeptic", skeptic_urls)],
        fetch,
        verifier_llm(relation),
        ledger,
        min_sources_for_verified=2,
    )
    return Conductor(scout, scholar, skeptic), ledger


def http_all(mapping):
    async def _get(url):
        return HttpResponse(status=200, body=mapping.get(url, ""), final_url=url)
    return _get


def _state():
    return RunState(question=Question(raw="What kernel does build123d use?", run_id="r1"))


# --- VERIFIED path -----------------------------------------------------------

def test_verified_claim_is_asserted_and_gate_passes():
    conductor, ledger = build_conductor(["https://i1", "https://i2"], relation="supports")
    st = run(conductor.run(_state()))

    # the verified claim is asserted, mapped to a real ledger claim
    assert CLAIM_TEXT in st.report.statement_to_claim
    claim_id = st.report.statement_to_claim[CLAIM_TEXT]
    ledger_ids = {c.id for c in run(ledger.get_claims("r1"))}
    assert claim_id in ledger_ids
    assert CLAIM_TEXT in st.report.body
    assert st.report.gaps == []

    # the gate independently agrees the report is clean
    assert gate_alpha(st).passed
    assert any("passed=True" in line for line in st.log)


# --- UNSUPPORTED path (no independent corroboration) -------------------------

def test_unsupported_claim_is_gap_not_fact():
    conductor, ledger = build_conductor([])  # skeptic finds no independent source
    st = run(conductor.run(_state()))

    assert st.report.statement_to_claim == {}          # nothing asserted as fact
    assert "No claim could be independently verified" in st.report.body
    assert any(CLAIM_TEXT in g and "unsupported" in g for g in st.report.gaps)
    assert gate_alpha(st).passed                         # honest emptiness still passes


# --- REFUTED path (the trap) -------------------------------------------------

def test_refuted_claim_is_never_asserted():
    conductor, ledger = build_conductor(
        ["https://i1"], relation="contradicts", verifier_content="CONTRADICT"
    )
    st = run(conductor.run(_state()))

    assert st.report.statement_to_claim == {}            # refuted -> never a fact
    assert any(CLAIM_TEXT in g and "refuted" in g for g in st.report.gaps)
    assert gate_alpha(st).passed


# --- conductor invents nothing ----------------------------------------------

def test_every_asserted_sentence_maps_to_a_ledger_claim():
    conductor, ledger = build_conductor(["https://i1", "https://i2"])
    st = run(conductor.run(_state()))
    ledger_claims = {c.id: c for c in run(ledger.get_claims("r1"))}
    for sentence, cid in st.report.statement_to_claim.items():
        assert cid in ledger_claims                      # no invented claim ids
        assert sentence == ledger_claims[cid].text       # body text == claim text


def test_decompose_without_llm_yields_single_subquestion():
    conductor, _ = build_conductor(["https://i1", "https://i2"])
    st = run(conductor.run(_state()))
    assert len(st.sub_questions) == 1
    assert st.sub_questions[0].text == "What kernel does build123d use?"
