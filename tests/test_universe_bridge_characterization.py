"""Characterization / facade-detector for ``discovery.universe_bridge``.

The headline claim under audit: the Universe Simulator Bridge SIMULATEs a system with the
in-process reference backend and then brings the result BACK THROUGH THE GATES — the simulated
data is run through ``discover_new_formulas`` and ONLY a gate-confirmed law is reported. The
simulator's output is never trusted; it is gated like real-world data.

These tests FAIL if the bridge is a hollow facade — i.e. if it returns a canned law that ignores
its input, skips the gate, or does not genuinely rediscover the physics from the simulated data.
They assert the claim REALLY holds on constructed specs driven through the real engine.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# src layout (pyproject: packages found under src/); match the repo's test convention of
# importing the package as ``gen.*`` rather than ``src.gen.*``.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.discovery.universe_bridge import (  # noqa: E402
    DEFAULT_MAX_LOCAL_POINTS,
    InProcessReferenceBackend,
    SimulationSpec,
    bridge_discover,
    should_offload,
)

# --- canonical specs ----------------------------------------------------------

#: Earth's standard gravitational parameter mu = G·M_earth [m^3/s^2]; the orbit period
#: T = 2π·a^(3/2)·mu^(-1/2) is Kepler's third law.
_MU_EARTH = 1.327e20


def _orbit_spec(sweep_vals: tuple[float, ...], mu: float = _MU_EARTH) -> SimulationSpec:
    return SimulationSpec(
        system="two_body_orbit",
        sweep=("a", "m", sweep_vals),
        observable=("T", "s"),
        params={"mu": (mu, "m^3/s^2")},
    )


def _oscillator_spec(masses: tuple[float, ...], k: float = 20.0) -> SimulationSpec:
    return SimulationSpec(
        system="harmonic_oscillator",
        sweep=("m", "kg", masses),
        observable=("T", "s"),
        params={"k": (k, "kg/s^2")},
    )


# --- 1. two_body_orbit rediscovers Kepler's third law THROUGH the gate --------

def test_two_body_orbit_rediscovers_kepler_third_law_and_passes_gate():
    """SIMULATE → DISCOVER → GATE: the orbit must come back as period ∝ a^1.5 with a
    ``bestaetigt`` verdict and a non-None discovered law — proving the simulated data passed
    the dimensional + recompute + fit gates, not merely echoed by the backend."""
    result = bridge_discover(_orbit_spec((1e9, 2e9, 3e9, 4e9, 5e9, 6e9)))

    assert result.verdict == "bestaetigt"
    assert result.discovered_law is not None
    # the discovered law is gate-confirmed (validated, not just recorded)
    assert result.discovery.validated, "a bestaetigt verdict must populate validated[]"
    best = result.discovery.validated[0]
    assert best.verdict == "bestaetigt"
    assert best.passed is True
    # Kepler's third law: T ∝ a^(3/2)·mu^(-1/2)
    assert best.candidate.exponents["a"] == pytest.approx(1.5, abs=1e-6)
    assert best.candidate.exponents["mu"] == pytest.approx(-0.5, abs=1e-6)
    # the fitted dimensionless constant is 2π (the closed form), recovered from data
    assert best.candidate.coefficient == pytest.approx(2.0 * math.pi, rel=1e-6)
    # provenance: the backend that produced the gated data is recorded
    assert result.data.backend == "in-process-reference"


# --- 2. harmonic_oscillator recovers the correct exponent ---------------------

def test_harmonic_oscillator_recovers_half_power_exponent():
    """A mass-spring period T = 2π·m^(1/2)·k^(-1/2): the bridge must recover the +1/2 mass
    exponent (and -1/2 on k) and confirm it through the gate."""
    result = bridge_discover(_oscillator_spec((0.1, 0.2, 0.5, 1.0, 2.0, 5.0)))

    assert result.verdict == "bestaetigt"
    assert result.discovered_law is not None
    best = result.discovery.validated[0]
    assert best.candidate.exponents["m"] == pytest.approx(0.5, abs=1e-6)
    assert best.candidate.exponents["k"] == pytest.approx(-0.5, abs=1e-6)
    assert best.candidate.coefficient == pytest.approx(2.0 * math.pi, rel=1e-6)


# --- 3. the input is genuinely CONSUMED, not canned ---------------------------

def test_simulated_observable_is_driven_by_the_sweep_not_canned():
    """The backend must compute the observable FROM the sweep — a canned facade would return a
    fixed array. We pin the simulated period array against the independent closed form and show
    a different sweep yields a different (still-correct) array."""
    spec = _orbit_spec((1e9, 2e9, 3e9))
    data = InProcessReferenceBackend().run(spec)
    a = np.array([1e9, 2e9, 3e9])
    expected = 2.0 * math.pi * a ** 1.5 / math.sqrt(_MU_EARTH)
    assert np.allclose(np.array(data.problem.target.values), expected)

    other = InProcessReferenceBackend().run(_orbit_spec((7e9, 8e9, 9e9)))
    assert not np.allclose(
        np.array(data.problem.target.values), np.array(other.problem.target.values)
    ), "different sweep values must produce different simulated periods"


def test_changing_params_changes_the_simulated_numbers():
    """``params`` (the system constants) must genuinely drive the simulation: a larger mu
    shrinks every orbital period by sqrt(mu_lo/mu_hi). A canned backend ignoring params would
    return identical arrays."""
    sweep = (1e9, 2e9, 3e9)
    lo = bridge_discover(_orbit_spec(sweep, mu=1.0e20))
    hi = bridge_discover(_orbit_spec(sweep, mu=4.0e20))

    y_lo = np.array(lo.data.problem.target.values)
    y_hi = np.array(hi.data.problem.target.values)
    assert not np.allclose(y_lo, y_hi), "changing mu must change the simulated periods"
    # T ∝ mu^(-1/2): doubling sqrt(mu) (4x mu) halves the period, exactly
    assert np.allclose(y_hi, y_lo * math.sqrt(1.0e20 / 4.0e20))
    # both still rediscover the same law (mu is a source variable, exponent fixed by dimension)
    assert lo.verdict == hi.verdict == "bestaetigt"


def test_different_systems_yield_different_discovered_exponents():
    """The discovered numbers track the SYSTEM, not a canned constant: an orbit and an
    oscillator must yield different exponent signatures."""
    orbit = bridge_discover(_orbit_spec((1e9, 2e9, 3e9, 4e9)))
    osc = bridge_discover(_oscillator_spec((0.1, 0.2, 0.5, 1.0)))
    assert orbit.discovery.validated[0].candidate.exponents != \
        osc.discovery.validated[0].candidate.exponents


# --- 4. negative: an unknown system fails loudly ------------------------------

def test_unknown_system_raises_value_error():
    """A system the reference backend cannot simulate must fail loudly (no fabricated data) —
    the no-silent-defaults principle."""
    spec = SimulationSpec(
        system="warp_drive",
        sweep=("x", "m", (1.0, 2.0, 3.0)),
        observable=("y", "s"),
        params={},
    )
    with pytest.raises(ValueError, match="cannot simulate"):
        bridge_discover(spec)


# --- 5. should_offload boundary ----------------------------------------------

def test_should_offload_boundary():
    """The local-vs-offloaded decision: at or below the cap stay local (False), strictly above
    it offload (True)."""
    cap = 5
    at_cap = _orbit_spec(tuple(float(i) * 1e9 for i in range(1, cap + 1)))  # len == cap
    over_cap = _orbit_spec(tuple(float(i) * 1e9 for i in range(1, cap + 2)))  # len == cap + 1
    assert should_offload(at_cap, max_local_points=cap) is False
    assert should_offload(over_cap, max_local_points=cap) is True


def test_should_offload_default_cap():
    """Sanity-check the documented default cap boundary without materialising 10k+ points by
    using the exposed constant for the small side and a synthetic over-cap spec."""
    small = _orbit_spec((1e9, 2e9, 3e9))
    assert should_offload(small) is False
    # one point past the default cap must offload
    over = SimulationSpec(
        system="two_body_orbit",
        sweep=("a", "m", tuple(float(i) for i in range(DEFAULT_MAX_LOCAL_POINTS + 1))),
        observable=("T", "s"),
        params={"mu": (_MU_EARTH, "m^3/s^2")},
    )
    assert should_offload(over) is True


# --- 6. property-based invariant: Kepler exponent is recovered for any orbit --

@settings(deadline=None, max_examples=30)
@given(
    a0=st.floats(min_value=1e8, max_value=1e10),
    step=st.floats(min_value=1e8, max_value=5e9),
    mu=st.floats(min_value=1e18, max_value=1e21),
)
def test_kepler_exponent_is_an_invariant(a0: float, step: float, mu: float):
    """INVARIANT: regardless of the sweep range or mu, the dimensional solve must fix the
    semi-major-axis exponent at exactly 3/2 and confirm the law — because the exponents come
    from dimensional analysis, not from fitting noise. A facade returning a canned law for one
    example would not hold across the input space."""
    sweep = tuple(a0 + step * i for i in range(6))
    result = bridge_discover(_orbit_spec(sweep, mu=mu))
    assert result.verdict == "bestaetigt"
    best = result.discovery.validated[0]
    assert best.candidate.exponents["a"] == pytest.approx(1.5, abs=1e-6)
    assert best.candidate.exponents["mu"] == pytest.approx(-0.5, abs=1e-6)
