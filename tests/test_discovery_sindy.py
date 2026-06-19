"""SINDy ODE discovery (discovery/sindy.py) from a GENESIS simulator trajectory.

Pins the categorical jump beyond a single power law: from a CLEAN RK4 pendulum trajectory, sparse
identification recovers the EXACT second-order ODE the simulator integrates — only the two terms the
dynamics need — and a planted dummy feature is thresholded out (the SINDy-hygiene property). Pure numpy,
offline, deterministic.
"""

import numpy as np

from gen.discovery.sindy import discover_ode, stlsq
from gen.simulation.multibody import STANDARD_GRAVITY, simulate_pendulum

# damped driven pendulum: I·θ̈ = −c·ω − m·g·d·sinθ  →  θ̈ = −(c/I)·θ̇ − (m·g·d/I)·sin θ
_M, _D, _C = 2.0, 0.18, 0.2
_I = _M * _D * _D
_TRUE_SIN = -(_M * STANDARD_GRAVITY * _D) / _I       # ≈ -54.48
_TRUE_DOT = -_C / _I                                  # ≈ -3.086


def _traj():
    return simulate_pendulum(0.8, 0.0, lambda t, th, om: -_C * om,
                             inertia=_I, mass=_M, com_distance=_D, duration=12.0, dt=0.004)


def test_recovers_the_exact_damped_pendulum_ode():
    model = discover_ode(_traj(), threshold=0.5)
    assert set(model.coefficients) == {"theta_dot", "sin(theta)"}     # only the two real terms
    assert model.n_active == 2
    assert model.r_squared > 0.999
    assert abs(model.coefficients["sin(theta)"] - _TRUE_SIN) < abs(_TRUE_SIN) * 0.01
    assert abs(model.coefficients["theta_dot"] - _TRUE_DOT) < abs(_TRUE_DOT) * 0.01


def test_a_planted_dummy_feature_is_thresholded_out():
    dummy = (("theta*theta_dot", lambda th, om: th * om),)
    model = discover_ode(_traj(), threshold=0.5, extra_terms=dummy)
    assert "theta*theta_dot" not in model.coefficients           # noise term does not enter the law
    assert set(model.coefficients) == {"theta_dot", "sin(theta)"}


def test_discovery_is_deterministic():
    a = discover_ode(_traj(), threshold=0.5)
    b = discover_ode(_traj(), threshold=0.5)
    assert a.coefficients == b.coefficients and a.expression == b.expression


def test_stlsq_zeros_terms_below_threshold():
    rng = np.random.default_rng(0)
    x = rng.uniform(-1, 1, size=(200, 3))
    y = 5.0 * x[:, 0] - 2.0 * x[:, 2]              # middle column is irrelevant (true coeff 0)
    xi = stlsq(x, y, threshold=0.1)
    assert abs(xi[0] - 5.0) < 1e-6 and abs(xi[2] + 2.0) < 1e-6
    assert xi[1] == 0.0                            # the irrelevant term is thresholded to exactly zero


def test_too_short_trajectory_raises():
    import pytest
    from gen.simulation.multibody import Trajectory
    with pytest.raises(ValueError):
        discover_ode(Trajectory(t=[0.0, 0.1], theta=[0.0, 0.1], omega=[0.0, 0.0], energy=[0.0, 0.0]))
