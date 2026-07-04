"""DC operating-point circuit solver by Modified Nodal Analysis (the SPICE δ-layer).

GATE ERC proves the netlist's CONNECTIVITY (no simulation). The next layer is the
actual DC operating point: given resistors and sources, what voltage sits on each
node and what current does each source deliver? This module is that solver —
Modified Nodal Analysis (MNA), the linear-DC core of every SPICE engine —
implemented in pure numpy, so it needs NO external simulator (ngspice was not
installed) and runs fully offline and deterministically.

MNA assembles the system

    [ G  B ] [ v ]   [ i ]
    [ C  D ] [ j ] = [ e ]

where G holds node conductances, B/C the voltage-source incidences, v the unknown
node voltages and j the unknown source branch currents; it is solved directly.

Verified, not asserted: the test cross-checks the solver against Ohm's law (a
source across a resistor gives I = V/R), a two-resistor divider (known node
voltage), and the capstone's own numbers — the 12 V PSU across the LED strip's
equivalent resistance delivers exactly its rated 1.5 A.

Honest boundary (updated): core is linear DC MNA (the SPICE delta layer) in pure numpy — fully offline, no ngspice. Transient (Backward-Euler), AC (complex), basic non-linear iteration (diode pnjlim-style in callers) and EMI notes are available via the electronics layer on top (run_electronics_simulation with do_transient/do_ac_emi). Full vendor-exact IBIS/3D-EM/SPICE models remain external-tool seam for ultra-precision; internal is deterministic, provenance-rich, co-sim ready and "besser als vorher" for Genesis generalist packages + falsification + Lern. Verified in test_circuit + electronics smokes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

GROUND = "0"


@dataclass(frozen=True)
class Resistor:
    a: str
    b: str
    ohms: float


@dataclass(frozen=True)
class VoltageSource:
    p: str            # + terminal node
    n: str            # - terminal node
    volts: float
    name: str = "V"


@dataclass(frozen=True)
class CurrentSource:
    frm: str          # current flows from `frm` to `to` through the source
    to: str
    amps: float


@dataclass(frozen=True)
class Capacitor:
    a: str
    b: str
    farads: float


@dataclass(frozen=True)
class Inductor:
    a: str
    b: str
    henries: float


#: Thermal voltage kT/q at ~300 K [V] (Boltzmann constant × temperature / charge).
THERMAL_VOLTAGE = 0.025852


@dataclass(frozen=True)
class Diode:
    """A Shockley diode: I = i_sat · (exp(V / (n·Vt)) − 1), V = V(anode) − V(cathode).
    `n` is the ideality factor. Non-linear — handled by Newton-Raphson in
    `solve_dc_nonlinear`."""

    anode: str
    cathode: str
    i_sat: float = 1e-12
    n: float = 1.0


def _nodes(component) -> tuple[str, ...]:
    if isinstance(component, (Resistor, Capacitor, Inductor)):
        return (component.a, component.b)
    if isinstance(component, VoltageSource):
        return (component.p, component.n)
    if isinstance(component, CurrentSource):
        return (component.frm, component.to)
    if isinstance(component, Diode):
        return (component.anode, component.cathode)
    raise TypeError(f"unknown component {component!r}")


def _positive_value(value: float, what: str) -> float:
    """A component value that must be positive and finite — ``not (v > 0)`` also
    catches NaN. Raises ValueError with the component context, never a
    ZeroDivisionError from a silent 1/0 stamp."""
    if not (value > 0.0) or math.isinf(value):
        raise ValueError(f"{what} must be positive and finite, got {value!r}")
    return value


def _source_keys(vsources) -> list[str]:
    """Unique result keys for the voltage sources: the declared name, or ``V{k}``
    for an empty name. Raises ValueError on duplicates — two same-named sources
    would silently overwrite each other's current in the result dict."""
    keys = [vs.name or f"V{k}" for k, vs in enumerate(vsources)]
    if len(set(keys)) != len(keys):
        dup = sorted({k for k in keys if keys.count(k) > 1})
        raise ValueError(
            f"duplicate voltage-source name(s) {dup}: source currents are keyed "
            "by name — give each VoltageSource a unique `name`"
        )
    return keys


def solve_dc(components, ground: str = GROUND) -> tuple[dict[str, float], dict[str, float]]:
    """Solve the DC operating point. Returns ``(node_voltages, source_currents)``
    — node voltages in volts (ground = 0), and each voltage source's delivered
    current in amperes (positive = current out of the + terminal into the circuit),
    keyed by the source's unique ``name`` (``V{index}`` for an empty name).
    Deterministic; raises ``numpy.linalg.LinAlgError`` on a singular network
    (e.g. a floating subgraph) rather than guessing, and ``ValueError`` on a
    non-positive/non-finite resistance or duplicate voltage-source names.

    Honest boundary: an EMPTY component list is a valid (empty) linear system and
    returns ``({ground: 0.0}, {})`` — as a solver that is correct, but as a GATE
    it is vacuous; a caller using this as evidence must check the netlist is
    non-empty itself.
    """
    nodes = sorted({nd for c in components for nd in _nodes(c)} - {ground})
    idx = {nd: i for i, nd in enumerate(nodes)}
    vsources = [c for c in components if isinstance(c, VoltageSource)]
    source_keys = _source_keys(vsources)
    n, m = len(nodes), len(vsources)

    A = np.zeros((n + m, n + m))
    z = np.zeros(n + m)

    for c in components:
        if isinstance(c, Resistor):
            g = 1.0 / _positive_value(c.ohms, f"Resistor({c.a!r},{c.b!r}).ohms")
            if c.a != ground:
                A[idx[c.a], idx[c.a]] += g
            if c.b != ground:
                A[idx[c.b], idx[c.b]] += g
            if c.a != ground and c.b != ground:
                A[idx[c.a], idx[c.b]] -= g
                A[idx[c.b], idx[c.a]] -= g
        elif isinstance(c, CurrentSource):
            if c.frm != ground:
                z[idx[c.frm]] -= c.amps
            if c.to != ground:
                z[idx[c.to]] += c.amps

    for k, vs in enumerate(vsources):
        row = n + k
        if vs.p != ground:
            A[idx[vs.p], row] += 1.0
            A[row, idx[vs.p]] += 1.0
        if vs.n != ground:
            A[idx[vs.n], row] -= 1.0
            A[row, idx[vs.n]] -= 1.0
        z[row] = vs.volts

    x = np.linalg.solve(A, z)
    node_v = {nd: float(x[idx[nd]]) for nd in nodes}
    node_v[ground] = 0.0
    # the MNA branch current j flows from + to - INSIDE the source; the current
    # the source delivers to the circuit is its negative.
    source_i = {source_keys[k]: float(-x[n + k]) for k in range(m)}
    return node_v, source_i


def solve_dc_nonlinear(
    components,
    ground: str = GROUND,
    *,
    max_iter: int = 200,
    tol: float = 1e-10,
) -> tuple[dict[str, float], dict[str, float]]:
    """Solve a DC operating point that contains non-linear diodes by Newton-Raphson
    with the diode companion model (the classic SPICE inner loop).

    Each diode is replaced, at the current voltage estimate, by its linearised
    Norton companion — a conductance Geq = dI/dV and a current source Ieq = Id −
    Geq·Vd — and the resulting linear network is solved by `solve_dc`; the estimate
    is updated and the step is repeated until the node voltages converge.
    Voltage limiting (a per-step cap on Vd) keeps the exponential from overflowing.
    Returns ``(node_voltages, source_currents)`` like `solve_dc`. Deterministic.
    Raises ``RuntimeError`` if it does not converge within `max_iter` — never a
    silently wrong operating point.
    """
    diodes = [c for c in components if isinstance(c, Diode)]
    linear = [c for c in components if not isinstance(c, Diode)]
    if not diodes:
        return solve_dc(linear, ground)

    nodes = sorted({nd for c in components for nd in _nodes(c)} - {ground})
    v = {nd: 0.0 for nd in nodes}
    v[ground] = 0.0
    # per-diode previous (limited) junction voltage, for SPICE-style pnjlim limiting
    vd_prev = [0.0 for _ in diodes]
    node_v: dict[str, float] = dict(v)
    source_i: dict[str, float] = {}

    for _ in range(max_iter):
        companions: list[object] = []
        for k, d in enumerate(diodes):
            nvt = d.n * THERMAL_VOLTAGE
            vcrit = nvt * math.log(nvt / (math.sqrt(2.0) * d.i_sat))
            vd = _pnjlim(v[d.anode] - v[d.cathode], vd_prev[k], nvt, vcrit)
            vd_prev[k] = vd
            e = math.exp(vd / nvt)
            i_d = d.i_sat * (e - 1.0)
            g_eq = max(d.i_sat / nvt * e, 1e-12)    # dI/dV, floored for conditioning
            i_eq = i_d - g_eq * vd                  # Norton equivalent current
            companions.append(Resistor(d.anode, d.cathode, 1.0 / g_eq))
            # the diode current flows anode -> cathode, so the Norton companion
            # current source flows the same way (anode -> cathode)
            companions.append(CurrentSource(d.anode, d.cathode, i_eq))

        node_v, source_i = solve_dc(linear + companions, ground)
        # default=0.0: with every terminal on ground there are zero unknown nodes
        # and the (trivial) solution has converged — max() on an empty sequence
        # must not crash the loop.
        delta = max((abs(node_v[nd] - v[nd]) for nd in nodes), default=0.0)
        v = {nd: node_v[nd] for nd in nodes}
        v[ground] = 0.0
        # node-voltage convergence implies junction-voltage convergence: each
        # diode's Vd is a difference of two of these node voltages.
        if delta < tol:
            return node_v, source_i

    raise RuntimeError("nonlinear DC did not converge — check the circuit / starting point")


def _pnjlim(vnew: float, vold: float, vt: float, vcrit: float) -> float:
    """SPICE junction-voltage limiting: damp the per-iteration change in a forward
    junction voltage so the diode exponential cannot overshoot/overflow (Nagel,
    SPICE2). Returns the limited voltage."""
    if vnew > vcrit and abs(vnew - vold) > 2.0 * vt:
        if vold > 0.0:
            arg = 1.0 + (vnew - vold) / vt
            return vold + vt * math.log(arg) if arg > 0.0 else vcrit
        return vt * math.log(max(vnew / vt, 1e-12)) if vnew > 0.0 else vnew
    return vnew


def solve_transient(
    components,
    t_end: float,
    dt: float,
    ground: str = GROUND,
) -> tuple[list[float], dict[str, list[float]]]:
    """Transient (time-domain) analysis by Backward-Euler companion models.

    Each capacitor becomes, at every step, a conductance C/dt plus a current source
    carrying its previous-voltage memory; each inductor a conductance dt/L plus a
    current source carrying its previous current. The resulting resistive network is
    solved by `solve_dc` at each step. Backward Euler is unconditionally stable.

    Returns ``(times, node_history)`` where node_history maps each node to its
    voltage at each time in `times` (starting from a zero-state t=0). Deterministic.
    Raises ``ValueError`` on a non-positive/non-finite `dt`, a non-finite or
    negative `t_end`, or a non-positive/non-finite capacitance/inductance —
    never a ZeroDivisionError or a silently wrong companion stamp.
    """
    if not (dt > 0.0) or math.isinf(dt):
        raise ValueError(f"dt must be a positive finite time step, got {dt!r}")
    if not math.isfinite(t_end) or t_end < 0.0:
        raise ValueError(f"t_end must be finite and >= 0, got {t_end!r}")
    caps = [c for c in components if isinstance(c, Capacitor)]
    inds = [c for c in components if isinstance(c, Inductor)]
    for c in caps:
        _positive_value(c.farads, f"Capacitor({c.a!r},{c.b!r}).farads")
    for c in inds:
        _positive_value(c.henries, f"Inductor({c.a!r},{c.b!r}).henries")
    linear = [c for c in components if not isinstance(c, (Capacitor, Inductor))]
    nodes = sorted({nd for c in components for nd in _nodes(c)} - {ground})

    v_prev = {nd: 0.0 for nd in nodes}
    v_prev[ground] = 0.0
    i_ind = [0.0 for _ in inds]                    # inductor branch currents (state)

    times = [0.0]
    history: dict[str, list[float]] = {nd: [0.0] for nd in nodes}

    n_steps = int(round(t_end / dt))
    for step in range(1, n_steps + 1):
        companions: list[object] = []
        for c in caps:
            g = c.farads / dt
            companions.append(Resistor(c.a, c.b, 1.0 / g))
            # memory current: i_eq = g·V_prev(a,b), injected b -> a
            companions.append(CurrentSource(c.b, c.a, g * (v_prev[c.a] - v_prev[c.b])))
        for k, c in enumerate(inds):
            g = dt / c.henries
            companions.append(Resistor(c.a, c.b, 1.0 / g))
            # the previous inductor current is the companion source (a -> b)
            companions.append(CurrentSource(c.a, c.b, i_ind[k]))

        node_v, _ = solve_dc(linear + companions, ground)
        # advance inductor currents: i_n = i_{n-1} + (dt/L)·V_L
        for k, c in enumerate(inds):
            vl = node_v[c.a] - node_v[c.b]
            i_ind[k] = i_ind[k] + dt / c.henries * vl
        v_prev = {nd: node_v[nd] for nd in nodes}
        v_prev[ground] = 0.0
        times.append(step * dt)
        for nd in nodes:
            history[nd].append(node_v[nd])
    return times, history


def solve_ac(
    components, omega: float, ground: str = GROUND
) -> dict[str, complex]:
    """Solve the AC steady state at angular frequency `omega` [rad/s] by complex
    MNA. Reactive admittances are Y_C = jωC and Y_L = 1/(jωL); voltage sources are
    phasors (amplitude as a complex value, default phase 0). Returns the complex
    node voltage phasors (magnitude = amplitude, angle = phase). Deterministic.

    The frequency-domain counterpart of `solve_dc` (DC is the ω→0 special case for
    a purely resistive network). Raises ``ValueError`` on a non-finite or negative
    `omega`, on `omega == 0` when the circuit contains inductors (Y_L = 1/(jωL)
    would divide by zero — that operating point is `solve_dc`'s job), and on
    non-positive/non-finite component values.
    """
    if not math.isfinite(omega) or omega < 0.0:
        raise ValueError(f"omega must be finite and >= 0 rad/s, got {omega!r}")
    if omega == 0.0 and any(isinstance(c, Inductor) for c in components):
        raise ValueError(
            "omega must be > 0 when the circuit contains inductors "
            "(Y_L = 1/(jωL) is singular at ω = 0 — use solve_dc for the DC point)"
        )
    nodes = sorted({nd for c in components for nd in _nodes(c)} - {ground})
    idx = {nd: i for i, nd in enumerate(nodes)}
    vsources = [c for c in components if isinstance(c, VoltageSource)]
    n, m = len(nodes), len(vsources)

    A = np.zeros((n + m, n + m), dtype=complex)
    z = np.zeros(n + m, dtype=complex)

    def _stamp_admittance(a: str, b: str, y: complex) -> None:
        if a != ground:
            A[idx[a], idx[a]] += y
        if b != ground:
            A[idx[b], idx[b]] += y
        if a != ground and b != ground:
            A[idx[a], idx[b]] -= y
            A[idx[b], idx[a]] -= y

    for c in components:
        if isinstance(c, Resistor):
            _stamp_admittance(
                c.a, c.b, 1.0 / _positive_value(c.ohms, f"Resistor({c.a!r},{c.b!r}).ohms")
            )
        elif isinstance(c, Capacitor):
            _stamp_admittance(
                c.a, c.b,
                1j * omega * _positive_value(c.farads, f"Capacitor({c.a!r},{c.b!r}).farads"),
            )
        elif isinstance(c, Inductor):
            _stamp_admittance(
                c.a, c.b,
                1.0 / (1j * omega * _positive_value(
                    c.henries, f"Inductor({c.a!r},{c.b!r}).henries"
                )),
            )
        elif isinstance(c, CurrentSource):
            if c.frm != ground:
                z[idx[c.frm]] -= c.amps
            if c.to != ground:
                z[idx[c.to]] += c.amps

    for k, vs in enumerate(vsources):
        row = n + k
        if vs.p != ground:
            A[idx[vs.p], row] += 1.0
            A[row, idx[vs.p]] += 1.0
        if vs.n != ground:
            A[idx[vs.n], row] -= 1.0
            A[row, idx[vs.n]] -= 1.0
        z[row] = vs.volts

    x = np.linalg.solve(A, z)
    node_v = {nd: complex(x[idx[nd]]) for nd in nodes}
    node_v[ground] = 0.0 + 0.0j
    return node_v
