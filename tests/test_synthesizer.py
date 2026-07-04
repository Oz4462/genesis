"""Tests for `synthesizer` — Phase β structuring. No network/real LLM.

Proves the synthesizer invents nothing: it references only existing VERIFIED
claim_ids, drops ids the model invents, and never emits an approach without a
verified grounding. The LLM is a deterministic ScriptedLLM.

Run:  pytest tests/test_synthesizer.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.synthesizer import (  # noqa: E402
    _MAX_APPROACHES,
    Synthesizer,
    approach_id,
)
from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Question,
    RunState,
    SourceRef,
    SourceSupport,
)
from gen.llm.base import ScriptedLLM  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def _src(u: str, retrieved: bool = True) -> SourceRef:
    return SourceRef(url_or_id=u, retrieved=retrieved, support=SourceSupport.SUPPORTS)


def _vclaim(cid: str, text: str, conf: float = 0.9) -> Claim:
    return Claim(
        id=cid,
        text=text,
        sources=[_src(f"https://s/{cid}")],
        status=ClaimStatus.VERIFIED,
        confidence=conf,
        verification=[_src(f"https://i/{cid}")],
    )


def _state(claims) -> RunState:
    st = RunState(question=Question(raw="How do systems rate-limit APIs?", run_id="r1"))
    st.claims = claims
    return st


def _llm(responder):
    return ScriptedLLM("claude-opus-4-8", responder)


def test_clusters_verified_claims_into_grounded_approaches():
    c1 = _vclaim("c1", "Token bucket is used to rate-limit production APIs.")
    c2 = _vclaim("c2", "Token bucket allows bursts up to the bucket size.")
    c3 = _vclaim("c3", "Leaky bucket smooths the outgoing request rate.")
    payload = json.dumps(
        [
            {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c2"]},
            {"name": "Leaky bucket", "grounding": ["c3"], "tradeoffs": []},
        ]
    )
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1, c2, c3])))
    names = {a.name for a in st.approaches}
    assert names == {"Token bucket", "Leaky bucket"}
    tb = next(a for a in st.approaches if a.name == "Token bucket")
    assert tb.grounding == ["c1"] and tb.tradeoffs == ["c2"]
    assert all(a.produced_by == "synthesizer" for a in st.approaches)


def test_invented_claim_id_is_dropped():
    c1 = _vclaim("c1", "Token bucket is used in production.")
    payload = json.dumps(
        [{"name": "Ghost", "grounding": ["c1", "does-not-exist"], "tradeoffs": ["also-fake"]}]
    )
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1])))
    assert len(st.approaches) == 1
    ap = st.approaches[0]
    assert ap.grounding == ["c1"]   # invented grounding id dropped
    assert ap.tradeoffs == []       # invented tradeoff id dropped


def test_approach_without_verified_grounding_is_not_emitted():
    c1 = _vclaim("c1", "Real verified claim.")
    payload = json.dumps([{"name": "Fabricated", "grounding": ["nope"], "tradeoffs": []}])
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1])))
    assert st.approaches == []      # no verified grounding -> dropped


def test_unsupported_claim_never_grounds_an_approach():
    c1 = _vclaim("c1", "Verified claim.")
    c2 = Claim(
        id="c2",
        text="Unsupported claim.",
        sources=[_src("https://s/c2")],
        status=ClaimStatus.UNSUPPORTED,
        confidence=0.1,
    )
    payload = json.dumps([{"name": "Bad", "grounding": ["c2"], "tradeoffs": []}])
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1, c2])))
    assert st.approaches == []      # c2 is not VERIFIED -> not groundable


def test_unparseable_llm_output_abstains():
    c1 = _vclaim("c1", "Verified claim.")
    st = run(Synthesizer(_llm(lambda s, u: "not json at all")).run(_state([c1])))
    assert st.approaches == []
    assert any("abstain" in line for line in st.log)


def test_no_verified_claims_abstains():
    c = Claim(
        id="c1",
        text="Only unsupported.",
        sources=[_src("https://s/c1")],
        status=ClaimStatus.UNSUPPORTED,
        confidence=0.1,
    )
    st = run(Synthesizer(_llm(lambda s, u: "[]")).run(_state([c])))
    assert st.approaches == []
    assert any("no VERIFIED claims" in line for line in st.log)


def test_under_confident_verified_is_excluded():
    c1 = _vclaim("c1", "Verified but low confidence.", conf=0.5)
    payload = json.dumps([{"name": "Low", "grounding": ["c1"], "tradeoffs": []}])
    st = run(Synthesizer(_llm(lambda s, u: payload), confidence_threshold=0.7).run(_state([c1])))
    assert st.approaches == []      # below τ -> excluded from the verified set


def test_non_string_name_is_coerced_not_crashed():
    # A non-string "name" (here an int) must NOT raise: the field is coerced like
    # architect's parsing, not trusted. Before the str() guard, `123 or ""` -> 123
    # and 123.strip() raised AttributeError, aborting the whole beta run instead of
    # honestly degrading (contract: malformed LLM output -> never crash).
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    payload = json.dumps([{"name": 123, "grounding": ["c1"], "tradeoffs": []}])
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1])))
    assert len(st.approaches) == 1
    assert st.approaches[0].name == "123"        # coerced to str, not crashed
    assert st.approaches[0].grounding == ["c1"]  # grounding still validated


def test_duplicate_approach_is_merged_and_logged():
    # Two proposals with identical name+grounding collapse to one approach; the
    # merge is logged so the audit trail can explain the missing duplicate (parity
    # with forge.py). An exact duplicate contributes nothing (+0 tradeoff ids).
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    payload = json.dumps(
        [
            {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},
            {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},
        ]
    )
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1])))
    assert len(st.approaches) == 1
    assert any("merge duplicate approach" in line for line in st.log)


def test_duplicate_approach_merges_tradeoffs_into_survivor():
    # D13(a): the id hashes only (name, sorted grounding) — two proposals that differ
    # ONLY in tradeoffs are the same approach. The duplicate's tradeoffs must be
    # merged into the survivor (not lost), and the id must stay exactly the id of the
    # (name, grounding) key: no id change for existing checkpoints (Prinzip 5).
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    c2 = _vclaim("c2", "Allows bursts up to bucket size.")
    c3 = _vclaim("c3", "Needs a refill timer per key.")
    payload = json.dumps(
        [
            {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c2"]},
            {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c3", "c2"]},
        ]
    )
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1, c2, c3])))
    assert len(st.approaches) == 1
    ap = st.approaches[0]
    assert ap.tradeoffs == ["c2", "c3"]     # union, first-seen order, no c2 twice
    assert ap.id == approach_id("r1", "Token bucket", ["c1"])   # id unchanged
    assert any("merge duplicate approach" in line for line in st.log)


def test_grounding_ids_are_deduplicated_before_id_and_emit():
    # D13(c): `c1|c1` must equal `c1` — duplicated grounding ids would otherwise
    # weaken duplicate detection (different id for the same grounding set) and leak
    # duplicated ids into the emitted approach.
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    c2 = _vclaim("c2", "Allows bursts.")
    payload = json.dumps(
        [{"name": "Token bucket", "grounding": ["c1", "c1"], "tradeoffs": ["c2", "c2"]}]
    )
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1, c2])))
    assert len(st.approaches) == 1
    ap = st.approaches[0]
    assert ap.grounding == ["c1"] and ap.tradeoffs == ["c2"]
    assert ap.id == approach_id("r1", "Token bucket", ["c1"])   # same id as plain c1


def test_approach_count_is_capped_and_logged():
    # D13(b): parsed approaches are capped at _MAX_APPROACHES (same bound as the
    # conductor's _MAX_SUB_QUESTIONS); the overflow is logged, never silent.
    c1 = _vclaim("c1", "Verified claim.")
    payload = json.dumps(
        [
            {"name": f"Ansatz {i}", "grounding": ["c1"], "tradeoffs": []}
            for i in range(_MAX_APPROACHES + 2)
        ]
    )
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1])))
    assert len(st.approaches) == _MAX_APPROACHES
    assert any("capping" in line for line in st.log)


def test_non_dict_array_elements_are_filtered_with_count_log():
    # D13(d): non-dict elements in the LLM array are filtered, but WITH a count log
    # for the audit trail — before, they vanished silently in _cluster.
    c1 = _vclaim("c1", "Verified claim.")
    payload = json.dumps(
        ["junk", {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []}, 42]
    )
    st = run(Synthesizer(_llm(lambda s, u: payload)).run(_state([c1])))
    assert len(st.approaches) == 1
    assert any("skipped 2 non-dict" in line for line in st.log)
