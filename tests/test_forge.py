"""Phase φ model layer — Forge acceptance (deterministic, offline ScriptedLLM).

Teeth: a possibility whose cited grounding is not a VERIFIED claim is DROPPED by code
(the φ analogue of scholar's quote guard), never emitted; a surviving divergence passes
GATE φ; no spark / no verified claims yields honest abstention.
"""

from __future__ import annotations

import asyncio

from gen.agents.forge import Forge
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
