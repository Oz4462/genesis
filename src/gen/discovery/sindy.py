"""sindy — sparse identification of nonlinear dynamics (SINDy) in pure numpy, fed by GENESIS simulators.

The categorical jump beyond GENESIS' single power-law fit (FORSCHUNG_AUTONOMES_ERFINDEN §A2, P2): discover
the DIFFERENTIAL EQUATION a system obeys, from a time series, by SPARSE regression over a candidate
function library (Brunton/Proctor/Kutz, PNAS 2016). The honest GENESIS twist is the data source — the
trajectory comes from one of GENESIS' OWN deterministic simulators (``simulation/multibody.simulate_pendulum``,
``circuit``, ``wissensbasis/bio_molecular``), so the derivative is computed from CLEAN RK4 data, which
defuses SINDy's notorious noise sensitivity (the documented "fed from GENESIS' simulators" advantage).

The algorithm is STLSQ (sequentially-thresholded least squares): fit all library terms by least squares,
zero every coefficient below a threshold, refit on the survivors, iterate to a fixed point. The result is
a SPARSE ODE — only the terms the dynamics actually need. It is a PROPOSAL, not a certified law: the
recovered coefficients have an R² (reported), and the structure should still pass the SRBench-hygiene gate
(``srbench_hygiene``) — a high R² with a dummy term present is exactly the "Schein-Entdeckung" that gate
catches. No pysindy dependency (a thin ``sindy_pysindy`` adapter is the opt-in path); pure numpy.

Honest boundary: this MVP identifies a SECOND-ORDER scalar ODE ``θ̈ = f(θ, θ̇)`` over a fixed library
(constant, θ, θ̇, sin θ, cos θ, plus any caller-supplied extra terms). The derivative is a finite
difference of the simulator's ω(t); edge points are dropped. Higher-dimensional state, weak-form (WSINDy)
and a learned library are declared extensions. Deterministic, offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np


@dataclass(frozen=True)
class SindyModel:
    """A discovered sparse ODE ``target = Σ coefficients[term]·term``.

    ``coefficients`` holds ONLY the active (non-thresholded) terms; ``r_squared`` is the fit of the sparse
    model to the finite-difference target derivative; ``expression`` renders it; ``n_active`` is the term
    count (parsimony). A SINDy model is a candidate — pair it with the hygiene gate before trusting it."""

    target: str
    coefficients: dict[str, float]
    r_squared: float
    expression: str
    n_active: int


#: The default second-order pendulum library: name -> function of (theta, omega) arrays.
def _default_terms(theta: np.ndarray, omega: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "1": np.ones_like(theta),
        "theta": theta,
        "theta_dot": omega,
        "sin(theta)": np.sin(theta),
        "cos(theta)": np.cos(theta),
    }


def stlsq(library_matrix: np.ndarray, target: np.ndarray, *, threshold: float, max_iter: int = 10) -> np.ndarray:
    """Sequentially-thresholded least squares. Fit ``library_matrix @ xi ≈ target`` by least squares, then
    repeatedly zero every ``|xi| < threshold`` and refit on the surviving columns until the active set is
    stable (or ``max_iter``). Returns the full coefficient vector (zeros on the dropped terms). Pure numpy."""
    if threshold < 0.0:
        raise ValueError("threshold must be >= 0")
    xi, *_ = np.linalg.lstsq(library_matrix, target, rcond=None)
    active = np.abs(xi) >= threshold
    for _ in range(max_iter):
        xi = np.where(active, xi, 0.0)
        if not active.any():
            break
        sub, *_ = np.linalg.lstsq(library_matrix[:, active], target, rcond=None)
        xi = np.zeros(library_matrix.shape[1])
        xi[active] = sub
        new_active = np.abs(xi) >= threshold
        if np.array_equal(new_active, active):
            break
        active = new_active
    return xi


def discover_ode(
    traj,
    *,
    target: str = "theta_ddot",
    threshold: float = 0.05,
    drop_edges: int = 3,
    extra_terms: Sequence[tuple[str, Callable[[np.ndarray, np.ndarray], np.ndarray]]] = (),
) -> SindyModel:
    """Discover the sparse ODE ``θ̈ = f(θ, θ̇)`` (``target='theta_ddot'``) or ``θ̇ = f(...)`` from a
    ``simulation.multibody.Trajectory``.

    The target derivative is a central finite difference of the simulator's ω(t) (for θ̈) or θ(t) (for θ̇);
    ``drop_edges`` rows are removed at each end (1st-order finite-difference edge error). ``extra_terms`` are
    extra library functions ``(name, fn(theta, omega))`` — e.g. a dummy noise term for the hygiene test, or
    a richer basis. STLSQ keeps only the terms the dynamics need. Raises ValueError on a too-short trajectory.
    """
    t = np.asarray(traj.t, dtype=float)
    theta = np.asarray(traj.theta, dtype=float)
    omega = np.asarray(traj.omega, dtype=float)
    if t.shape[0] < 2 * drop_edges + 5:
        raise ValueError("trajectory too short for a finite-difference SINDy fit")

    if target == "theta_ddot":
        dxdt = np.gradient(omega, t)
    elif target == "theta_dot":
        dxdt = np.gradient(theta, t)
    else:
        raise ValueError("target must be 'theta_ddot' or 'theta_dot'")

    terms = _default_terms(theta, omega)
    for name, fn in extra_terms:
        terms[name] = np.asarray(fn(theta, omega), dtype=float)

    sl = slice(drop_edges, t.shape[0] - drop_edges) if drop_edges > 0 else slice(None)
    names = list(terms)
    library = np.column_stack([terms[n][sl] for n in names])
    y = dxdt[sl]

    xi = stlsq(library, y, threshold=threshold)
    y_hat = library @ xi
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0

    coefficients = {n: float(c) for n, c in zip(names, xi) if c != 0.0}
    expression = f"{target} = " + (
        " + ".join(f"{c:.4g}*{n}" for n, c in coefficients.items()) if coefficients else "0"
    )
    return SindyModel(target=target, coefficients=coefficients, r_squared=r_squared,
                      expression=expression, n_active=len(coefficients))
