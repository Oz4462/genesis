"""Phase φ model layer — Forge acceptance (deterministic, offline ScriptedLLM).

Teeth: a possibility whose cited grounding is not a VERIFIED claim is DROPPED by code
(the φ analogue of scholar's quote guard), never emitted; a surviving divergence passes
GATE φ; no spark / no verified claims yields honest abstention.
"""

from __future__ import annotations

import asyncio
import json

from gen.agents.forge import _MAX_POSSIBILITIES, Forge, possibility_id
from gen.core.state import (
    Claim,
    ClaimStatus,
    Question,
    RunState,
    SourceRef,
    Spark,
)
from gen.llm.base import ScriptedLLM
from gen.verification import gate_phi


def _state(claims: list[Claim], spark: Spark | None) -> RunState:
    st = RunState(question=Question(raw="spark", run_id="r1"))
    st.claims = claims
    st.spark = spark
    return st


def _verified(cid: str = "c1", conf: float = 0.9) -> Claim:
    return Claim(
        id=cid, text="Phase-change materials store latent heat at constant temperature.",
        sources=[SourceRef(url_or_id="src://pcm", retrieved=True)],
        status=ClaimStatus.VERIFIED, confidence=conf,
    )


def _run(forge: Forge, state: RunState) -> RunState:
    return asyncio.run(forge.run(state))


def test_emits_grounded_possibility_and_passes_gate():
    claim = _verified()
    forge = Forge(ScriptedLLM(
        "qwen3.5:9b",
        lambda s, u: '[{"statement":"Wärme in einem Phasenwechselmaterial speichern",'
                     '"mechanism":"latente Wärme","grounding":["c1"]}]',
    ))
    state = _run(forge, _state([claim], Spark(id="s1", raw="glätte Temperaturspitzen")))
    assert state.divergence is not None
    assert len(state.divergence.possibilities) == 1
    p = state.divergence.possibilities[0]
    assert p.grounding == ["c1"] and p.produced_by == "forge"
    # end-to-end: the produced divergence must pass the deterministic gate
    assert gate_phi(state.divergence, state.claims).passed


def test_drops_invented_grounding():
    # the model cites a claim id that is not in the verified set -> dropped, abstain
    forge = Forge(ScriptedLLM(
        "qwen3.5:9b",
        lambda s, u: '[{"statement":"erfundene Richtung","mechanism":"?","grounding":["c_fake"]}]',
    ))
    state = _run(forge, _state([_verified()], Spark(id="s1", raw="x")))
    assert state.divergence is not None
    assert state.divergence.possibilities == []
    assert any("no verified grounding" in m for m in state.log)


def test_drops_unverified_anchor():
    unver = Claim(id="c_u", text="maybe", sources=[SourceRef(url_or_id="s", retrieved=True)],
                  status=ClaimStatus.UNSUPPORTED, confidence=0.0)
    forge = Forge(ScriptedLLM(
        "qwen3.5:9b",
        lambda s, u: '[{"statement":"Richtung","mechanism":"m","grounding":["c_u"]}]',
    ))
    state = _run(forge, _state([unver], Spark(id="s1", raw="x")))
    assert state.divergence.possibilities == []


def test_no_spark_skips():
    forge = Forge(ScriptedLLM("qwen3.5:9b", lambda s, u: "[]"))
    state = _run(forge, _state([_verified()], None))
    assert state.divergence is None
    assert any("no spark" in m for m in state.log)


def test_no_verified_claims_abstains():
    forge = Forge(ScriptedLLM("qwen3.5:9b", lambda s, u: "[]"))
    state = _run(forge, _state([], Spark(id="s1", raw="x")))
    assert state.divergence is not None
    assert state.divergence.possibilities == []
    assert state.divergence.grounded_sample is True


def test_unparseable_llm_abstains():
    forge = Forge(ScriptedLLM("qwen3.5:9b", lambda s, u: "not json at all"))
    state = _run(forge, _state([_verified()], Spark(id="s1", raw="x")))
    assert state.divergence is not None
    assert state.divergence.possibilities == []


def test_duplicate_possibility_merges_mechanism_into_survivor():
    # D13(a): the id hashes only (statement, sorted grounding) — two proposals that
    # differ ONLY in mechanism are the same direction. The duplicate's mechanism is
    # merged into the survivor ("; "-joined, deduped), and the id stays exactly the
    # id of the (statement, grounding) key: no id change for existing checkpoints
    # (Prinzip 5). Symmetric to synthesizer's tradeoff merge.
    payload = json.dumps(
        [
            {"statement": "Richtung A", "mechanism": "latente Wärme", "grounding": ["c1"]},
            {"statement": "Richtung A", "mechanism": "Phasenwechsel", "grounding": ["c1"]},
            {"statement": "Richtung A", "mechanism": "latente Wärme", "grounding": ["c1"]},
        ]
    )
    forge = Forge(ScriptedLLM("qwen3.5:9b", lambda s, u: payload))
    state = _run(forge, _state([_verified()], Spark(id="s1", raw="x")))
    assert len(state.divergence.possibilities) == 1
    p = state.divergence.possibilities[0]
    assert p.mechanism == "latente Wärme; Phasenwechsel"   # merged, no third copy
    assert p.id == possibility_id("s1", "Richtung A", ["c1"])   # id unchanged
    assert any("merge duplicate possibility" in m for m in state.log)


def test_grounding_ids_are_deduplicated_before_id_and_emit():
    # D13(c): `c1|c1` must equal `c1` — duplicated grounding ids would otherwise
    # weaken duplicate detection and leak duplicated ids into the possibility.
    forge = Forge(ScriptedLLM(
        "qwen3.5:9b",
        lambda s, u: '[{"statement":"Richtung","mechanism":"m","grounding":["c1","c1"]}]',
    ))
    state = _run(forge, _state([_verified()], Spark(id="s1", raw="x")))
    assert len(state.divergence.possibilities) == 1
    p = state.divergence.possibilities[0]
    assert p.grounding == ["c1"]
    assert p.id == possibility_id("s1", "Richtung", ["c1"])   # same id as plain c1


def test_possibility_count_is_capped_and_logged():
    # D13(b): parsed possibilities are capped at _MAX_POSSIBILITIES (same bound as
    # the conductor's _MAX_SUB_QUESTIONS); the overflow is logged, never silent.
    payload = json.dumps(
        [
            {"statement": f"Richtung {i}", "mechanism": "m", "grounding": ["c1"]}
            for i in range(_MAX_POSSIBILITIES + 2)
        ]
    )
    forge = Forge(ScriptedLLM("qwen3.5:9b", lambda s, u: payload))
    state = _run(forge, _state([_verified()], Spark(id="s1", raw="x")))
    assert len(state.divergence.possibilities) == _MAX_POSSIBILITIES
    assert any("capping" in m for m in state.log)


def test_non_dict_array_elements_are_filtered_with_count_log():
    # D13(d): non-dict elements in the LLM array are filtered, but WITH a count log
    # for the audit trail — before, they vanished silently in _open.
    forge = Forge(ScriptedLLM(
        "qwen3.5:9b",
        lambda s, u: '["junk",{"statement":"Richtung","mechanism":"m","grounding":["c1"]},42]',
    ))
    state = _run(forge, _state([_verified()], Spark(id="s1", raw="x")))
    assert len(state.divergence.possibilities) == 1
    assert any("skipped 2 non-dict" in m for m in state.log)


def test_non_string_statement_or_mechanism_is_coerced_not_crashed():
    # Non-string 'statement'/'mechanism' from the LLM must NOT raise: both fields are
    # coerced (str()) like architect/synthesizer, not trusted. Before the guard,
    # `123 or ""` -> 123 and 123.strip() raised AttributeError OUTSIDE the
    # LLMOutputError handler, crashing the whole phi run instead of degrading.
    forge = Forge(ScriptedLLM(
        "qwen3.5:9b",
        lambda s, u: '[{"statement":123,"mechanism":456,"grounding":["c1"]}]',
    ))
    state = _run(forge, _state([_verified()], Spark(id="s1", raw="x")))
    assert state.divergence is not None
    assert len(state.divergence.possibilities) == 1
    p = state.divergence.possibilities[0]
    assert p.statement == "123" and p.mechanism == "456"   # coerced, not crashed
    assert p.grounding == ["c1"]
