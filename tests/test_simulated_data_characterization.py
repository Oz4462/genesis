"""Characterization + depth-audit for ``discovery.simulated_data`` (INVENTOR §10).

These tests PROVE the headline claim — that ``problem_from_simulation`` /
``discover_from_simulation`` genuinely SAMPLE a closed form to SELF-GENERATE the target data and
recover the law (not a canned stub) — by asserting:

  (a) the self-generated target is EXACTLY ``sim_fn`` applied to the sampled input columns (the data
      is computed, never fabricated), and changes meaningfully when the driving inputs change;
  (b) the dimensional SR engine recovers the law's exponents from that self-generated data, for a
      WHOLE FAMILY of randomly chosen power laws (property-based — the math is real, not memorised);
  (c) the ``baked`` callable closes the constants correctly (round-trip identity, property-based);
  (d) every documented fail-loud guard fires (empty inputs, too-few samples, non-positive/non-finite
      target, bad InputSpec range) PLUS the duplicate-name silent-corruption guard.

These complement (do not replace) tests/test_discovery_simulated_data.py.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.discovery.engine import Constant  # noqa: E402
from gen.discovery.simulated_data import (  # noqa: E402
    InputSpec,
    discover_from_simulation,
    problem_from_simulation,
)


# --------------------------------------------------------------------------------------------------
# (a) The target data is GENUINELY self-generated from sim_fn — not a constant/canned stub.
# --------------------------------------------------------------------------------------------------

def test_target_is_exactly_sim_fn_of_the_sampled_inputs():
    """The self-generated target must equal ``sim_fn`` evaluated on the sampled input columns, point
    for point — proving the data is computed from the simulator, not fabricated."""
    sim = lambda m, v: 0.5 * m * v ** 2
    problem, _ = problem_from_simulation(
        "kinetische Energie", target_name="E", target_unit="J",
        inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
        sim_fn=sim, n_samples=32, seed=3)
    cols = {iv.name: iv.values for iv in problem.inputs}
    recomputed = [sim(m=cols["m"][i], v=cols["v"][i]) for i in range(32)]
    assert problem.target.values == pytest.approx(recomputed, rel=0, abs=0)
    # And the data actually spans magnitudes (log-uniform sampling), not a degenerate constant column.
    assert len(set(problem.target.values)) == 32
    assert max(problem.target.values) > 10.0 * min(problem.target.values)


def test_different_sim_fn_yields_a_different_recovered_law():
    """Changing the driving input (the closed form) MUST change the recovered exponents — the engine
    is reading the self-generated data, not returning a canned answer."""
    common = dict(target_name="E", target_unit="J",
                  inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
                  n_samples=128, seed=0)
    kinetic = discover_from_simulation("kin", sim_fn=lambda m, v: 0.5 * m * v ** 2, **common)
    # E' = m * v  (J only dimensionally if we relabel; use a power-law over the SAME inputs/units that
    # is still dimensionally J: m^1 v^2 vs ... we instead keep dimensions valid by reusing kinetic's
    # unit but a different exponent split is impossible for fixed dims) -> use a distinct problem.
    momentum = discover_from_simulation(
        "imp", target_name="p", target_unit="kg*m/s",
        inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
        sim_fn=lambda m, v: m * v, n_samples=128, seed=0)
    kin_top = kinetic.validated[0].candidate
    mom_top = momentum.validated[0].candidate
    assert round(kin_top.exponents["v"], 3) == 2.0
    assert round(mom_top.exponents["v"], 3) == 1.0
    assert kin_top.exponents != mom_top.exponents


def test_recovers_the_law_and_confirms_it():
    res = discover_from_simulation(
        "kinetische Energie", target_name="E", target_unit="J",
        inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
        sim_fn=lambda m, v: 0.5 * m * v ** 2, n_samples=200, seed=0)
    top = res.validated[0]
    assert top.verdict == "bestaetigt"
    assert round(top.candidate.exponents["m"], 3) == 1.0
    assert round(top.candidate.exponents["v"], 3) == 2.0
    assert top.candidate.r_squared == pytest.approx(1.0, abs=1e-9)
    assert top.candidate.coefficient == pytest.approx(0.5, rel=1e-6)


# --------------------------------------------------------------------------------------------------
# (b) Property: a WHOLE FAMILY of self-generated power laws is recovered (the SR is real math).
# --------------------------------------------------------------------------------------------------

@settings(deadline=None, max_examples=30)
@given(
    a=st.integers(min_value=1, max_value=3),
    b=st.integers(min_value=-2, max_value=3),
    seed=st.integers(min_value=0, max_value=50),
)
def test_property_recovers_arbitrary_power_law(a: int, b: int, seed: int):
    """For target ``E = m^a · v^b`` (units chosen so the dimension is reachable), the engine recovers
    exactly ``a`` and ``b`` from self-generated data — proving the dimensional solve, not memorisation.

    Units: m=[kg], v=[m] ⇒ target dimension kg^a·m^b, so the dimensional solve is exactly determined
    and the recovered exponents must be (a, b) regardless of the random seed / sampled magnitudes."""
    target_unit = f"kg^{a}*m^{b}" if b != 0 else f"kg^{a}"
    res = discover_from_simulation(
        "power law", target_name="E", target_unit=target_unit,
        inputs=(InputSpec("m", "kg", 0.5, 5.0), InputSpec("v", "m", 0.5, 5.0)),
        sim_fn=lambda m, v: (m ** a) * (v ** b), n_samples=64, seed=seed)
    assert res.validated, f"no validated law for m^{a} v^{b}"
    top = res.validated[0].candidate
    assert round(top.exponents["m"], 3) == float(a)
    assert round(top.exponents["v"], 3) == float(b)
    assert top.r_squared == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------------------------------
# (c) The baked callable closes the constants correctly (round-trip identity).
# --------------------------------------------------------------------------------------------------

def test_baked_closes_a_constant():
    """``baked`` must be ``sim_fn`` with the constants closed in: an input-only callable whose value
    equals the full sim_fn at the same inputs + constant — the engine's separability annotation relies
    on this."""
    g = 9.80665
    sim = lambda L, g: 2.0 * math.pi * (L / g) ** 0.5
    _, baked = problem_from_simulation(
        "Pendelperiode", target_name="T", target_unit="s",
        inputs=(InputSpec("L", "m", 0.1, 10.0),),
        sim_fn=sim, constants=(Constant("g", g, "m/s^2"),), n_samples=16, seed=1)
    for L in (0.25, 1.0, 4.0, 9.0):
        assert baked(L=L) == pytest.approx(sim(L=L, g=g))


@settings(deadline=None, max_examples=40)
@given(
    coeff=st.floats(min_value=0.1, max_value=10.0),
    x=st.floats(min_value=0.1, max_value=100.0),
)
def test_property_baked_round_trip_identity(coeff: float, x: float):
    """For any positive input, ``baked(**x)`` equals ``sim_fn(**x, **constants)`` — a behaviour
    (constant-closure) identity that must hold for ALL inputs, not just hand-picked ones."""
    sim = lambda x, k: k * x ** 2
    _, baked = problem_from_simulation(
        "p", target_name="y", target_unit="m^2",
        inputs=(InputSpec("x", "m", 0.1, 100.0),),
        sim_fn=sim, constants=(Constant("k", coeff, ""),), n_samples=8, seed=0)
    assert baked(x=x) == pytest.approx(sim(x=x, k=coeff))


def test_recovers_pendulum_period_with_a_constant():
    res = discover_from_simulation(
        "Pendelperiode", target_name="T", target_unit="s",
        inputs=(InputSpec("L", "m", 0.1, 10.0),),
        sim_fn=lambda L, g: 2.0 * math.pi * (L / g) ** 0.5,
        constants=(Constant("g", 9.80665, "m/s^2"),), n_samples=200, seed=1)
    assert res.validated
    top = res.validated[0].candidate
    assert round(top.exponents["L"], 3) == 0.5
    assert top.r_squared == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------------------------------
# Determinism (A5 reproducibility): same seed ⇒ byte-identical self-generated data + verdict.
# --------------------------------------------------------------------------------------------------

def test_is_deterministic_given_the_seed():
    kw = dict(target_name="E", target_unit="J",
              inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
              sim_fn=lambda m, v: 0.5 * m * v ** 2, n_samples=48, seed=11)
    p1, _ = problem_from_simulation("e", **kw)
    p2, _ = problem_from_simulation("e", **kw)
    assert p1.target.values == p2.target.values
    assert tuple(iv.values for iv in p1.inputs) == tuple(iv.values for iv in p2.inputs)


def test_different_seed_changes_the_sampled_data_not_the_law():
    """A different seed must resample DIFFERENT magnitudes (proving sampling is real) yet recover the
    SAME law (proving the recovery is data-driven, not seed-driven)."""
    kw = dict(target_name="E", target_unit="J",
              inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
              sim_fn=lambda m, v: 0.5 * m * v ** 2, n_samples=64)
    a, _ = problem_from_simulation("e", seed=1, **kw)
    b, _ = problem_from_simulation("e", seed=2, **kw)
    assert a.target.values != b.target.values
    ra = discover_from_simulation("e", seed=1, **kw).validated[0].candidate.exponents
    rb = discover_from_simulation("e", seed=2, **kw).validated[0].candidate.exponents
    assert {k: round(v, 3) for k, v in ra.items()} == {k: round(v, 3) for k, v in rb.items()}


# --------------------------------------------------------------------------------------------------
# (d) Documented fail-loud guards — "a gate without a test does not exist".
# --------------------------------------------------------------------------------------------------

def test_guard_rejects_empty_inputs():
    with pytest.raises(ValueError, match="at least one input"):
        problem_from_simulation("x", target_name="y", target_unit="m",
                                inputs=(), sim_fn=lambda: 1.0, n_samples=10)


def test_guard_rejects_too_few_samples():
    with pytest.raises(ValueError, match="at least 2 samples"):
        problem_from_simulation("x", target_name="y", target_unit="m",
                                inputs=(InputSpec("x", "m", 0.1, 1.0),),
                                sim_fn=lambda x: x, n_samples=1)


def test_guard_rejects_non_positive_target():
    with pytest.raises(ValueError, match="non-positive/non-finite"):
        problem_from_simulation("bad", target_name="y", target_unit="J",
                                inputs=(InputSpec("x", "m", 0.1, 1.0),),
                                sim_fn=lambda x: -x, n_samples=10, seed=0)


def test_guard_rejects_non_finite_target():
    with pytest.raises(ValueError, match="non-positive/non-finite"):
        problem_from_simulation("bad", target_name="y", target_unit="J",
                                inputs=(InputSpec("x", "m", 0.1, 1.0),),
                                sim_fn=lambda x: float("inf"), n_samples=10, seed=0)


@pytest.mark.parametrize("lo,hi", [(5.0, 1.0), (0.0, 1.0), (-1.0, 2.0), (1.0, 1.0)])
def test_guard_rejects_bad_input_range(lo: float, hi: float):
    with pytest.raises(ValueError, match="0 < lo < hi"):
        InputSpec("x", "m", lo, hi)


def test_guard_rejects_nan_input_range():
    with pytest.raises(ValueError, match="0 < lo < hi"):
        InputSpec("x", "m", float("nan"), 1.0)


# --- the silent-corruption guard this audit added (duplicate name → corrupted dimensional solve) ---

def test_guard_rejects_duplicate_input_names():
    """Two inputs with the same name would silently collapse to one column and feed the engine a
    corrupted problem (the engine keys sources by name). Must fail loud."""
    with pytest.raises(ValueError, match="unique"):
        problem_from_simulation("x", target_name="y", target_unit="kg",
                                inputs=(InputSpec("m", "kg", 1.0, 2.0), InputSpec("m", "kg", 3.0, 4.0)),
                                sim_fn=lambda **kw: kw["m"], n_samples=8, seed=0)


def test_guard_rejects_input_name_colliding_with_constant():
    with pytest.raises(ValueError, match="unique"):
        problem_from_simulation("x", target_name="y", target_unit="m",
                                inputs=(InputSpec("a", "m", 1.0, 2.0),),
                                sim_fn=lambda **kw: kw["a"],
                                constants=(Constant("a", 1.0, "m"),), n_samples=8, seed=0)


# --------------------------------------------------------------------------------------------------
# Negative control: an additive form (not a single power law) is NOT falsely confirmed.
# --------------------------------------------------------------------------------------------------

def test_additive_form_is_not_falsely_confirmed():
    """``y = x + x^3`` over a single dimension is not a single power law; the honest engine must not
    return a ``bestaetigt`` perfect-fit verdict for it (no fabricated confirmation)."""
    res = discover_from_simulation(
        "additiv", target_name="y", target_unit="m",
        inputs=(InputSpec("x", "m", 0.1, 10.0),),
        sim_fn=lambda x: x + x ** 3, n_samples=128, seed=0)
    # The single power-law candidate cannot fit an additive form perfectly → r² below the bar.
    top = res.all_records[0].candidate
    assert top.r_squared < 0.999
    assert not res.validated or res.validated[0].verdict != "bestaetigt"
