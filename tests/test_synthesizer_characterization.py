"""Characterization tests for `synthesizer` dedup — proves it is NOT a hollow facade.

The headline claim under audit: the synthesizer deduplicates approaches correctly —
true duplicates collapse to one (and the drop is logged), but a genuinely-different
proposal survives. The pre-fix module keyed the dedup identity on the VERIFIED-filtered
tradeoffs, so a proposal whose only distinguishing field was a presented-but-unverified
tradeoff id got that id stripped FIRST and then silently collapsed into an earlier
approach — a real alternative was lost. These tests fail loudly if that facade returns.

Every test drives the REAL `Synthesizer.run` over a deterministic ScriptedLLM (the unit
under test is never mocked). They assert (a) input-sensitivity — the surviving count
changes when the presented fields change — and (b) the fail-loud grounding guard still
drops fabricated approaches, and (c) the emitted Approach carries ONLY verified ids.

Run:  pytest tests/test_synthesizer_characterization.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.synthesizer import Synthesizer, approach_id  # noqa: E402
from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Question,
    RunState,
    SourceRef,
    SourceSupport,
)
from gen.llm.base import ScriptedLLM  # noqa: E402


def _run(coro):
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
    st_ = RunState(question=Question(raw="How do systems rate-limit APIs?", run_id="r1"))
    st_.claims = claims
    return st_


def _llm(payload: str) -> ScriptedLLM:
    return ScriptedLLM("claude-opus-4-8", lambda s, u: payload)


def _synth(claims, proposals) -> RunState:
    payload = json.dumps(proposals)
    return _run(Synthesizer(_llm(payload)).run(_state(claims)))


# --- THE BUG THIS TASK FIXES -------------------------------------------------

def test_proposal_differing_only_by_unverified_tradeoff_survives():
    """The headline facade-detector. Three proposals share name+grounding; the third
    adds a presented-but-unverified tradeoff id. It is a genuinely-different alternative
    and MUST survive dedup — the pre-fix module collapsed it (verified-filtered key)."""
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    proposals = [
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},  # true dup
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c-extra"]},  # distinct
    ]
    st_ = _synth([c1], proposals)
    assert len(st_.approaches) == 2  # the distinct-presented one is kept, the true dup dropped
    assert any("drop duplicate approach" in line for line in st_.log)


def test_surviving_approach_carries_only_verified_ids():
    """Grounding validation is NOT weakened: even though the unverified tradeoff drove
    the dedup identity, the emitted Approach must surface ONLY verified ids."""
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    proposals = [
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c-extra"]},
    ]
    st_ = _synth([c1], proposals)
    assert len(st_.approaches) == 2
    for ap in st_.approaches:
        assert ap.grounding == ["c1"]          # only verified grounding
        assert "c-extra" not in ap.tradeoffs   # unverified tradeoff never surfaced
        assert ap.tradeoffs == []              # nothing verified to carry
    # The two approaches must have DISTINCT ids (downstream architect anchors by id) —
    # collapsing them onto one id would re-introduce the silent-loss bug at the id layer.
    assert len({ap.id for ap in st_.approaches}) == 2


def test_distinct_presented_grounding_also_survives():
    """Symmetry with tradeoffs: a presented-but-unverified GROUNDING id likewise marks a
    distinct proposal, so it must not collapse into the earlier one either."""
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    proposals = [
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},
        {"name": "Token bucket", "grounding": ["c1", "ghost-ground"], "tradeoffs": []},
    ]
    st_ = _synth([c1], proposals)
    assert len(st_.approaches) == 2
    for ap in st_.approaches:
        assert ap.grounding == ["c1"]  # invented grounding id stripped on emit


# --- INPUT-SENSITIVITY (output changes when input changes) -------------------

def test_output_count_is_sensitive_to_presented_tradeoffs():
    """Flip ONLY the third proposal's presented tradeoff between a duplicate value and a
    distinct value; the surviving count must move 1 -> 2. Proves the field is consumed."""
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    base = [
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},
        {"name": "Token bucket", "grounding": ["c1"], "tradeoffs": []},
    ]
    collapsed = _synth([c1], base)
    expanded = _synth([c1], base[:1] + [{"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c-extra"]}])
    assert len(collapsed.approaches) == 1   # identical presented fields collapse
    assert len(expanded.approaches) == 2    # one distinct presented tradeoff splits them


def test_true_duplicates_still_collapse_and_log():
    """The dedup must STILL work: N byte-identical proposals collapse to exactly one and
    each drop is logged. (A facade that never dedups would also pass the survive-tests.)"""
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    proposals = [{"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c1"]}] * 4
    st_ = _synth([c1], proposals)
    # tradeoffs ["c1"] overlaps grounding so it is dropped on emit; all four collapse to one.
    assert len(st_.approaches) == 1
    drops = [line for line in st_.log if "drop duplicate approach" in line]
    assert len(drops) == 3  # 4 proposals -> 1 kept + 3 dropped-as-duplicate, each logged


# --- FAIL-LOUD GUARDS still hold (no weakening) ------------------------------

def test_fabricated_approach_without_verified_grounding_is_dropped():
    """The grounding gate is not weakened by the dedup change: an approach whose grounding
    is entirely unverified is dropped (logged), never emitted on the strength of a
    presented id alone."""
    c1 = _vclaim("c1", "Real verified claim.")
    st_ = _synth([c1], [{"name": "Fabricated", "grounding": ["nope"], "tradeoffs": ["c1"]}])
    assert st_.approaches == []
    assert any("no verified grounding" in line for line in st_.log)


def test_unparseable_llm_output_abstains():
    """Malformed model output -> abstain, never crash (contract preserved)."""
    c1 = _vclaim("c1", "Verified claim.")
    st_ = _run(Synthesizer(_llm("not json")).run(_state([c1])))
    assert st_.approaches == []
    assert any("abstain" in line for line in st_.log)


# --- PROPERTY-BASED INVARIANTS -----------------------------------------------

# Distinct claim ids used to build presented tradeoff sets; all are unverified except c1.
_TRADEOFF_IDS = st.lists(
    st.sampled_from(["t-a", "t-b", "t-c", "t-d", "t-e"]),
    min_size=0,
    max_size=5,
    unique=True,
)


@settings(max_examples=75)
@given(extra=_TRADEOFF_IDS)
def test_property_distinct_presented_tradeoffs_yield_distinct_ids(extra):
    """Invariant: two proposals identical except for their presented (unverified) tradeoff
    set collapse iff those sets are equal AS SETS. The dedup id is order-insensitive, so a
    permutation does not split, but a genuinely different set always does."""
    base_id = approach_id("r1", "Token bucket", ["c1"], [])
    extra_id = approach_id("r1", "Token bucket", ["c1"], list(extra))
    permuted_id = approach_id("r1", "Token bucket", ["c1"], list(reversed(extra)))
    # Order-insensitivity: a reordering of the same presented set is the SAME approach.
    assert extra_id == permuted_id
    # Sensitivity: a non-empty presented tradeoff set always distinguishes from the bare one.
    if extra:
        assert extra_id != base_id
    else:
        assert extra_id == base_id


@settings(max_examples=50)
@given(n=st.integers(min_value=1, max_value=6))
def test_property_n_identical_proposals_collapse_to_one(n):
    """Idempotence: feeding the SAME proposal n times always yields exactly one approach,
    with n-1 'drop duplicate approach' log lines — dedup is total, not partial."""
    c1 = _vclaim("c1", "Token bucket rate-limits APIs.")
    proposals = [{"name": "Token bucket", "grounding": ["c1"], "tradeoffs": ["c-extra"]}] * n
    st_ = _synth([c1], proposals)
    assert len(st_.approaches) == 1
    drops = [line for line in st_.log if "drop duplicate approach" in line]
    assert len(drops) == n - 1
