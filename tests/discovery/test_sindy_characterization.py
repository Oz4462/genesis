"""Depth-audit characterization of discovery/sindy.py (T01).

Headline claim under audit: SINDy performs *sparse* identification of nonlinear dynamics —
it recovers the governing terms of a system by sparse regression over a candidate library,
zeroing out terms the dynamics do not need (true sparsity, not a dense least-squares fit).

These tests fail loudly if the module were a hollow facade:
  * feed data from a KNOWN sparse system (a cubic polynomial RHS and a cubic-damping ODE) and
    assert the active terms + coefficients are recovered within tolerance while spurious terms
    are zeroed EXACTLY — and contrast against plain ``np.linalg.lstsq`` to prove the sparsity is
    real (the dense fit leaves nonzero spurious coefficients; STLSQ does not);
  * NEGATIVE: missing/too-short data raises (no fabricated formula), a target with no sparse
    representation in the library yields an honest empty model (all-zero coefficients), and an
    inadequate library is reported with an honestly lower R² rather than a fabricated perfect fit.
  * PROPERTY (Hypothesis): for any random well-conditioned sparse linear system, STLSQ recovers
    the exact support and the coefficients within tolerance — the sparse-recovery invariant.

Pure numpy, deterministic, offline. See docs/audit/sindy.md for the verdict.
"""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.sindy import discover_ode, stlsq
from gen.simulation.multibody import Trajectory


# --------------------------------------------------------------------------- helpers
def _rk4_trajectory(accel, theta0=0.8, omega0=0.0, duration=10.0, dt=0.002):
    """Integrate a KNOWN scalar second-order ODE ``theta_ddot = accel(theta, omega)`` with RK4 and
    return a ``Trajectory``. Used to manufacture data from a system whose true law we control, so the
    recovered ODE can be checked against ground truth. ``energy`` is unused by SINDy (filled with 0)."""
    ts, thetas, omegas = [0.0], [theta0], [omega0]
    theta, omega = theta0, omega0
    for _ in range(int(duration / dt)):
        def deriv(a, w):
            return w, accel(a, w)

        k1 = deriv(theta, omega)
        k2 = deriv(theta + dt / 2 * k1[0], omega + dt / 2 * k1[1])
        k3 = deriv(theta + dt / 2 * k2[0], omega + dt / 2 * k2[1])
        k4 = deriv(theta + dt * k3[0], omega + dt * k3[1])
        theta += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        omega += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        ts.append(ts[-1] + dt)
        thetas.append(theta)
        omegas.append(omega)
    return Trajectory(t=ts, theta=thetas, omega=omegas, energy=[0.0] * len(ts))


def _polynomial_problem(noise=0.0, seed=0):
    """A KNOWN sparse polynomial regression problem ``y = 3 + 2x - 1.5x^3`` over a 7-term library
    {1, x, x^2, x^3, v, x*v, v^2}. Four of the seven terms are genuinely inactive (true coeff 0).
    Well-conditioned random design (n >> p), so exact recovery is the ground truth to assert."""
    rng = np.random.default_rng(seed)
    n = 500
    x = rng.uniform(-2.0, 2.0, n)
    v = rng.uniform(-2.0, 2.0, n)
    columns = {
        "1": np.ones(n), "x": x, "x^2": x ** 2, "x^3": x ** 3,
        "v": v, "x*v": x * v, "v^2": v ** 2,
    }
    names = list(columns)
    library = np.column_stack([columns[k] for k in names])
    truth = {"1": 3.0, "x": 2.0, "x^3": -1.5}
    target = sum(truth.get(k, 0.0) * columns[k] for k in names)
    if noise:
        target = target + noise * rng.standard_normal(n)
    return names, library, target, truth


# --------------------------------------------------------------------------- POSITIVE: real recovery
def test_recovers_known_sparse_polynomial_system_with_correct_coefficients():
    """The core SINDy claim: from data of a KNOWN sparse system, STLSQ recovers exactly the active
    terms with the right coefficients and zeros every inactive term — even with measurement noise."""
    names, library, target, truth = _polynomial_problem(noise=0.05, seed=1)
    xi = stlsq(library, target, threshold=0.5)
    coeffs = dict(zip(names, xi))

    active = {n for n, c in coeffs.items() if c != 0.0}
    assert active == set(truth), f"recovered support {active} != true support {set(truth)}"
    for term, true_value in truth.items():
        assert abs(coeffs[term] - true_value) < 0.1, f"{term}: {coeffs[term]} vs {true_value}"
    # every inactive term is driven to EXACTLY zero — the parsimony the headline claims
    for term in names:
        if term not in truth:
            assert coeffs[term] == 0.0


def test_sparsity_is_real_not_a_dense_least_squares_fit():
    """Contrast against plain least squares on the SAME noisy data: the dense solve leaves nonzero
    coefficients on spurious terms, while STLSQ thresholds them to exactly zero. If SINDy were a
    facade (a relabeled dense fit), this test would fail because the spurious terms would survive."""
    names, library, target, truth = _polynomial_problem(noise=0.05, seed=1)
    spurious = [n for n in names if n not in truth]

    dense, *_ = np.linalg.lstsq(library, target, rcond=None)
    sparse = stlsq(library, target, threshold=0.5)

    assert any(abs(dense[names.index(s)]) > 1e-6 for s in spurious), "dense fit should be dense"
    assert all(sparse[names.index(s)] == 0.0 for s in spurious), "STLSQ must zero spurious terms"


def test_discover_ode_recovers_a_nonlinear_cubic_damping_law():
    """End-to-end on a manufactured trajectory of a KNOWN nonlinear ODE θ̈ = -2·θ - 0.6·θ̇³.
    With the needed cubic-damping term supplied, SINDy recovers it with the correct coefficient and a
    near-perfect R²; the irrelevant default library terms (constant, sin, cos) are thresholded out."""
    coeff_lin, coeff_cubic = -2.0, -0.6
    traj = _rk4_trajectory(lambda th, om: coeff_lin * th + coeff_cubic * om ** 3)
    model = discover_ode(traj, threshold=0.3,
                         extra_terms=(("theta_dot^3", lambda th, om: om ** 3),))

    assert model.coefficients.get("theta_dot^3") is not None
    assert abs(model.coefficients["theta_dot^3"] - coeff_cubic) < 0.02
    assert abs(model.coefficients["theta"] - coeff_lin) < 0.05
    assert model.r_squared > 0.999
    assert "1" not in model.coefficients and "cos(theta)" not in model.coefficients


# --------------------------------------------------------------------------- NEGATIVE: honest refusal
def test_missing_data_raises_instead_of_fabricating_a_formula():
    """A too-short trajectory carries no identifiable dynamics — the module must fail loud (ValueError),
    never return a fabricated ODE. 'Keine stillen Defaults bei faktischen Dingen.'"""
    stub = Trajectory(t=[0.0, 0.1], theta=[0.0, 0.1], omega=[0.0, 0.0], energy=[0.0, 0.0])
    with pytest.raises(ValueError):
        discover_ode(stub)


def test_negative_threshold_is_rejected():
    """A negative sparsity threshold is meaningless; STLSQ must reject it rather than silently proceed."""
    rng = np.random.default_rng(0)
    library = rng.standard_normal((50, 3))
    target = rng.standard_normal(50)
    with pytest.raises(ValueError):
        stlsq(library, target, threshold=-0.1)


def test_target_with_no_sparse_representation_yields_an_honest_empty_model():
    """A target that is pure noise, uncorrelated with every library column, has NO sparse law. STLSQ
    must return the all-zero model (an honest 'I found nothing') rather than fabricate active terms."""
    rng = np.random.default_rng(2)
    library = rng.standard_normal((300, 5))
    noise_target = 0.3 * rng.standard_normal(300)  # small, structureless, orthogonal in expectation
    xi = stlsq(library, noise_target, threshold=0.5)
    assert np.count_nonzero(xi) == 0


def test_inadequate_library_is_reported_with_lower_r2_not_a_fabricated_perfect_fit():
    """Same cubic-damping system, but WITHOUT the θ̇³ term in the library: the dynamics are not
    representable, so SINDy must report an honestly lower R² (and cannot list θ̇³, which is absent) —
    not a fabricated R²≈1. This is the 'no fabricated claim' contract against an inadequate basis."""
    traj = _rk4_trajectory(lambda th, om: -2.0 * th - 0.6 * om ** 3)
    adequate = discover_ode(traj, threshold=0.3,
                            extra_terms=(("theta_dot^3", lambda th, om: om ** 3),))
    inadequate = discover_ode(traj, threshold=0.3)

    assert "theta_dot^3" not in inadequate.coefficients   # absent term cannot be invented
    assert inadequate.r_squared < adequate.r_squared       # honest: worse basis -> worse fit
    assert inadequate.r_squared < 0.99                     # and it does NOT claim a perfect law


# --------------------------------------------------------------------------- PROPERTY: recovery invariant
@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    support=st.lists(st.booleans(), min_size=6, max_size=6),
)
def test_property_stlsq_recovers_exact_support_of_any_sparse_linear_system(seed, support):
    """INVARIANT: for any well-conditioned random design X and any sparse coefficient vector whose
    nonzero entries are comfortably above the threshold, STLSQ recovers the EXACT support (zeros land
    exactly where the true zeros are) and the coefficients within tolerance. This is the formal
    sparse-recovery property the module's headline rests on, explored across the input space."""
    rng = np.random.default_rng(seed)
    n_rows, p = 400, 6
    X = rng.standard_normal((n_rows, p))
    # nonzero coeffs in [2,5] magnitude (>> threshold 0.5) so recovery of the support is unambiguous
    beta = np.array([
        (rng.uniform(2.0, 5.0) * rng.choice([-1.0, 1.0])) if active else 0.0
        for active in support
    ])
    y = X @ beta  # noise-free: exact recovery is a true invariant here
    xi = stlsq(X, y, threshold=0.5)

    for i in range(p):
        assert (xi[i] == 0.0) == (beta[i] == 0.0), "support mismatch (a true zero became active or vice versa)"
        if beta[i] != 0.0:
            assert abs(xi[i] - beta[i]) < 0.05
