"""Tests for the GENESIS-disciplined full GP search (Frontier 7, ``gp_search``).

The contract: the π-scaffold makes every GP genome dimensionless by construction (tree-level
dimensional typing), the Occam rival ladder (power law → power-of-π → multiterm → 6.3 → 6.6 →
6.7 → 6.8) collapses a GP claim onto any simpler family that is essentially exact, GP itself
NEVER confirms (its candidate goes through the gp_discover gates: δ-raised fit, dummy exclusion,
out-of-sample), noise is never confirmed, and a fixed seed reproduces the outcome exactly.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from gen.discovery.benchmark import (
    gp_noise_redteam_problem,
    kepler_case,
    pendulum_case,
    transcendental_sine_problem,
)
from gen.discovery.engine import Constant, DiscoveryProblem, Variable
from gen.discovery.gp_search import (
    DEFAULT_RUNGS,
    build_pi_scaffold,
    gp_occam_discover,
)
from gen.discovery.symbolic_search import GPConfig

# small but convergent search — deterministic seeds keep the suite fast (CLAUDE.md Prinzip 5)
CFG = GPConfig(population=200, generations=60, max_depth=3, parsimony=2e-3)

# the cheap front of the ladder (no scipy pair enumerations) for tests whose point is the GP
# discipline itself; the ONE full-ladder acceptance test below runs every rung.
CHEAP_RUNGS = ("power_law", "power_of_pi", "multiterm", "transzendent")


def _lorentz_problem() -> DiscoveryProblem:
    """Lorentz-type response y = a·π/(1+π²) with π = x/b — a RATIONAL law outside every 6.x
    family (algebraic peak + algebraic tails; measured at build time: all six rungs < 0.999)."""
    a_val, b_val = 3.0, 2.0
    x = np.geomspace(0.05, 200.0, 14) * b_val
    pi = x / b_val
    y = a_val * pi / (1.0 + pi**2)
    return DiscoveryProblem(
        idea="Resonanzartige Antwort (rational, kein 6.x-Fall).",
        target=Variable("y", "m", tuple(y)),
        inputs=(Variable("x", "s", tuple(x)),),
        constants=(Constant("a", a_val, "m"), Constant("b", b_val, "s")))


# --- (a) Rediscovery of the classics through the GP entry point ---------------------------

def test_kepler_rediscovery_collapses_to_confirmed_power_law():
    out = gp_occam_discover(kepler_case().problem, seed=0, cfg=CFG)
    assert out.verdict == "bestaetigt"
    assert out.form == "power_law" and out.occam_winner == "power_law"
    assert "a^3/2" in out.expression and "mu^-1/2" in out.expression
    # Occam short-circuit: no GP budget burned, no tree monster
    assert out.gp_verdict is None


def test_pendulum_rediscovery_collapses_to_confirmed_power_law():
    out = gp_occam_discover(pendulum_case().problem, seed=0, cfg=CFG)
    assert out.verdict == "bestaetigt" and out.form == "power_law"
    assert "L^1/2" in out.expression and "g^-1/2" in out.expression


# --- (b) a law OUTSIDE the 6.x families that only GP finds (full default ladder) ----------

def test_lorentzian_rational_law_only_gp_finds_it():
    out = gp_occam_discover(_lorentz_problem(), seed=5, cfg=CFG, rungs=DEFAULT_RUNGS)
    # every simpler family was tried and none is essentially exact
    assert tuple(r.name for r in out.rungs) == DEFAULT_RUNGS
    assert all(not r.equivalent for r in out.rungs)
    assert max(r.r_squared for r in out.rungs) < 0.999
    # GP wins — but only through the gates, never on fit alone
    assert out.verdict == "bestaetigt" and out.form == "gp"
    assert out.occam_winner is None
    assert out.gp_verdict is not None and out.gp_verdict.passed
    assert out.gp_verdict.dummy_excluded and out.gp_verdict.generalises
    assert out.r_squared > 0.999
    # the law is rendered over the dimensionless scaffold
    assert "pi1" in out.expression and "pi1 = x * b^-1" in out.expression


# --- (c) noise: NEVER a confirmed law (GP is the most overfit-prone search mode) ----------

@pytest.mark.parametrize("seed", [0, 1])
def test_noise_is_never_confirmed(seed):
    out = gp_occam_discover(gp_noise_redteam_problem(), seed=seed, cfg=CFG, rungs=CHEAP_RUNGS)
    assert out.verdict != "bestaetigt"
    assert out.occam_winner is None
    assert all(not r.equivalent for r in out.rungs)
    # the out-of-sample gate is what catches the in-sample noise fit
    assert out.gp_verdict is not None and not out.gp_verdict.generalises


# --- (d) determinism: same seed → byte-identical outcome (Prinzip 5) -----------------------

def test_same_seed_reproduces_outcome_exactly():
    a = gp_occam_discover(_lorentz_problem(), seed=5, cfg=CFG, rungs=CHEAP_RUNGS)
    b = gp_occam_discover(_lorentz_problem(), seed=5, cfg=CFG, rungs=CHEAP_RUNGS)
    assert a.expression == b.expression
    assert a.r_squared == b.r_squared  # exact float equality — a fixed seed must reproduce
    assert a.verdict == b.verdict and a.form == b.form


# --- (e) Occam: a power-law dataset collapses onto the power form, no tree monster --------

def test_dimensionless_power_law_collapses_to_power_of_pi():
    x = np.linspace(0.5, 4.0, 10)
    prob = DiscoveryProblem(
        idea="Reines Potenzgesetz (dimensionslos).",
        target=Variable("y", "1", tuple(4.0 * x**2)),
        inputs=(Variable("x", "1", tuple(x)),))
    out = gp_occam_discover(prob, seed=0, cfg=CFG, rungs=CHEAP_RUNGS)
    assert out.form == "power_of_pi" and out.occam_winner == "power_of_pi"
    assert out.verdict == "unentschieden"  # the simple family explains it; GP claims nothing
    assert out.gp_verdict is None          # Occam short-circuit: GP never ran
    assert out.r_squared >= 0.999


def test_additive_law_collapses_to_multiterm_family():
    # v = g·t + v0: the 6.1/6.2 additive family is exact and OOS-validated → GP defers
    g = 9.80665
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    prob = DiscoveryProblem(
        idea="Freier Fall mit Anfangsgeschwindigkeit.",
        target=Variable("v", "m/s", tuple(g * t + 40.0)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("g", g, "m/s^2"),))
    out = gp_occam_discover(prob, seed=0, cfg=CFG, rungs=CHEAP_RUNGS)
    assert out.form == "multiterm" and out.occam_winner == "multiterm"
    assert out.verdict == "unentschieden" and out.gp_verdict is None


def test_transcendental_law_collapses_to_6_3_family():
    out = gp_occam_discover(transcendental_sine_problem(), seed=0, cfg=CFG, rungs=CHEAP_RUNGS)
    assert out.form == "transzendent" and out.occam_winner == "transzendent"
    assert out.gp_verdict is None


# --- π-scaffold: tree-level dimensional discipline -----------------------------------------

def test_scaffold_determined_system_has_no_pi_groups():
    s = build_pi_scaffold(kepler_case().problem)
    assert s.reachable
    assert s.pi_groups == ()
    assert s.base_exponents["a"] == pytest.approx(1.5)
    assert s.base_exponents["mu"] == pytest.approx(-0.5)


def test_scaffold_picks_integer_unit_pi_group():
    s = build_pi_scaffold(_lorentz_problem())
    assert s.reachable
    assert len(s.pi_groups) == 1
    # the canonical, integer-preferring lattice pick: π1 = x/b (not x^0.5/b^0.5)
    assert s.pi_groups[0] == {"x": 1.0, "a": 0.0, "b": -1.0}
    assert s.base_exponents["a"] == pytest.approx(1.0)


def test_dimensionally_impossible_target_is_widerlegt():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    prob = DiscoveryProblem(
        idea="Temperatur aus Länge und Zeit (unmöglich).",
        target=Variable("Theta", "K", tuple(2.0 * x)),
        inputs=(Variable("a", "m", tuple(x)), Variable("t", "s", tuple(x))))
    out = gp_occam_discover(prob, seed=0, cfg=CFG, rungs=CHEAP_RUNGS)
    assert out.verdict == "widerlegt" and out.form == "keine"
    assert not build_pi_scaffold(prob).reachable


def test_determined_but_unconfirmed_is_honest_unentschieden():
    # v = g·t + v0 with the multiterm rung EXCLUDED: the dimensional system is determined, the
    # power law fails, and the open-form space beyond C·base is EMPTY → an honest "I don't know"
    g = 9.80665
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    prob = DiscoveryProblem(
        idea="Freier Fall mit Offset, reduzierte Leiter.",
        target=Variable("v", "m/s", tuple(g * t + 40.0)),
        inputs=(Variable("t", "s", tuple(t)),),
        constants=(Constant("g", g, "m/s^2"),))
    out = gp_occam_discover(prob, seed=0, cfg=CFG, rungs=("power_law",))
    assert out.verdict == "unentschieden" and out.form == "keine"
    assert out.gp_verdict is None


# --- negative tests -------------------------------------------------------------------------

def test_non_positive_data_raises():
    prob = DiscoveryProblem(
        idea="negativ",
        target=Variable("y", "1", (1.0, -2.0, 3.0)),
        inputs=(Variable("x", "1", (1.0, 2.0, 3.0)),))
    with pytest.raises(ValueError):
        gp_occam_discover(prob, seed=0, cfg=CFG, rungs=CHEAP_RUNGS)


def test_empty_target_raises():
    prob = DiscoveryProblem(
        idea="leer",
        target=Variable("y", "1", ()),
        inputs=(Variable("x", "1", ()),))
    with pytest.raises(ValueError):
        gp_occam_discover(prob, seed=0, cfg=CFG, rungs=CHEAP_RUNGS)


def test_unknown_rung_raises():
    with pytest.raises(ValueError):
        gp_occam_discover(_lorentz_problem(), seed=0, cfg=CFG, rungs=("power_law", "voodoo"))


def test_outcome_r2_is_finite_or_minus_inf_never_nan():
    out = gp_occam_discover(gp_noise_redteam_problem(), seed=0, cfg=CFG, rungs=CHEAP_RUNGS)
    assert not math.isnan(out.r_squared)
