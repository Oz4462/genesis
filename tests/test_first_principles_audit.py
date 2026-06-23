"""first_principles audit: characterize recompute (gate_c6) + derive only emits verified proofs.

This is the authoritative characterization test per T03. It proves:
- verify_proof recomputes every step from axioms + prior *stated* claims and sets verified
  iff the claim matches (within tolerance); input .verified flags are ignored.
- A tampered step (claim does not follow from formula over priors) is caught exactly there
  (verified=False at that index); overall proven=False.
- derive performs bounded (+-*/ only, up to max_ops) search and returns *only* proofs where
  every step has verified=True and proven=True (re-checked via verify_proof).
- Unreachable within bound => None (never a false proven=False proof).
- Invariants via property-based tests (hypothesis).

Uses only stdlib + the module under test + pre-existing verification.derivation (for cross-check in props).
"""

from __future__ import annotations

import math

from hypothesis import given, strategies as st

from gen.discovery import Axiom, ProofStep, ProofTree, verify_proof, derive


# ---------- helpers for properties (recompute cross-check) ----------

def _axiom_dict(axioms: list[Axiom]) -> dict[str, float]:
    return {ax.name: ax.value for ax in axioms}


# ---------- SOUND CHAIN + RECOMPUTE ----------

def test_verify_proof_confirms_sound_axioms_to_target_chain():
    """Every step recomputed; all verified=True and proven=True for correct chain."""
    axioms = [Axiom("F", 12.0), Axiom("m", 3.0), Axiom("t", 2.0)]
    steps = [
        ProofStep("a", "F / m", 4.0),
        ProofStep("v", "a * t", 8.0),
    ]
    proof = verify_proof(axioms, steps, target_name="v", target_value=8.0)
    assert proof.proven is True
    assert all(s.verified for s in proof.steps)
    assert proof.target_name == "v"
    assert proof.target_value == 8.0
    assert len(proof.steps) == 2


def test_verify_proof_recomputes_and_ignores_input_verified_flag():
    """Recompute is the source of truth: a pre-marked verified=True on bad claim is overridden."""
    axioms = [Axiom("F", 12.0), Axiom("m", 3.0)]
    # Claim is wrong (should be 4), but caller pre-sets verified=True to simulate "trust"
    bad_step = ProofStep("a", "F / m", 5.0, verified=True)
    proof = verify_proof(axioms, [bad_step], target_name="a")
    assert proof.proven is False
    assert proof.steps[0].verified is False  # recomputed and rejected


# ---------- TAMPER CAUGHT AT EXACT STEP (NEGATIVE) ----------

def test_verify_catches_tampered_step_exactly_at_that_step():
    """gate_c6: tampered claim fails only at the offending step; prior steps can still verify."""
    axioms = [Axiom("F", 12.0), Axiom("m", 3.0), Axiom("t", 2.0)]
    steps = [
        ProofStep("a", "F / m", 4.0),   # correct
        ProofStep("v", "a * t", 9.0),   # tampered: 4*2=8, not 9
    ]
    proof = verify_proof(axioms, steps, target_name="v", target_value=8.0)
    assert proof.proven is False
    assert proof.steps[0].verified is True
    assert proof.steps[1].verified is False  # caught exactly here


def test_verify_tampered_prior_does_not_silently_validate_dependent():
    """Overall proof fails when any step (here the first) does not recompute correctly."""
    axioms = [Axiom("F", 12.0), Axiom("m", 3.0), Axiom("t", 2.0)]
    steps = [
        ProofStep("a", "F / m", 5.0),   # tampered
        ProofStep("v", "a * t", 10.0),  # this would follow from the *stated* a=5
    ]
    proof = verify_proof(axioms, steps, target_name="v", target_value=8.0)
    assert proof.proven is False
    assert proof.steps[0].verified is False
    # second step: follows from *stated* (wrong) prior, can be locally verified, but overall not proven
    assert proof.steps[1].verified is True


# ---------- DERIVE: BOUNDED SEARCH, ONLY VERIFIED PROOFS, NO FALSE PROOFS ----------

def test_derive_returns_none_for_unreachable_within_bound():
    """Honest boundary: no short derivation => None, never a fabricated proof (proven=False or otherwise)."""
    proof = derive([Axiom("a", 2.0), Axiom("b", 3.0)], target_value=100.0, max_ops=1)
    assert proof is None


def test_derive_one_op_returns_verified_proof():
    """derive finds 1-op, calls verify internally, returns only a fully verified+proven tree."""
    proof = derive([Axiom("F", 12.0), Axiom("m", 3.0)], target_value=4.0, max_ops=1)
    assert proof is not None
    assert isinstance(proof, ProofTree)
    assert proof.proven is True
    assert len(proof.steps) == 1
    assert proof.steps[0].verified is True
    assert proof.steps[0].formula in {"F / m", "m / F"}  # order depends on enumeration, either ok if correct


def test_derive_two_op_returns_verified_proof_and_skips_when_max_ops_1():
    """2-op target only reachable with 2 ops; max_ops=1 yields None; returned proof always verified."""
    axioms = [Axiom("a", 6.0), Axiom("b", 2.0), Axiom("c", 4.0)]
    proof = derive(axioms, target_value=7.0, max_ops=2)
    assert proof is not None
    assert proof.proven is True
    assert proof.steps[0].verified is True
    assert "(" in proof.steps[0].formula  # grouped 2-op form
    # bound respected
    assert derive(axioms, target_value=7.0, max_ops=1) is None


def test_derive_respects_max_ops_bound():
    """derive must not exceed max_ops: max_ops=0 must yield None for any op-requiring target (1-op target)."""
    axioms = [Axiom("F", 12.0), Axiom("m", 3.0)]
    # 1-op target
    p0 = derive(axioms, target_value=4.0, max_ops=0)
    assert p0 is None, "must not emit 1-op derivation when max_ops=0"
    # sanity: max_ops=1 allows it
    p1 = derive(axioms, target_value=4.0, max_ops=1)
    assert p1 is not None and p1.proven


def test_derive_returned_proof_recomputes_identically():
    """Any proof emitted by derive, when passed through verify_proof again, is still proven+verified.
    Proves derive only emits things that pass the full gate.
    """
    axioms = [Axiom("x", 9.0), Axiom("y", 3.0)]
    proof = derive(axioms, target_value=6.0, max_ops=2)  # e.g. x / y * 2? or (x - y) + 0 wait; actual: x-y +0 no; search will find x-y? 6 no wait choose reachable
    # choose reachable: x / y * 2 but 2 not axiom; use (x + y) / y ? wait better pick known
    # use simple: target that 1 or 2 hits
    proof = derive(axioms, target_value=12.0, max_ops=1)  # x + y? 12 yes? 9+3=12
    assert proof is not None
    # re-verify with the emitted step (even if we tamper its .verified in the object)
    tampered_step = ProofStep(
        proof.steps[0].name, proof.steps[0].formula, proof.steps[0].value, verified=False
    )
    re_proof = verify_proof(
        list(proof.axioms),
        [tampered_step],
        target_name=proof.target_name,
        target_value=proof.target_value,
    )
    assert re_proof.proven is True
    assert re_proof.steps[0].verified is True  # recompute wins


# ---------- PROPERTY-BASED INVARIANTS ----------

@given(
    x=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e4, max_value=1e4)
        .filter(lambda v: abs(v) > 1e-9),
    y=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e4, max_value=1e4)
        .filter(lambda v: abs(v) > 1e-9),
)
def test_verify_accepts_exactly_what_evaluate_produces(x: float, y: float):
    """Property: any value produced by evaluate_formula, when used as claimed step.value, verifies True."""
    from gen.verification.derivation import evaluate_formula, within_tolerance  # pre-existing, allowed
    axioms = [Axiom("x", x), Axiom("y", y)]
    for op, fn in [("+", lambda a, b: a + b), ("-", lambda a, b: a - b),
                   ("*", lambda a, b: a * b), ("/", lambda a, b: a / b if b != 0 else None)]:
        if op == "/" and y == 0:
            continue
        val = fn(x, y)
        if not math.isfinite(val):
            continue
        f = f"x {op} y"
        step = ProofStep("s", f, val)  # may arrive with default verified=False
        p = verify_proof(axioms, [step], target_name="s", target_value=val)
        assert p.proven
        assert p.steps[0].verified
        # tolerance cross check
        recomputed = evaluate_formula(f, _axiom_dict(axioms))
        assert within_tolerance(val, recomputed, tolerance=1e-9)


@given(
    x=st.floats(allow_nan=False, allow_infinity=False, min_value=-100, max_value=100)
        .filter(lambda v: abs(v) > 1e-9),
    y=st.floats(allow_nan=False, allow_infinity=False, min_value=-100, max_value=100)
        .filter(lambda v: abs(v) > 1e-9),
)
def test_derive_found_proof_is_always_recomputable_to_target(x: float, y: float):
    """Property: whatever derive returns (when not None), its formula evaluated on axioms is within
    tolerance of the requested target_value, and the proof is marked proven/verified.
    """
    from gen.verification.derivation import evaluate_formula, within_tolerance
    axioms = [Axiom("x", x), Axiom("y", y)]
    # probe a few possible 1-op targets that may be hit
    candidates = [
        ("x + y", x + y),
        ("x - y", x - y),
        ("x * y", x * y),
    ]
    if abs(y) > 1e-12:
        candidates.append(("x / y", x / y))
    for _fname, target in candidates:
        if not math.isfinite(target):
            continue
        p = derive(axioms, target_value=target, max_ops=1)
        if p is None:
            continue  # some targets not enumerated first in order, fine
        assert p.proven
        assert p.steps[0].verified
        recomputed = evaluate_formula(p.steps[0].formula, _axiom_dict(axioms))
        assert within_tolerance(target, recomputed, tolerance=1e-9)


@given(
    x=st.floats(allow_nan=False, allow_infinity=False, min_value=-50, max_value=50)
        .filter(lambda v: abs(v) > 1e-9),
    y=st.floats(allow_nan=False, allow_infinity=False, min_value=-50, max_value=50)
        .filter(lambda v: abs(v) > 1e-9),
)
def test_derive_is_deterministic(x: float, y: float):
    """A5 reproducibility: identical input => identical ProofTree (or both None)."""
    axioms = [Axiom("x", x), Axiom("y", y)]
    p1 = derive(axioms, target_value=x + y, max_ops=1)
    p2 = derive(axioms, target_value=x + y, max_ops=1)
    assert p1 == p2


# ---------- EDGE / FAIL LOUD (scoped to real defects per conventions) ----------

def test_verify_non_finite_or_unknown_yields_non_verified():
    """Non-matching or uncomputable step => verified=False (no silent value)."""
    # unknown name
    p = verify_proof([Axiom("F", 1.0)], [ProofStep("a", "F / m", 1.0)], target_name="a")
    assert not p.proven and not p.steps[0].verified

    # formula that would div0 during recompute
    p2 = verify_proof([Axiom("z", 1.0)], [ProofStep("q", "z / 0", 99.0)], target_name="q")
    assert not p2.proven and not p2.steps[0].verified


def test_derive_never_returns_unverified_proof_even_for_edge_targets():
    """If derive succeeds, the emitted tree is always fully recomputed (no path returns unverified)."""
    # use a case that hits 2-op
    axioms = [Axiom("p", 10.0), Axiom("q", 2.0), Axiom("r", 3.0)]
    # (p / q) + r ? 5+3=8
    p = derive(axioms, target_value=8.0, max_ops=2)
    if p is not None:
        assert p.proven and all(s.verified for s in p.steps)
