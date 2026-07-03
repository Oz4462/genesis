"""SimulatorBackend seam (simulation/backends.py): pluggable physics simulators behind one interface.

Pins the offline-first / external-opt-in discipline: the in-house RK4 backend is the deterministic default
and feeds SINDy a clean trajectory it recovers the ODE from; the external MuJoCo adapter is import-guarded
and SKIPS cleanly (raises SimulatorUnavailable) when the tool is absent — never a fabricated trajectory.
Offline, deterministic.
"""

import pytest

from gen.discovery.sindy import discover_ode
from gen.simulation.backends import (
    MujocoPendulumBackend, MultibodyPendulumBackend, PendulumSpec,
    SimulatorBackend, SimulatorUnavailable, default_backend,
)
from gen.simulation.multibody import STANDARD_GRAVITY

_M, _D, _C = 2.0, 0.18, 0.2
_I = _M * _D * _D
_SPEC = PendulumSpec(theta0=0.8, inertia=_I, mass=_M, com_distance=_D, damping=_C, duration=12.0, dt=0.004)
_TRUE_SIN = -(_M * STANDARD_GRAVITY * _D) / _I


def test_offline_backend_satisfies_the_protocol_and_is_the_default():
    be = MultibodyPendulumBackend()
    assert isinstance(be, SimulatorBackend)
    assert default_backend().name == "multibody"


def test_offline_backend_feeds_sindy_a_recoverable_trajectory():
    traj = MultibodyPendulumBackend().simulate(_SPEC)
    assert len(traj.t) > 1000
    model = discover_ode(traj, threshold=0.5)
    assert set(model.coefficients) == {"theta_dot", "sin(theta)"}      # the seam's data recovers the ODE
    assert model.r_squared > 0.999
    assert abs(model.coefficients["sin(theta)"] - _TRUE_SIN) < abs(_TRUE_SIN) * 0.01


def test_external_mujoco_adapter_skips_cleanly_without_the_tool():
    mj = MujocoPendulumBackend()
    assert isinstance(mj, SimulatorBackend)
    if mj.available():                       # if mujoco IS installed, the live path must produce a trajectory
        traj = mj.simulate(_SPEC)
        assert len(traj.t) > 1000
    else:                                    # the tested contract here: a clean, honest skip — never a fake
        with pytest.raises(SimulatorUnavailable):
            mj.simulate(_SPEC)


def test_spec_rejects_nonpositive_physical_quantities():
    with pytest.raises(ValueError):
        PendulumSpec(theta0=0.8, inertia=-1.0, mass=_M, com_distance=_D)
    with pytest.raises(ValueError):
        PendulumSpec(theta0=0.8, inertia=_I, mass=_M, com_distance=_D, duration=0.0)


def test_backend_is_deterministic():
    a = MultibodyPendulumBackend().simulate(_SPEC)
    b = MultibodyPendulumBackend().simulate(_SPEC)
    assert a.theta == b.theta and a.omega == b.omega
