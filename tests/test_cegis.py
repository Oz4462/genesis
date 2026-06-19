"""Tests for the CEGIS counterexample-guided refine loop (verification/cegis.py).

Pins: a counterexample drives a real repair to convergence (one-shot and stepwise), the loop makes
monotone progress (margins strictly shrink), a blocked repair returns converged=False with the
UNRESOLVED counterexample (never hidden), an already-passing candidate needs zero iterations, and the
loop composes with the SMT gate (#63) — the SMT worst-case point is the falsifying signal it refines
against. Offline, deterministic; the SMT-integration test honest-skips without z3.
"""

import pytest

from gen.verification.cegis import (
    Counterexample,
    cantilever_yield_check,
    increase_depth_repair,
    refine,
)
from gen.verification.smt import HAVE_Z3

_SA = 600.0
_INITIAL = {"F": 100.0, "L": 50.0, "b": 10.0, "h": 2.0}   # sigma = 6*100*50/(10*4) = 750 > 600 (fails)


def _check(design):
    return cantilever_yield_check(design, _SA)


def test_one_shot_repair_converges_in_one_iteration():
    res = refine(_INITIAL, _check, increase_depth_repair, max_iterations=4)
    assert res.converged and res.iterations == 1
    assert cantilever_yield_check(res.candidate, _SA) is None      # the final design passes the gate
    assert res.history[0][1].margin > 0.0                          # the recorded failure was real


def test_stepwise_repair_converges_with_monotone_progress():
    # a small 4% step on h reduces sigma by ~1/1.04^2 each round, so it takes SEVERAL iterations to
    # cross 600 from 750 -> exercises the loop, not a one-shot fix.
    res = refine(_INITIAL, _check, lambda d, ce: increase_depth_repair(d, ce, step=0.04), max_iterations=20)
    assert res.converged and res.iterations > 1                    # several steps, not one-shot
    margins = [ce.margin for _, ce in res.history]
    assert all(later < earlier for earlier, later in zip(margins, margins[1:]))  # strictly shrinking


def test_blocked_repair_returns_unresolved_counterexample():
    # a no-op repair can never fix the violation -> bounded loop reports it, never loops forever.
    res = refine(_INITIAL, _check, lambda d, ce: d, max_iterations=3)
    assert not res.converged and res.iterations == 3
    assert res.counterexample is not None and res.counterexample.margin > 0.0
    assert len(res.history) == 3


def test_already_passing_candidate_needs_zero_iterations():
    passing = {"F": 100.0, "L": 50.0, "b": 10.0, "h": 8.0}         # sigma = 46.875 < 600
    res = refine(passing, _check, increase_depth_repair, max_iterations=4)
    assert res.converged and res.iterations == 0 and res.history == ()


def test_counterexample_margin_is_signed_violation():
    assert Counterexample("bending_stress", 750.0, 600.0).margin == 150.0


def test_max_iterations_must_be_positive():
    with pytest.raises(ValueError):
        refine(_INITIAL, _check, increase_depth_repair, max_iterations=0)


@pytest.mark.skipif(not HAVE_Z3, reason="z3-solver not installed (honest-skip, README §7)")
def test_cegis_drives_the_smt_gate_to_a_machine_checked_proof():
    from gen.verification.smt import cantilever_stress, prove_cantilever_within_yield

    def check(d):
        proof = prove_cantilever_within_yield(
            force=d["F"], arm=d["L"], breadth=d["b"], depth=(d["h_lo"], d["h_hi"]), sigma_allow=_SA
        )
        if proof.proved:
            return None
        pt = proof.counterexample                                  # the SMT worst-case operating point
        worst = cantilever_stress(pt["F"], pt["L"], pt["b"], pt["h"])
        return Counterexample("worst_case_stress", worst, _SA, detail="SMT falsifying point")

    def repair(d, ce):
        nd = dict(d)
        nd["h_lo"] = d["h_lo"] * 1.25                              # deepen the thinnest allowed section
        nd["h_hi"] = max(d["h_hi"], nd["h_lo"])
        return nd

    initial = {"F": 100.0, "L": 50.0, "b": 10.0, "h_lo": 2.0, "h_hi": 4.0}  # worst case 750 > 600
    res = refine(initial, check, repair, max_iterations=12)
    assert res.converged
    final = prove_cantilever_within_yield(
        force=res.candidate["F"], arm=res.candidate["L"], breadth=res.candidate["b"],
        depth=(res.candidate["h_lo"], res.candidate["h_hi"]), sigma_allow=_SA,
    )
    assert final.proved                                           # the refined design is machine-checked
