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
    conductive_temperature_rise,
    fourier_heat,
    overtemperature_check,
    peak_temperature,
    solve_heat,
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
