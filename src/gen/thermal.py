"""Steady-state heat conduction FEM — the thermal axis (numpy, no solver dep).

The electrical layers (circuit.py / ERC) compute the power a component dissipates;
the structural layers compute stress. The missing physics that connects them is
HEAT: a dissipated power raises a part's temperature, and a polymer part (PLA glass
transition ~60 °C) fails thermally long before it fails mechanically. This module is
the steady-state heat-conduction analogue of the elasticity FEM: the scalar field is
temperature, the element is the 4-node tetrahedron, and the element matrix is
k·V·(∇N)ᵀ(∇N) — Fourier conduction. Pure numpy, the same structured mesher as the
elasticity solver, no external dependency.

Verified, not asserted: the linear tetrahedron reproduces a LINEAR temperature field
exactly, so 1-D conduction through a prismatic bar returns Fourier's law
Q = k·A·ΔT/L to machine precision on any mesh — the thermal twin of the
"uniform stress is exact" elasticity test. The conducted heat read from the FEM
reactions equals the closed form exactly; the test pins both.

The TRANSIENT extension (heat capacity C·Ṫ + K·T = q, Backward-Euler) answers the
time question — "how long until it reaches the glass transition?" — and is verified
the same way: its steady-state limit equals the steady solve exactly, the capacitance
sums to ρc·V, and the slowest thermal time constant (the eigenvalue 1/λ₁) converges to
the analytic first-mode value 4ρcL²/(π²k) of a bar.

Consistent units: pass k in W/(mm·K), lengths in mm, temperatures in K (or °C for
differences) — then heat is in W; the volumetric heat capacity ρc is in J/(mm³·K) and
time in s. Honest boundary: linear, isotropic conduction — no convection/radiation
boundary film, no temperature-dependent k. A clean steady PASS bounds the conductive
temperature rise; real cooling (a convecting surface) only lowers it, so the
conduction-only rise is conservative for a heat-sunk part and optimistic for a
still-air one (stated, not hidden).
"""

from __future__ import annotations

import numpy as np

from .core.errors import GeometryError


def _tet4_conductivity(coords: np.ndarray, conductivity: float) -> np.ndarray:
    """4×4 element conductivity matrix k·V·(∇N)ᵀ(∇N) of a 4-node tetrahedron.

    The shape-function gradients are constant over the element (linear field), so the
    matrix is exact in closed form — no quadrature. `coords` is the (4×3) node block.
    """
    m = np.ones((4, 4))
    m[:, 1:] = coords                       # rows [1, x, y, z]
    vol6 = np.linalg.det(m)                 # = 6·V (signed)
    if abs(vol6) < 1e-18:
        raise GeometryError("degenerate tetrahedron (zero volume) in the thermal mesh")
    grads = np.linalg.inv(m)[1:4, :]        # (3×4): rows dN/dx, dN/dy, dN/dz
    vol = abs(vol6) / 6.0
    return conductivity * vol * (grads.T @ grads)


def solve_heat(
    nodes: np.ndarray,
    tets: np.ndarray,
    conductivity: float,
    fixed_temps: dict[int, float],
    heat_loads: dict[int, float],
) -> tuple[np.ndarray, dict[int, float]]:
    """Solve K_T·T = q for steady-state conduction.

    `fixed_temps` are prescribed nodal temperatures ``{node: T}`` (Dirichlet, e.g. a
    heat-sunk face); `heat_loads` are nodal heat inputs ``{node: Q_in}`` in W (a
    dissipating component). Returns ``(temperatures (N,), reactions)`` where
    ``reactions[node]`` is the external heat (W) that must be supplied at each fixed
    node to hold its temperature — NEGATIVE at a sink (heat leaving the part), so the
    conducted heat out of a cold face is ``-sum(reactions over that face)``.

    Raises GeometryError if no temperature is fixed (a pure-Neumann steady-state
    problem is singular — there must be at least one heat-sunk node). Deterministic.
    """
    if not fixed_temps:
        raise GeometryError(
            "steady-state conduction needs at least one fixed temperature (a heat "
            "sink); a fully insulated body has no steady state."
        )
    n = len(nodes)
    k = np.zeros((n, n))
    for tet in tets:
        ke = _tet4_conductivity(nodes[tet], conductivity)
        k[np.ix_(tet, tet)] += ke

    q = np.zeros(n)
    for node, val in heat_loads.items():
        q[node] += val
    free = np.array([i for i in range(n) if i not in fixed_temps])
    t = np.zeros(n)
    for node, val in fixed_temps.items():
        t[node] = val
    if free.size:
        fixed_idx = np.array(list(fixed_temps))
        rhs = q[free] - k[np.ix_(free, fixed_idx)] @ np.array(list(fixed_temps.values()))
        t[free] = np.linalg.solve(k[np.ix_(free, free)], rhs)

    react_vec = k @ t - q
    reactions = {int(node): float(react_vec[node]) for node in fixed_temps}
    return t, reactions


def fourier_heat(conductivity: float, area: float, length: float, delta_t: float) -> float:
    """1-D Fourier conduction Q = k·A·ΔT/L (W) — the closed form the FEM reproduces
    exactly. `area` is the cross-section ⟂ to the flow, `length` the path length."""
    return conductivity * area * delta_t / length


def conductive_temperature_rise(
    power: float, conductivity: float, area: float, length: float
) -> float:
    """Steady-state temperature rise ΔT = P·L/(k·A) (K) of a 1-D conduction path
    carrying dissipated `power` (W) to a heat sink — Fourier's law inverted."""
    if conductivity <= 0.0 or area <= 0.0 or length <= 0.0:
        raise ValueError("conductivity, area and length must be positive")
    return power * length / (conductivity * area)


def overtemperature_check(
    power: float,
    conductivity: float,
    area: float,
    length: float,
    *,
    ambient: float,
    max_service_temp: float,
) -> dict:
    """Thermal DFM check: does the conductive temperature rise from `power` push the
    peak temperature past the material's service limit?

    Returns ``{"delta_t", "peak_temp", "max_service_temp", "margin", "ok"}``: peak =
    ambient + ΔT; margin = max_service_temp − peak; ok = margin ≥ 0. This is the
    conduction-only bound — a real convecting/radiating surface lowers the rise, so a
    PASS here on a still-air part is optimistic and a FAIL is decisive. Deterministic.
    """
    dt = conductive_temperature_rise(power, conductivity, area, length)
    peak = ambient + dt
    margin = max_service_temp - peak
    return {
        "delta_t": dt,
        "peak_temp": peak,
        "max_service_temp": max_service_temp,
        "margin": margin,
        "ok": margin >= 0.0,
    }


def peak_temperature(
    nodes: np.ndarray,
    tets: np.ndarray,
    conductivity: float,
    fixed_temps: dict[int, float],
    heat_loads: dict[int, float],
) -> float:
    """Peak nodal temperature of the conduction solution — usable on ANY meshed
    geometry (where no closed form exists), e.g. a plate spreading a point heat
    source to cooled edges. Convenience wrapper over `solve_heat`."""
    t, _ = solve_heat(nodes, tets, conductivity, fixed_temps, heat_loads)
    return float(t.max())


# --- transient conduction (the time axis) --------------------------------------

def _tet4_capacitance(coords: np.ndarray, volumetric_heat_capacity: float) -> np.ndarray:
    """4×4 consistent heat-capacity matrix ρc·∫NᵀN dV of a 4-node tetrahedron =
    (ρc·V/20)·(1 + δ_ij) — closed form, no quadrature; sums to ρc·V exactly."""
    m = np.ones((4, 4))
    m[:, 1:] = coords
    vol = abs(np.linalg.det(m)) / 6.0
    return (volumetric_heat_capacity * vol / 20.0) * (np.ones((4, 4)) + np.eye(4))


def _assemble_conduction_capacitance(nodes, tets, conductivity, volumetric_heat_capacity):
    n = len(nodes)
    k = np.zeros((n, n))
    c = np.zeros((n, n))
    for tet in tets:
        coords = nodes[tet]
        k[np.ix_(tet, tet)] += _tet4_conductivity(coords, conductivity)
        c[np.ix_(tet, tet)] += _tet4_capacitance(coords, volumetric_heat_capacity)
    return k, c


def solve_transient_heat(
    nodes: np.ndarray,
    tets: np.ndarray,
    conductivity: float,
    volumetric_heat_capacity: float,
    fixed_temps: dict[int, float],
    heat_loads: dict[int, float],
    *,
    dt: float,
    n_steps: int,
    initial_temp,
) -> np.ndarray:
    """March the transient conduction C·Ṫ + K·T = q in time by Backward-Euler.

    `volumetric_heat_capacity` is ρ·c (J/(mm³·K)); `dt` the step (s); `initial_temp` a
    scalar or per-node array. Each step solves (C/Δt + K)·Tⁿ⁺¹ = q + (C/Δt)·Tⁿ with the
    fixed temperatures held. Returns the temperature history, shape ``(n_steps+1, N)``
    (row 0 is the initial state). Backward-Euler is unconditionally stable, so any Δt is
    stable (accuracy is first-order in Δt). Deterministic.
    """
    if dt <= 0.0 or n_steps < 1:
        raise ValueError("dt must be positive and n_steps >= 1")
    n = len(nodes)
    k, c = _assemble_conduction_capacitance(
        nodes, tets, conductivity, volumetric_heat_capacity
    )
    q = np.zeros(n)
    for node, val in heat_loads.items():
        q[node] += val
    t = np.full(n, float(initial_temp)) if np.isscalar(initial_temp) else np.array(
        initial_temp, dtype=float
    )
    for node, val in fixed_temps.items():
        t[node] = val
    free = np.array([i for i in range(n) if i not in fixed_temps])
    a = c / dt + k
    history = [t.copy()]
    if free.size:
        a_ff = a[np.ix_(free, free)]
        fixed_idx = np.array(list(fixed_temps)) if fixed_temps else np.array([], dtype=int)
        fixed_val = np.array(list(fixed_temps.values())) if fixed_temps else np.array([])
        for _ in range(n_steps):
            rhs = q + (c / dt) @ t
            rhs_f = rhs[free]
            if fixed_idx.size:
                rhs_f = rhs_f - a[np.ix_(free, fixed_idx)] @ fixed_val
            t = t.copy()
            t[free] = np.linalg.solve(a_ff, rhs_f)
            history.append(t.copy())
    else:
        for _ in range(n_steps):
            history.append(t.copy())
    return np.array(history)


def slowest_thermal_time_constant(
    nodes: np.ndarray,
    tets: np.ndarray,
    conductivity: float,
    volumetric_heat_capacity: float,
    fixed_temps: dict[int, float],
) -> float:
    """The longest thermal time constant τ₁ = 1/λ₁ (s) — the slowest decay mode of the
    body, from the generalized eigenproblem K·φ = λ·C·φ on the free nodes.

    This is the "how slow is the slowest transient" number, the thermal twin of the
    fundamental natural frequency. For a bar (fixed one end, insulated the other) it
    converges to the analytic first mode 4ρcL²/(π²k). Raises GeometryError if every
    node is fixed.
    """
    if not fixed_temps:
        raise GeometryError("a free body has an infinite time constant (no heat sink)")
    k, c = _assemble_conduction_capacitance(
        nodes, tets, conductivity, volumetric_heat_capacity
    )
    free = np.array([i for i in range(len(nodes)) if i not in fixed_temps])
    if free.size == 0:
        raise GeometryError("every node is fixed — there is no transient")
    chol = np.linalg.cholesky(c[np.ix_(free, free)])
    a = np.linalg.solve(chol, np.linalg.solve(chol, k[np.ix_(free, free)]).T).T
    lam = np.linalg.eigvalsh(a)
    lam = lam[lam > 1e-12]
    return float(1.0 / lam.min())


def time_to_threshold(history: np.ndarray, dt: float, threshold: float) -> float | None:
    """First time (s) at which the peak temperature of the transient history crosses
    `threshold` — the "time to reach the glass transition" answer. Returns None if it
    never crosses within the simulated window. `history` is the array from
    `solve_transient_heat`; the step index times `dt` gives the time."""
    peaks = history.max(axis=1)
    for step, peak in enumerate(peaks):
        if peak >= threshold:
            return step * dt
    return None
