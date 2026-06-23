"""Characterization / facade-detector for ``gen.future_ideas`` (T01 depth audit).

The headline claim of ``future_ideas`` is that each of the five spec builders returns a
COMPLETE, GENUINELY DATA-DRIVEN, GATED ``Specification`` — run through the SAME
``pipeline.assess_specification`` machinery as every other spec — that fires its real
δ-physics axes to an HONEST verdict, never a masked pass.

This module is the authoritative facade-detector. It is deliberately distinct from the
legacy ``test_future_ideas.py`` (which checks the happy-path verdict + artifact bundle):
here we prove the data is not hollow and the gate is not a rubber stamp. Every test does
one of two things:

  (a) DRIVING INPUT IS CONSUMED — a derived value is recomputed from its declared inputs
      with the SAME safe evaluator the γ-gate uses, and (property-based) scaling a driving
      input scales the output, proving the number is computed from the formula, not a
      canned constant; every grounded value resolves to a real claim and every reference
      (geometry/component/constraint/claim_ids_used) resolves to a real id — proving the
      spec is wired, not a shell.

  (b) FAIL-LOUD / ABSTENTION FIRES (the mandatory NEGATIVE tests) — drop a single required
      physics input and the gate reports an honest GAP and refuses the "physics_verified"
      verdict (never a masked pass); a hollow grounded quantity (no claim) fails loud at
      construction.

Offline, deterministic, no LLM. Run:  pytest tests/test_future_ideas_characterization.py
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.core.errors import UngroundedValueError  # noqa: E402
from gen.core.state import Quantity, ValueOrigin  # noqa: E402
from gen.future_ideas import ALL_FUTURE_IDEAS  # noqa: E402
from gen.pipeline import assess_specification  # noqa: E402
from gen.physics_selection import select_physics_checks  # noqa: E402
from gen.verification.derivation import evaluate_formula  # noqa: E402

# Parametrize every test over the five builders, labelled by their run_id, so a failure
# names the offending domain. Built once at import — the builders are pure/deterministic.
_CASES = [(fn, cl) for fn, cl in ALL_FUTURE_IDEAS]
_IDS = [fn().run_id for fn, _ in _CASES]


def _recompute(quantity: Quantity, by_id: dict[str, Quantity]) -> float:
    """Re-evaluate a DERIVED quantity's formula over its declared inputs.

    Mirrors what GATE γ does: bind each input id to its quantity's value and run the
    formula through the safe evaluator. Raises if any input id is missing (a dangling
    derivation input) — exactly the defect class this audit must catch.
    """
    bindings = {name: by_id[name].value for name in quantity.derivation.inputs}
    return evaluate_formula(quantity.derivation.formula, bindings)


# ---------------------------------------------------------------------------------------
# (a) DRIVING INPUT IS CONSUMED — the specs are computed + wired, not hollow constants.
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("spec_fn,claims_fn", _CASES, ids=_IDS)
def test_derived_values_recompute_from_their_declared_inputs(spec_fn, claims_fn):
    """Every DERIVED quantity's inputs resolve to real quantities AND the formula
    recomputes the declared value — proving the number is consumed from its inputs, not a
    hand-typed constant that happens to sit in a DERIVED slot."""
    spec = spec_fn()
    by_id = {q.id: q for q in spec.quantities}
    derived = [q for q in spec.quantities if q.origin is ValueOrigin.DERIVED]
    assert derived, f"{spec.run_id}: no derived quantities — a hollow spec would have none"
    for q in derived:
        missing = [name for name in q.derivation.inputs if name not in by_id]
        assert not missing, f"{spec.run_id}/{q.id}: dangling derivation inputs {missing}"
        recomputed = _recompute(q, by_id)
        # Same tolerance posture as the γ-gate's recompute check: relative, with an
        # absolute floor so a near-zero declared value can't divide by ~0.
        assert recomputed == pytest.approx(q.value, rel=1e-9, abs=1e-9), (
            f"{spec.run_id}/{q.id}: declared {q.value} != recompute {recomputed}"
        )


@pytest.mark.parametrize("spec_fn,claims_fn", _CASES, ids=_IDS)
def test_grounded_values_and_all_references_resolve(spec_fn, claims_fn):
    """No dangling ids anywhere: every GROUNDED quantity's claim ids, every BOM grounding,
    every ``claim_ids_used``, and every geometry/component/constraint reference points at a
    real id in the same spec. A facade would leave one dangling."""
    spec = spec_fn()
    claim_ids = {c.id for c in claims_fn()}
    q_ids = {q.id for q in spec.quantities}

    for q in spec.quantities:
        if q.origin is ValueOrigin.GROUNDED:
            dangling = [g for g in q.grounding if g not in claim_ids]
            assert not dangling, f"{spec.run_id}/{q.id}: grounded on missing claim {dangling}"

    for item in spec.bom:
        dangling = [g for g in (item.grounding or []) if g not in claim_ids]
        assert not dangling, f"{spec.run_id}/{item.id}: BOM grounding missing claim {dangling}"

    dangling_used = [c for c in spec.claim_ids_used if c not in claim_ids]
    assert not dangling_used, f"{spec.run_id}: claim_ids_used references missing {dangling_used}"

    def walk(node) -> None:
        for ref in node.params.values():
            assert ref in q_ids, f"{spec.run_id}: geometry param {ref!r} unresolved"
        for child in node.children:
            walk(child)

    for comp in spec.components:
        if comp.geometry is not None:
            walk(comp.geometry)
        for ref in comp.quantity_ids:
            assert ref in q_ids, f"{spec.run_id}/{comp.id}: quantity_id {ref!r} unresolved"
        if comp.material_density is not None:
            assert comp.material_density in q_ids, (
                f"{spec.run_id}/{comp.id}: material_density {comp.material_density!r} unresolved"
            )

    for k in spec.constraints:
        assert k.left in q_ids and k.right in q_ids, (
            f"{spec.run_id}/{k.id}: constraint references unresolved quantity"
        )


@pytest.mark.parametrize("spec_fn,claims_fn", _CASES, ids=_IDS)
def test_each_spec_fires_real_physics_axes_and_is_honestly_verified(spec_fn, claims_fn):
    """The headline: the spec fires AT LEAST ONE δ-physics axis (never zero — a vacuous
    spec-level pass), runs every indicated check with no gap, and earns an honest
    ``physics_verified``. Proves the gate actually engaged the spec's physics."""
    spec = spec_fn()
    assessment = assess_specification(spec, claims=claims_fn())
    assert assessment.physics_checks, f"{spec.run_id}: NO physics axis fired (vacuous pass)"
    assert assessment.physics_gaps == [], f"{spec.run_id}: uncomputable gaps {assessment.physics_gaps}"
    assert assessment.constraint_contradictions == []
    assert assessment.physics_ok and assessment.overall == "physics_verified"


@settings(max_examples=40, deadline=None)
@given(scale=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False))
@pytest.mark.parametrize("spec_fn,claims_fn", _CASES, ids=_IDS)
def test_scaling_the_load_scales_the_bending_stress(spec_fn, claims_fn, scale):
    """PROPERTY (driving input is consumed): the cantilever bending stress ``q_sigma_nom``
    is exactly linear in its load ``q_force`` — scaling the force by k scales the
    recomputed stress by k. A hard-coded constant would ignore the input and break this.

    This is the formal facade-killer: it proves the derived output genuinely flows from the
    driving input rather than being a canned value pinned next to a decorative formula.
    """
    spec = spec_fn()
    by_id = {q.id: q for q in spec.quantities}
    sigma = by_id["q_sigma_nom"]
    assert "q_force" in sigma.derivation.inputs

    base = _recompute(sigma, by_id)
    # Perturb ONLY the load; the cantilever formula is σ = 6·F·L/(b·h²), linear in F.
    scaled_force = dataclasses.replace(by_id["q_force"], value=by_id["q_force"].value * scale)
    perturbed = dict(by_id, q_force=scaled_force)
    got = evaluate_formula(sigma.derivation.formula, {n: perturbed[n].value for n in sigma.derivation.inputs})
    assert got == pytest.approx(base * scale, rel=1e-9, abs=1e-12)


# ---------------------------------------------------------------------------------------
# (b) FAIL-LOUD / ABSTENTION — the mandatory NEGATIVE tests: the gate is no rubber stamp.
# ---------------------------------------------------------------------------------------


def _measurand_of(spec, q_id: str) -> str:
    return next(q.measurand for q in spec.quantities if q.id == q_id)


def test_dropping_a_required_input_yields_an_honest_gap_not_a_masked_pass():
    """NEGATIVE: remove a single quantity that an indicated physics axis needs (the drone's
    take-off mass, an input to the rotor-hover check whose trigger ``rotor.max_total_thrust``
    remains). The selector must report the axis as INDICATED-BUT-UNRUNNABLE (a gap), and the
    overall verdict must NOT be ``physics_verified`` — never a silent masked pass. This is
    the core anti-facade guarantee: the gate cannot pass over a hole."""
    spec_fn, claims_fn = next(c for c, run_id in zip(_CASES, _IDS) if run_id == "delivery_drone")
    spec = spec_fn()

    # vehicle.mass (q_mass) is a rotor-hover INPUT but not the trigger and not referenced by
    # geometry/constraints, so dropping it isolates the failure to the rotor-hover axis.
    assert _measurand_of(spec, "q_mass") == "vehicle.mass"
    broken = dataclasses.replace(spec, quantities=[q for q in spec.quantities if q.id != "q_mass"])

    _, gaps = select_physics_checks(broken)
    assert any("rotor_hover" in g or "vehicle.mass" in g for g in gaps), gaps

    assessment = assess_specification(broken, claims=claims_fn())
    assert assessment.physics_gaps, "dropping a required input must surface a gap"
    assert not assessment.physics_ok
    # The missing measurand is surfaced honestly (a physics gap, and a clarifying question);
    # whichever honest non-pass state wins priority, it must NOT be a clean physics pass.
    assert assessment.overall != "physics_verified"
    assert assessment.overall in {"physics_incomplete", "needs_clarification"}


def test_a_hollow_grounded_quantity_fails_loud_at_construction():
    """NEGATIVE: the data layer the specs are built on refuses a GROUNDED value with no
    backing claim — so a future facade quantity cannot silently masquerade as grounded.
    Guards the 'kein faktischer Output ohne Quelle' core principle at its root."""
    with pytest.raises(UngroundedValueError):
        Quantity(id="q_hollow", name="ungegründet", value=1.0, unit="N",
                 origin=ValueOrigin.GROUNDED, grounding=[])


def test_five_distinct_data_driven_domains():
    """Sanity: exactly five builders, five distinct run_ids, each carrying real quantities,
    components, BOM, steps and at least one constraint — five wired specs, not one stub
    cloned five times."""
    seen = set()
    for spec_fn, _ in _CASES:
        spec = spec_fn()
        seen.add(spec.run_id)
        assert spec.quantities and spec.components and spec.bom and spec.steps and spec.constraints
    assert len(seen) == 5
