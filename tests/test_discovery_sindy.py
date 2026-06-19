"""SINDy ODE discovery (discovery/sindy.py) from a GENESIS simulator trajectory.

Pins the categorical jump beyond a single power law: from a CLEAN RK4 pendulum trajectory, sparse
identification recovers the EXACT second-order ODE the simulator integrates — only the two terms the
dynamics need — and a planted dummy feature is thresholded out (the SINDy-hygiene property). Pure numpy,
offline, deterministic.
"""

import numpy as np

from gen.discovery.sindy import CoefficientBand, discover_ode, ode_coefficient_bands, stlsq
from gen.simulation.multibody import STANDARD_GRAVITY, Trajectory, simulate_pendulum

# damped driven pendulum: I·θ̈ = −c·ω − m·g·d·sinθ  →  θ̈ = −(c/I)·θ̇ − (m·g·d/I)·sin θ
_M, _D, _C = 2.0, 0.18, 0.2
_I = _M * _D * _D
_TRUE_SIN = -(_M * STANDARD_GRAVITY * _D) / _I       # ≈ -54.48
_TRUE_DOT = -_C / _I                                  # ≈ -3.086


def _traj():
    return simulate_pendulum(0.8, 0.0, lambda t, th, om: -_C * om,
                             inertia=_I, mass=_M, com_distance=_D, duration=12.0, dt=0.004)


def _noisy(traj, level=0.01, seed=7):
    """The same trajectory with relative Gaussian MEASUREMENT noise on θ and ω (sensor noise that the
    finite-difference target then amplifies)."""
    rng = np.random.default_rng(seed)
    th = np.asarray(traj.theta); om = np.asarray(traj.omega)
    return Trajectory(t=traj.t,
                      theta=tuple(th + level * np.std(th) * rng.standard_normal(th.shape)),
                      omega=tuple(om + level * np.std(om) * rng.standard_normal(om.shape)),
                      energy=traj.energy)


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
    with pytest.raises(ValueError):
        discover_ode(Trajectory(t=[0.0, 0.1], theta=[0.0, 0.1], omega=[0.0, 0.0], energy=[0.0, 0.0]))


def test_clean_data_gives_a_tight_band_that_pins_the_coefficients():
    """Ensemble-SINDy bootstrap on CLEAN RK4 data: each active coefficient's band is tight (well-
    identified) and its mean sits within 1% of the analytic truth — the honest "the data pins this"."""
    bands = ode_coefficient_bands(_traj(), threshold=0.5, n_resamples=60)
    assert set(bands) == {"theta_dot", "sin(theta)"}
    assert all(isinstance(b, CoefficientBand) for b in bands.values())
    assert abs(bands["sin(theta)"].mean - _TRUE_SIN) < abs(_TRUE_SIN) * 0.01
    assert abs(bands["theta_dot"].mean - _TRUE_DOT) < abs(_TRUE_DOT) * 0.01
    # tight: the statistical band is a tiny fraction of the coefficient magnitude on noise-free data
    assert bands["sin(theta)"].width < abs(_TRUE_SIN) * 0.01
    assert bands["theta_dot"].width < abs(_TRUE_DOT) * 0.01


def test_measurement_noise_widens_the_band():
    """Sensor noise, amplified by the finite-difference target, sharply widens the bootstrap band — the
    honest signal that the coefficient is no longer well-identified (SINDy's documented noise sensitivity)."""
    traj = _traj()
    clean = ode_coefficient_bands(traj, threshold=0.5, n_resamples=60)
    noisy = ode_coefficient_bands(_noisy(traj), threshold=0.5, n_resamples=60)
    assert noisy["sin(theta)"].std > clean["sin(theta)"].std        # noise -> real, wider uncertainty
    assert noisy["sin(theta)"].width > clean["sin(theta)"].width


def test_coefficient_bands_are_deterministic():
    a = ode_coefficient_bands(_traj(), threshold=0.5, n_resamples=40, seed=1)
    b = ode_coefficient_bands(_traj(), threshold=0.5, n_resamples=40, seed=1)
    assert a["sin(theta)"].mean == b["sin(theta)"].mean and a["theta_dot"].lo == b["theta_dot"].lo
