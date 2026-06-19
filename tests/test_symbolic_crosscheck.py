"""Tests for the independent SymPy dimensional cross-check (verification/symbolic.py).

Pins the THIRD, disjoint dimensional engine against the same benchmark laws the discovery arm
rediscovers (Kepler/gas/pendulum): SymPy must independently confirm the power-law dimensions, recover
the exact constant (2·π), catch a dimension-broken candidate, and ABSTAIN honestly (not guess) on an
opaque unit. Offline, deterministic, no network.
"""

import math
from fractions import Fraction

from gen.verification.symbolic import (
    SymbolicDimensionCheck,
    cross_check_power_law,
    cross_engine_dimension_agrees,
    recover_exact_constant,
    sympy_base_exponents,
)


def test_kepler_power_law_crosschecks_and_recovers_2pi():
    # T = 2π · a^(3/2) · mu^(-1/2), a [m], mu = G·M [m^3/s^2], T [s].
    r = cross_check_power_law("s", {"a": "m", "mu": "m^3/s^2"}, {"a": 1.5, "mu": -0.5})
    assert r.available and r.agrees
    assert r.candidate == {"time": 1}                     # SymPy independently reduces to pure time
    assert recover_exact_constant(2.0 * math.pi) == "2*pi"


def test_ideal_gas_power_law_crosschecks():
    # P = R·n·T·V^(-1): J/(mol·K) · mol · K / m^3 -> pressure, fully independently of units.py.
    r = cross_check_power_law(
        "Pa",
        {"R": "J/mol/K", "n": "mol", "Temp": "K", "V": "m^3"},
        {"R": 1.0, "n": 1.0, "Temp": 1.0, "V": -1.0},
    )
    assert r.available and r.agrees
    assert r.candidate == {"mass": 1, "length": -1, "time": -2}   # = pressure


def test_pendulum_power_law_crosschecks():
    # T = 2π · L^(1/2) · g^(-1/2), L [m], g [m/s^2], T [s].
    r = cross_check_power_law("s", {"L": "m", "g": "m/s^2"}, {"L": 0.5, "g": -0.5})
    assert r.available and r.agrees
    assert recover_exact_constant(2.0 * math.pi) == "2*pi"


def test_dimension_broken_candidate_is_caught():
    # Wrong exponent on a (1.0 instead of 1.5) leaves a stray length^(-1/2) — must NOT agree.
    r = cross_check_power_law("s", {"a": "m", "mu": "m^3/s^2"}, {"a": 1.0, "mu": -0.5})
    assert r.available and not r.agrees
    assert r.candidate.get("length") == Fraction(-1, 2)   # the exact half-integer residual is exposed
    assert r.candidate.get("time") == 1


def test_opaque_unit_is_honest_abstention_not_a_guess():
    # An unknown atom must yield available=False (cannot corroborate), never a fabricated pass/fail.
    r = cross_check_power_law("s", {"a": "widget", "mu": "m^3/s^2"}, {"a": 1.5, "mu": -0.5})
    assert isinstance(r, SymbolicDimensionCheck)
    assert not r.available and not r.agrees


def test_cross_engine_agreement_on_known_units():
    # SymPy and units.py reduce the SAME compound units to the SAME base dimensions.
    assert cross_engine_dimension_agrees("Pa") is True
    assert cross_engine_dimension_agrees("kg*m/s^2") is True      # = N (force)
    assert cross_engine_dimension_agrees("m/s^2") is True
    assert cross_engine_dimension_agrees("J/mol/K") is True


def test_cross_engine_returns_none_on_opaque_atom():
    assert cross_engine_dimension_agrees("widget") is None        # nothing to cross-check -> honest None


def test_sympy_base_exponents_independent_reduction():
    assert sympy_base_exponents("Pa") == {"mass": 1, "length": -1, "time": -2}
    assert sympy_base_exponents("m/s^2") == {"length": 1, "time": -2}
    assert sympy_base_exponents("m^3") == {"length": 3}
    assert sympy_base_exponents("widget") is None                 # opaque -> None, never a guess


def test_corroboration_flows_through_the_discovery_engine():
    # End-to-end: rediscovering Kepler through the real engine must carry the SymPy corroboration,
    # i.e. two independent dimensional engines agreed before the law was accepted.
    from gen.discovery.benchmark import kepler_case
    from gen.discovery.engine import discover_new_formulas

    res = discover_new_formulas(kepler_case().problem)
    assert res.validated                                   # Kepler is rediscovered
    best = res.validated[0].candidate
    assert best.dimension_ok
    assert best.dimension_corroborated is True             # SymPy independently corroborated the dims


def test_recover_exact_constant_is_conservative():
    assert recover_exact_constant(2.0 * math.pi) == "2*pi"
    assert recover_exact_constant(math.pi) == "pi"
    assert recover_exact_constant(0.5) == "1/2"
    # An empirical constant (gas constant R) has no simple closed form -> stays numeric (None).
    assert recover_exact_constant(8.314462618) is None
    assert recover_exact_constant(1.23987) is None
    assert recover_exact_constant(0.0) is None
