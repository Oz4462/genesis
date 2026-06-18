"""Universe Simulator Bridge — simulate -> discover -> gate; external backend is a declared seam."""

import math

import numpy as np
import pytest

from gen.discovery import (
    Variable, Constant, DiscoveryProblem,
    SimulationSpec, SimulationData, InProcessReferenceBackend,
    bridge_discover, should_offload,
)

MU_SUN = 1.32712440018e20


def test_bridge_simulates_a_two_body_orbit_then_rediscovers_kepler():
    """The whole-loop proof: the reference backend SIMULATES a two-body orbit, the engine
    DISCOVERS the law from the simulated data, and the GATE confirms Kepler's third law — the
    simulator's output is gated, not trusted."""
    a = tuple(np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11, 1.434e12]))
    spec = SimulationSpec(system="two_body_orbit", sweep=("a", "m", a),
                          observable=("T", "s"), params={"mu": (MU_SUN, "m^3/s^2")})
    res = bridge_discover(spec)
    assert res.verdict == "bestaetigt"
    assert "a^3/2" in res.discovered_law and "mu^-1/2" in res.discovered_law
    best = res.discovery.validated[0].candidate
    assert abs(best.coefficient - 2.0 * math.pi) / (2.0 * math.pi) < 1e-3
    assert res.data.backend == "in-process-reference"


def test_bridge_rediscovers_the_harmonic_oscillator():
    """A second reference system: mass-spring period T = 2π·m^(1/2)·k^(-1/2)."""
    m = tuple(np.array([0.5, 1.0, 1.5, 2.0, 2.5, 3.0]))
    spec = SimulationSpec(system="harmonic_oscillator", sweep=("m", "kg", m),
                          observable=("T", "s"), params={"k": (10.0, "N/m")})
    res = bridge_discover(spec)
    assert res.verdict == "bestaetigt"
    best = res.discovery.validated[0].candidate
    assert abs(best.exponents["m"] - 0.5) < 1e-3 and abs(best.exponents["k"] + 0.5) < 1e-3


def test_external_backend_is_a_declared_seam():
    """Any object implementing run(spec)->SimulationData plugs in behind the protocol — the
    bridge uses it, proving the external HPC engine is a drop-in, not a hidden dependency."""
    class FakeHpcBackend:
        name = "external-hpc-stub"

        def run(self, spec):
            a = np.array([1e11, 2e11, 3e11, 4e11, 5e11])
            T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
            problem = DiscoveryProblem(idea="extern simuliert", target=Variable("T", "s", tuple(T)),
                                       inputs=(Variable("a", "m", tuple(a)),),
                                       constants=(Constant("mu", MU_SUN, "m^3/s^2"),))
            return SimulationData(problem=problem, backend=self.name, note="stub")

    res = bridge_discover(SimulationSpec("two_body_orbit", ("a", "m", ()), ("T", "s")),
                          backend=FakeHpcBackend())
    assert res.data.backend == "external-hpc-stub"      # the seam was used
    assert res.verdict == "bestaetigt"


def test_offload_policy_is_size_based():
    big = SimulationSpec("two_body_orbit", ("a", "m", tuple(range(1, 20001))), ("T", "s"))
    small = SimulationSpec("two_body_orbit", ("a", "m", (1.0, 2.0, 3.0)), ("T", "s"))
    assert should_offload(big) is True
    assert should_offload(small) is False


def test_reference_backend_rejects_an_unknown_system():
    spec = SimulationSpec("warp_drive", ("x", "m", (1.0, 2.0)), ("y", "s"))
    with pytest.raises(ValueError):
        InProcessReferenceBackend().run(spec)


def test_bridge_is_deterministic():
    a = tuple(np.array([1e11, 2e11, 3e11, 4e11, 5e11]))
    spec = SimulationSpec("two_body_orbit", ("a", "m", a), ("T", "s"), {"mu": (MU_SUN, "m^3/s^2")})
    assert bridge_discover(spec).discovered_law == bridge_discover(spec).discovered_law
