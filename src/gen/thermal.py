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

Consistent units: pass k in W/(mm·K), lengths in mm, temperatures in K (or °C for
differences) — then heat is in W. Honest boundary: linear, isotropic, steady-state
conduction — no convection/radiation boundary film, no temperature-dependent k, no
transient. A clean PASS bounds the conductive temperature rise; real cooling (a
convecting surface) only lowers it, so the conduction-only rise is conservative for a
heat-sunk part and optimistic for a still-air one (stated, not hidden).
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
