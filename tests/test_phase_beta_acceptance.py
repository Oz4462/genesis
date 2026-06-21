"""Phase β acceptance — the four problem classes through the REAL pipeline.

Each class runs scout -> scholar -> skeptic -> synthesizer in a deterministic
"scripted world" (scripted models + canned sources) and checks the β GUARANTEES
(PHASE_BETA.md §5), not real model quality. No network, no real LLM.

  A  solved / multi-approach   -> >=2 grounded approaches              (B1,B2,B3)
  B  false-uniqueness trap     -> uniqueness REFUTED, alternatives     (B4)
  C  no groundable solution    -> abstention, no fabricated approach   (B5)
  D  contested trade-offs      -> both approaches, no fabricated winner (B2,B6)

Run:  pytest tests/test_phase_beta_acceptance.py
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
from gen.agents.synthesizer import Synthesizer  # noqa: E402
from gen.core.state import ClaimStatus, Question, RunState, SourceCandidate  # noqa: E402
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.tools.fetch import WebFetchTool  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402
from gen.verification.gates import gate_beta  # noqa: E402


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


def http_all(mapping):
    async def _get(url):
        return HttpResponse(status=200, body=mapping.get(url, ""), final_url=url)

    return _get


def scholar_llm(extract_map):
    """extract_map: list of (content_substr, claim_text, quote)."""
    def responder(system, user):
        content = user.split("SOURCE TEXT:", 1)[-1]
        for sub, text, quote in extract_map:
            if sub in content:
                return json.dumps([{"text": text, "quote": quote}])
        return "[]"

    return ScriptedLLM("claude-opus-4-8", responder)


def verifier_llm(rule):
    """rule(claim_text) -> (relation, confidence)."""
    def responder(system, user):
        claim = user.split("CLAIM:", 1)[-1].split("INDEPENDENT", 1)[0]
        rel, conf = rule(claim)
        return json.dumps({"relation": rel, "confidence": conf, "reason": "x"})

    return ScriptedLLM("gpt-4o", responder)


def synth_llm(groups):
    """groups: list of (keyword, approach_name). Routes verified claims to approaches
    by reading the claim ids straight out of the synthesizer's own prompt."""
    def responder(system, user):
        block = user.split("VERIFIED CLAIMS:", 1)[-1]
        pairs = []
        for ln in block.strip().splitlines():
            if ": " in ln:
                cid, text = ln.split(": ", 1)
                pairs.append((cid.strip(), text.strip()))
        out = []
        for keyword, name in groups:
            ids = [cid for cid, text in pairs if keyword.lower() in text.lower()]
            if ids:
                out.append({"name": name, "grounding": [ids[0]], "tradeoffs": ids[1:]})
        return json.dumps(out)

    return ScriptedLLM("claude-opus-4-8", responder)


ALWAYS_SUPPORT = lambda claim: ("supports", 0.85)  # noqa: E731


def build(problem, *, docs, extract_map, skeptic_urls, verifier_rule, synth_groups, run_id="rb"):
    ledger = InMemoryLedgerStore()
    http = {**docs, **{u: "SUPPORT: independent corroborating text" for u in skeptic_urls}}
    fetch = WebFetchTool(http_all(http))
    scout = Scout([FakeBackend("scout", list(docs.keys()))])
    scholar = Scholar(fetch, scholar_llm(extract_map), ledger)
    skeptic = Skeptic(
        [FakeBackend("skeptic", skeptic_urls)],
        fetch,
        verifier_llm(verifier_rule),
        ledger,
        min_sources_for_verified=2,
    )
    synth = Synthesizer(synth_llm(synth_groups))
    conductor = Conductor(scout, scholar, skeptic, synthesizer=synth)
    state = RunState(question=Question(raw=problem, run_id=run_id))
    run(conductor.run_solution(state))
    return state, ledger


def _claims(ledger, run_id="rb"):
    return {c.text: c for c in run(ledger.get_claims(run_id))}


def _verified_ids(ledger, run_id="rb"):
    return {c.id for c in run(ledger.get_claims(run_id)) if c.status is ClaimStatus.VERIFIED}


# --- class configs (reused for the reproducibility check) --------------------

CLASS_A = dict(
    problem="How do production systems implement API rate limiting?",
    docs={
        "https://d/token1": "Token bucket is widely used to rate-limit production APIs.",
        "https://d/token2": "Token bucket allows short bursts up to the bucket size.",
        "https://d/leaky": "Leaky bucket smooths the outgoing request rate at gateways.",
    },
    extract_map=[
        ("widely used to rate-limit", "Token bucket is used to rate-limit production APIs.",
         "Token bucket is widely used to rate-limit production APIs"),
        ("short bursts", "Token bucket allows short bursts up to the bucket size.",
         "Token bucket allows short bursts up to the bucket size"),
        ("smooths the outgoing", "Leaky bucket smooths the outgoing request rate.",
         "Leaky bucket smooths the outgoing request rate"),
    ],
    skeptic_urls=["https://i1", "https://i2"],
    verifier_rule=ALWAYS_SUPPORT,
    synth_groups=[("token", "Token bucket"), ("leaky", "Leaky bucket")],
)


# --- Class A: solved, multiple real approaches -------------------------------

def test_class_A_multiple_grounded_approaches():
    state, ledger = build(**CLASS_A)
    sr = state.solution_report
    assert sr is not None
    names = {a.name for a in sr.approaches}
    assert names == {"Token bucket", "Leaky bucket"}          # B2: real alternatives
    assert len(sr.approaches) >= 2

    verified = _verified_ids(ledger)
    for a in sr.approaches:
        assert a.grounding                                    # B1: grounded
        for cid in a.grounding:
            assert cid in verified                            # grounded in VERIFIED
        for cid in a.tradeoffs:
            assert cid in verified                            # B3: trade-offs verified

    tb = next(a for a in sr.approaches if a.name == "Token bucket")
    assert tb.tradeoffs                                       # carried a verified trade-off

    assert gate_beta(state).passed                            # B6: gate passes
    assert any("gate beta" in ln and "passed=True" in ln for ln in state.log)


def test_class_A_is_reproducible():
    s1, _ = build(**CLASS_A)
    s2, _ = build(**CLASS_A)
    shape1 = sorted((a.name, tuple(a.grounding), tuple(a.tradeoffs)) for a in s1.solution_report.approaches)
    shape2 = sorted((a.name, tuple(a.grounding), tuple(a.tradeoffs)) for a in s2.solution_report.approaches)
    assert shape1 == shape2                                   # A5-analogue: deterministic


# --- Class B: false-uniqueness trap ------------------------------------------

def test_class_B_false_uniqueness_trap_caught():
    def rule(claim):
        return ("contradicts", 0.9) if "only" in claim.lower() else ("supports", 0.85)

    state, ledger = build(
        problem="Why is the token bucket the only way to rate-limit an API?",
        docs={
            "https://d/uniq": "Token bucket is the only way to rate-limit an API.",
            "https://d/token": "Token bucket is a common rate-limiting algorithm.",
            "https://d/leaky": "Leaky bucket is another rate-limiting algorithm.",
        },
        extract_map=[
            ("the only way", "Token bucket is the only way to rate-limit an API.",
             "Token bucket is the only way to rate-limit an API"),
            ("a common rate-limiting", "Token bucket is a common rate-limiting algorithm.",
             "Token bucket is a common rate-limiting algorithm"),
            ("another rate-limiting", "Leaky bucket is another rate-limiting algorithm.",
             "Leaky bucket is another rate-limiting algorithm"),
        ],
        skeptic_urls=["https://i1", "https://i2"],
        verifier_rule=rule,
        synth_groups=[("token", "Token bucket"), ("leaky", "Leaky bucket")],
    )
    sr = state.solution_report
    claims = _claims(ledger)

    uniq = claims["Token bucket is the only way to rate-limit an API."]
    assert uniq.status is ClaimStatus.REFUTED                 # B4: trap caught, not confirmed

    grounded = {cid for a in sr.approaches for cid in (*a.grounding, *a.tradeoffs)}
    assert uniq.id not in grounded                            # never used to ground an approach

    assert len(sr.approaches) >= 2                            # real alternatives surfaced
    assert {a.name for a in sr.approaches} == {"Token bucket", "Leaky bucket"}
    assert gate_beta(state).passed


# --- Class C: no groundable solution (abstention) ----------------------------

def test_class_C_abstention():
    state, ledger = build(
        problem="What is the optimal approach to faster-than-light communication?",
        docs={"https://d/ftl": "Some speculative FTL idea is described here in prose."},
        extract_map=[
            ("speculative FTL", "A speculative FTL mechanism is proposed.",
             "Some speculative FTL idea is described here"),
        ],
        skeptic_urls=[],                                      # no independent corroboration
        verifier_rule=ALWAYS_SUPPORT,
        synth_groups=[("ftl", "FTL")],
    )
    sr = state.solution_report
    assert sr.approaches == []                                # B5: nothing fabricated
    assert any("No solution approach could be independently grounded" in g for g in sr.gaps)
    assert gate_beta(state).passed                            # honest emptiness still passes


# --- Class D: contested trade-offs -------------------------------------------

def test_class_D_contested_no_fabricated_winner():
    state, ledger = build(
        problem="Is microservices or monolith the better architecture?",
        docs={
            "https://d/micro": "Microservices enable independent deployment of components.",
            "https://d/mono": "A monolith keeps simpler operational overhead.",
        },
        extract_map=[
            ("independent deployment", "Microservices enable independent deployment.",
             "Microservices enable independent deployment"),
            ("simpler operational", "A monolith keeps simpler operational overhead.",
             "A monolith keeps simpler operational overhead"),
        ],
        skeptic_urls=["https://i1", "https://i2"],
        verifier_rule=ALWAYS_SUPPORT,
        synth_groups=[("microservices", "Microservices"), ("monolith", "Monolith")],
    )
    sr = state.solution_report
    assert {a.name for a in sr.approaches} == {"Microservices", "Monolith"}  # both sides
    assert len(sr.approaches) == 2
    # no fabricated verdict: nothing in the ledger asserts one is "better"
    texts = [c.text.lower() for c in run(ledger.get_claims("rb"))]
    assert not any("better" in t for t in texts)
    assert gate_beta(state).passed
