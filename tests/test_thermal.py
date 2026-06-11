"""Steady-state heat conduction FEM — exact against Fourier, plus the thermal DFM check.

The element is the thermal twin of the constant-strain tetrahedron: a linear
temperature field is reproduced EXACTLY, so 1-D conduction through a prismatic bar
must return Fourier's law Q = k·A·ΔT/L to machine precision on any mesh. The test
pins exactly that (the proof), then checks the closed-form helpers it validates and
the over-temperature DFM check, and a 2-D spreading case where the FEM gives a peak
no closed form does.

Offline, no LLM. Engine: numpy (pure, no mesher needed — the structured box mesh).

Run:  pytest tests/test_thermal.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.fem3d import structured_box_mesh  # noqa: E402
from gen.thermal import (  # noqa: E402
    _assemble_conduction_capacitance,
    conductive_temperature_rise,
    fourier_heat,
    overtemperature_check,
    peak_temperature,
    slowest_thermal_time_constant,
    solve_heat,
    solve_transient_heat,
    time_to_threshold,
)

_L, _B, _H, _K = 10.0, 2.0, 3.0, 0.2          # mm, mm, mm, W/(mm·K)
_AREA = _B * _H


def _bar(nx: int):
    return structured_box_mesh(_L, _B, _H, nx, 2, 2)


# --- exact against Fourier (the proof) -----------------------------------------

@pytest.mark.parametrize("nx", [3, 6, 12])
def test_prismatic_bar_temperature_field_is_exactly_linear(nx):
    nodes, tets = _bar(nx)
    t_hot = 50.0
    fixed = {}
    for i, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-9:
            fixed[i] = 0.0
        if abs(x - _L) < 1e-9:
            fixed[i] = t_hot
    temps, _ = solve_heat(nodes, tets, _K, fixed, {})
    exact = t_hot * nodes[:, 0] / _L                       # linear in x
    assert np.max(np.abs(temps - exact)) < 1e-9


def test_conducted_heat_matches_fourier_law_exactly():
    nodes, tets = _bar(6)
    t_hot = 50.0
    fixed = {}
    for i, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-9:
            fixed[i] = 0.0
        if abs(x - _L) < 1e-9:
            fixed[i] = t_hot
    _, reactions = solve_heat(nodes, tets, _K, fixed, {})
    cold = [i for i in fixed if abs(nodes[i, 0]) < 1e-9]
    q_out = -sum(reactions[i] for i in cold)               # heat leaving the cold face
    assert np.isclose(q_out, fourier_heat(_K, _AREA, _L, t_hot), rtol=1e-9)


# --- closed-form helpers (validated exact by the FEM above) ---------------------

def test_fourier_and_rise_are_inverses():
    power = 4.0
    dt = conductive_temperature_rise(power, _K, _AREA, _L)
    assert np.isclose(fourier_heat(_K, _AREA, _L, dt), power, rtol=1e-12)


def test_rise_rejects_nonpositive_geometry():
    for bad in (dict(area=0.0), dict(length=-1.0), dict(conductivity=0.0)):
        kw = dict(conductivity=_K, area=_AREA, length=_L)
        kw.update(bad)
        with pytest.raises(ValueError):
            conductive_temperature_rise(1.0, **kw)


# --- thermal DFM check ----------------------------------------------------------

def test_pla_heat_path_overheats_aluminium_does_not():
    # an LED dissipating 0.5 W through a 5 mm standoff of 20 mm^2 cross-section.
    power, area, length, ambient = 0.5, 20.0, 5.0, 25.0
    pla = overtemperature_check(power, 1.3e-4, area, length,         # PLA ~1.3e-4 W/mm.K
                                ambient=ambient, max_service_temp=60.0)
    al = overtemperature_check(power, 0.237, area, length,           # Al ~0.237 W/mm.K
                               ambient=ambient, max_service_temp=150.0)
    # PLA conducts heat ~1800x worse than aluminium: the path cannot be heat-sunk
    assert not pla["ok"] and pla["margin"] < 0.0 and pla["delta_t"] > 900.0
    assert al["ok"] and al["margin"] > 0.0 and al["delta_t"] < 1.0
    # peak = ambient + rise, by construction
    assert np.isclose(al["peak_temp"], ambient + al["delta_t"], rtol=1e-12)


# --- arbitrary geometry: a spreading field no closed form gives -----------------

def test_point_source_spreads_to_a_cooled_edge():
    # a 20x20x1 plate, the x=0 edge held at 0, a point heat source at the far edge:
    # the peak sits at the source and the field decays monotonically to the sink.
    nodes, tets = structured_box_mesh(20.0, 20.0, 1.0, 10, 10, 1)
    fixed = {i: 0.0 for i, (x, y, z) in enumerate(nodes) if abs(x) < 1e-9}
    src = int(np.argmin(np.linalg.norm(nodes - np.array([20.0, 10.0, 0.0]), axis=1)))
    mid = int(np.argmin(np.linalg.norm(nodes - np.array([10.0, 10.0, 0.0]), axis=1)))
    temps, reactions = solve_heat(nodes, tets, 0.5, fixed, {src: 2.0})
    assert int(np.argmax(temps)) == src                    # peak at the source
    assert temps[src] > temps[mid] > 1e-9                  # monotone decay to the sink
    assert np.isclose(temps.min(), 0.0, atol=1e-12)        # cooled edge held
    assert abs(sum(reactions.values()) + 2.0) < 1e-9       # energy conserved
    assert np.isclose(peak_temperature(nodes, tets, 0.5, fixed, {src: 2.0}), temps[src])


# --- guards & determinism -------------------------------------------------------

def test_no_heat_sink_is_an_error():
    nodes, tets = _bar(3)
    with pytest.raises(GeometryError):
        solve_heat(nodes, tets, _K, {}, {0: 1.0})          # pure-Neumann: singular


def test_is_deterministic():
    nodes, tets = _bar(4)
    fixed = {i: 0.0 for i, (x, y, z) in enumerate(nodes) if abs(x) < 1e-9}
    fixed.update({i: 40.0 for i, (x, y, z) in enumerate(nodes) if abs(x - _L) < 1e-9})
    a, _ = solve_heat(nodes, tets, _K, fixed, {})
    b, _ = solve_heat(nodes, tets, _K, fixed, {})
    assert np.array_equal(a, b)


# --- transient conduction (the time axis) --------------------------------------

# SI units for the transient checks (m, W/(m.K), J/(m^3.K), s)
_TL, _TK, _RHOC = 0.1, 50.0, 3.0e6
_ALPHA = _TK / _RHOC                              # thermal diffusivity
_TAU1 = 4.0 * _TL ** 2 / (np.pi ** 2 * _ALPHA)    # analytic first-mode time constant


def _tbar(nx):
    return structured_box_mesh(_TL, 0.02, 0.02, nx, 1, 1)


def test_capacitance_sums_to_body_heat_capacity():
    nodes, tets = _tbar(12)
    _, c = _assemble_conduction_capacitance(nodes, tets, _TK, _RHOC)
    assert np.isclose(c.sum(), _RHOC * _TL * 0.02 * 0.02, rtol=1e-12)


def test_transient_settles_to_the_steady_solution():
    nodes, tets = _tbar(12)
    fixed = {i: 0.0 for i, (x, y, z) in enumerate(nodes) if abs(x) < 1e-12}
    fixed.update({i: 80.0 for i, (x, y, z) in enumerate(nodes) if abs(x - _TL) < 1e-12})
    history = solve_transient_heat(nodes, tets, _TK, _RHOC, fixed, {},
                                   dt=5.0, n_steps=4000, initial_temp=0.0)
    steady, _ = solve_heat(nodes, tets, _TK, fixed, {})
    assert np.max(np.abs(history[-1] - steady)) < 1e-9     # t->inf equals the steady solve


def test_slowest_time_constant_converges_to_the_analytic_bar_mode():
    errs = []
    for nx in (8, 16):
        nodes, tets = _tbar(nx)
        fixed = {i: 0.0 for i, (x, y, z) in enumerate(nodes) if abs(x) < 1e-12}
        tau = slowest_thermal_time_constant(nodes, tets, _TK, _RHOC, fixed)
        errs.append(abs(tau - _TAU1) / _TAU1)
    assert errs[-1] < 0.03                                  # ~2% at nx=16
    assert errs[-1] < errs[0]                               # refining converges (from below)


def test_transient_rises_monotonically_and_reaches_a_threshold():
    nodes, tets = _tbar(10)
    # sink the x=0 end at 0 and INJECT heat at the far end -> the part warms up over
    # time from 0 toward its steady temperature (a real "component dissipating power").
    fixed = {i: 0.0 for i, (x, y, z) in enumerate(nodes) if abs(x) < 1e-12}
    far = [i for i, (x, y, z) in enumerate(nodes) if abs(x - _TL) < 1e-12]
    loads = {i: 60.0 / len(far) for i in far}              # 60 W total into the far end
    steady_peak = solve_heat(nodes, tets, _TK, fixed, loads)[0].max()
    dt = _TAU1 / 50.0
    history = solve_transient_heat(nodes, tets, _TK, _RHOC, fixed, loads,
                                   dt=dt, n_steps=400, initial_temp=0.0)
    peaks = history.max(axis=1)
    assert np.all(np.diff(peaks) >= -1e-9)                  # monotone non-decreasing
    assert peaks[0] == 0.0 and peaks[-1] > 0.5 * steady_peak
    # it crosses a sub-steady threshold at a finite time, but never exceeds steady
    t_hit = time_to_threshold(history, dt, 0.5 * steady_peak)
    assert t_hit is not None and 0.0 < t_hit <= 400 * dt
    assert time_to_threshold(history, dt, 2.0 * steady_peak) is None


def test_transient_guards():
    nodes, tets = _tbar(3)
    fixed = {i: 0.0 for i, (x, y, z) in enumerate(nodes) if abs(x) < 1e-12}
    with pytest.raises(ValueError):
        solve_transient_heat(nodes, tets, _TK, _RHOC, fixed, {},
                             dt=0.0, n_steps=1, initial_temp=0.0)
    with pytest.raises(GeometryError):
        slowest_thermal_time_constant(nodes, tets, _TK, _RHOC, {})   # no sink
