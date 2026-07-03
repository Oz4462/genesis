"""Tests for the SMT (Z3) gate proof-of-concept (verification/smt.py).

Pins: a degenerate (point) box reproduces the closed-form yield verdict EXACTLY; a real box proves the
worst case; an unsafe box returns a counterexample that GENUINELY violates yield (the proof is sound,
not a guess) and lies inside the box; and z3-absence is an honest abstention. z3-using tests honest-
skip when z3-solver is not installed (README §7, like the cadquery/build123d-gated tests).
"""

import pytest

from gen.verification import smt
from gen.verification.smt import (
    HAVE_Z3,
    cantilever_stress,
    prove_cantilever_within_yield,
    prove_nonpositive,
)

needs_z3 = pytest.mark.skipif(not HAVE_Z3, reason="z3-solver not installed (honest-skip, README §7)")


@needs_z3
def test_point_proof_matches_closed_form_when_safe():
    F, L, b, h, sa = 100.0, 50.0, 10.0, 8.0, 600.0
    assert cantilever_stress(F, L, b, h) <= sa                       # closed-form: safe
    p = prove_cantilever_within_yield(force=F, arm=L, breadth=b, depth=h, sigma_allow=sa)
    assert p.available and p.proved                                  # SMT agrees: proved


@needs_z3
def test_point_proof_matches_closed_form_when_unsafe():
    F, L, b, h, sa = 100.0, 50.0, 10.0, 2.0, 600.0                   # σ = 6·100·50/(10·4) = 750 > 600
    assert cantilever_stress(F, L, b, h) > sa                        # closed-form: unsafe
    p = prove_cantilever_within_yield(force=F, arm=L, breadth=b, depth=h, sigma_allow=sa)
    assert p.available and not p.proved
    assert abs(p.counterexample["h"] - 2.0) < 1e-9                   # the degenerate box IS the point


@needs_z3
def test_universal_proof_over_a_box_holds_for_the_worst_case():
    # worst case = max F,L / min b,h: 6·100·50/(10·8·8) = 46.875 ≤ 600 -> proved for the WHOLE box.
    p = prove_cantilever_within_yield(
        force=(50.0, 100.0), arm=(20.0, 50.0), breadth=(10.0, 12.0), depth=(8.0, 10.0), sigma_allow=600.0
    )
    assert p.available and p.proved


@needs_z3
def test_unsafe_box_returns_a_genuinely_falsifying_counterexample():
    p = prove_cantilever_within_yield(
        force=(50.0, 100.0), arm=(20.0, 50.0), breadth=(10.0, 12.0), depth=(2.0, 3.0), sigma_allow=600.0
    )
    assert p.available and not p.proved
    ce = p.counterexample
    # soundness: the returned point really violates yield when plugged into the closed form...
    assert cantilever_stress(ce["F"], ce["L"], ce["b"], ce["h"]) > 600.0
    # ...and it lies inside the declared box (a real operating point, not an artefact).
    assert 50.0 <= ce["F"] <= 100.0 and 20.0 <= ce["L"] <= 50.0
    assert 10.0 <= ce["b"] <= 12.0 and 2.0 <= ce["h"] <= 3.0


@needs_z3
def test_prove_nonpositive_primitive():
    assert prove_nonpositive(lambda v: v["x"] - 1.0, {"x": (0.0, 1.0)}).proved     # x-1 ≤ 0 on [0,1]
    bad = prove_nonpositive(lambda v: v["x"] - 0.5, {"x": (0.0, 1.0)})             # x-0.5 ≤ 0 fails
    assert not bad.proved and bad.counterexample["x"] > 0.5


@needs_z3
def test_nonpositive_lower_bound_breadth_is_refused():
    p = prove_cantilever_within_yield(force=100.0, arm=50.0, breadth=0.0, depth=8.0, sigma_allow=600.0)
    assert not p.proved                                             # b ≤ 0 invalidates the rewrite


def test_honest_abstention_when_z3_absent(monkeypatch):
    # With z3 unavailable, the gate must abstain (available=False), never fabricate a verdict.
    monkeypatch.setattr(smt, "HAVE_Z3", False)
    p = smt.prove_nonpositive(lambda v: v["x"] - 1.0, {"x": (0.0, 1.0)})
    assert not p.available and not p.proved
