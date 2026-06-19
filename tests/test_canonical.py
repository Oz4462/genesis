"""Tests for canonical power-law signatures + dedup (discovery/canonical.py).

Pins: equivalent forms (1.5 ≡ 3/2 ≡ 1.4999…, an explicit zero exponent is no term) collapse to one
signature; distinct forms do not; dedup keeps the first per signature; and the proposer drops a model's
own repeated proposals before they reach the gate. Offline, deterministic.
"""

import pytest

from gen.discovery.canonical import canonical_signature, dedupe_by_exponents


def test_equivalent_forms_share_a_signature():
    base = canonical_signature({"a": 1.5, "mu": -0.5})
    assert canonical_signature({"a": 1.4999999998, "mu": -0.5}) == base      # float artefact rationalised
    assert canonical_signature({"a": 1.5, "mu": -0.5, "b": 0.0}) == base     # zero exponent is no term


def test_distinct_forms_have_distinct_signatures():
    assert canonical_signature({"a": 1.5}) != canonical_signature({"a": 2.0})


def test_dedupe_keeps_first_per_signature_order_preserving():
    items = [
        {"id": 1, "exps": {"a": 1.5, "mu": -0.5}},
        {"id": 2, "exps": {"a": 1.4999999998, "mu": -0.5}},   # equivalent to #1 -> dropped
        {"id": 3, "exps": {"a": 2.0}},                         # distinct -> kept
    ]
    kept = dedupe_by_exponents(items, key=lambda it: it["exps"])
    assert [it["id"] for it in kept] == [1, 3]


@pytest.mark.asyncio
async def test_proposer_dedupes_its_own_repeated_forms():
    from gen.discovery.benchmark import pendulum_case
    from gen.discovery.symbiosis import GrokProposer
    from gen.llm.base import ScriptedLLM

    # the model emits the SAME law twice (as 0.5 and as the float artefact) plus one distinct form.
    scripted = ScriptedLLM(
        "grok-build",
        '[{"exponents": {"L": 0.5, "g": -0.5}}, {"exponents": {"L": 0.4999999998, "g": -0.5}},'
        ' {"exponents": {"L": 1.0, "g": -1.0}}]',
    )
    proposals = await GrokProposer(client=scripted, model="grok-build").propose(pendulum_case().problem)
    sigs = {canonical_signature(p.exponents) for p in proposals}
    assert len(proposals) == 2 and len(sigs) == 2          # the duplicate was dropped before gating
