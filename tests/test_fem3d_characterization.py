"""Characterization: fem3d genuinely computes deflection/stress from load + geometry.

This is a facade-detector, not a smoke test. A hollow FEM that returned canned
constants would pass `test_fem3d.py` only if those constants happened to match one
fixed case — but it could NOT reproduce the *scaling laws* of linear elasticity for
a prismatic bar pulled along x by a force F:

    σ_xx = F / A                (mean axial stress, exact by equilibrium)
    δ    = F · L / (A · E)      (end deflection, exact for the uniform field)

with A = width·height. So we drive `prismatic_bar_axial_response` (a real call into
`solve_elasticity`, no mocking of the unit under test) and assert the response is
SENSITIVE to its inputs in exactly the way the physics dictates:

  * linear in force F  — double F ⇒ double σ and δ (exact, it is a linear system);
  * stress per 1/A     — halve the area ⇒ σ doubles; σ is independent of length L;
  * deflection per L/A  — longer ⇒ proportionally larger δ; thinner ⇒ larger δ.

If `solve_elasticity` ignored load or geometry, these ratios would collapse to 1 and
the test fails — that is the whole point.

Offline, numpy only, deterministic.

Run:  pytest tests/test_fem3d_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.fem3d import (  # noqa: E402
    PrismaticBarResponse,
    prismatic_bar_axial_response,
)

E, NU = 210000.0, 0.3
BASE_L, BASE_W, BASE_H = 10.0, 2.0, 2.0
BASE_F = 1000.0

# The end-face deflection carries a small load-application end effect from the
# coarse (2x2) cross-section, so geometry ratios land near the ideal factor but
# not to machine precision. 5% cleanly separates "scales with geometry" (~2.0)
# from "ignores geometry" (1.0) — the facade we want to reject.
GEOM_RTOL = 0.05


def _base() -> PrismaticBarResponse:
    return prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, NU, BASE_F)


def test_stress_equals_F_over_A_exactly():
    """The mean axial stress is the computed F/A, not a constant."""
    r = _base()
    assert math.isclose(r.axial_stress, BASE_F / (BASE_W * BASE_H), rel_tol=1e-9)


def test_deflection_tracks_FL_over_AE():
    """End deflection matches the closed form F·L/(A·E) within the end-effect band,
    proving δ is computed from E, L and A — not canned."""
    r = _base()
    closed = BASE_F * BASE_L / (BASE_W * BASE_H * E)
    assert math.isclose(r.axial_deflection, closed, rel_tol=GEOM_RTOL)
    assert r.axial_deflection > 0.0


def test_stress_and_deflection_scale_linearly_with_force():
    """Linear system ⇒ both outputs scale EXACTLY with the applied force."""
    r1 = prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, NU, BASE_F)
    r2 = prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, NU, 2.0 * BASE_F)
    assert math.isclose(r2.axial_stress, 2.0 * r1.axial_stress, rel_tol=1e-9)
    assert math.isclose(r2.axial_deflection, 2.0 * r1.axial_deflection, rel_tol=1e-9)
    # zero force ⇒ zero response (no spurious offset constant).
    r0 = prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, NU, 0.0)
    assert math.isclose(r0.axial_stress, 0.0, abs_tol=1e-9)
    assert math.isclose(r0.axial_deflection, 0.0, abs_tol=1e-9)


def test_longer_specimen_deflects_proportionally_more():
    """Deflection ∝ L: double the length ⇒ ~double the deflection, while the
    stress stays F/A (independent of length). Mesh density per length is held
    constant so element shape does not confound the ratio."""
    short = prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, NU, BASE_F,
                                         nx=10, ny=2, nz=2)
    long = prismatic_bar_axial_response(2.0 * BASE_L, BASE_W, BASE_H, E, NU, BASE_F,
                                        nx=20, ny=2, nz=2)
    assert math.isclose(long.axial_deflection, 2.0 * short.axial_deflection,
                        rel_tol=GEOM_RTOL)
    # stress is geometry-of-length independent: same F, same A ⇒ same σ.
    assert math.isclose(long.axial_stress, short.axial_stress, rel_tol=1e-9)


def test_thinner_specimen_carries_proportionally_more_stress_and_deflection():
    """Stress and deflection ∝ 1/A: halve the cross-section ⇒ both ~double."""
    full = _base()
    # shrink each transverse dimension by 1/sqrt(2) ⇒ area halved.
    thin = prismatic_bar_axial_response(
        BASE_L, BASE_W / math.sqrt(2.0), BASE_H / math.sqrt(2.0), E, NU, BASE_F,
    )
    assert math.isclose(thin.axial_stress, 2.0 * full.axial_stress, rel_tol=1e-6)
    assert math.isclose(thin.axial_deflection, 2.0 * full.axial_deflection,
                        rel_tol=GEOM_RTOL)


def test_guards_raise_on_degenerate_inputs():
    """Fail-loud, not silent-wrong, on non-physical geometry/material."""
    with pytest.raises(ValueError):
        prismatic_bar_axial_response(0.0, BASE_W, BASE_H, E, NU, BASE_F)   # L = 0
    with pytest.raises(ValueError):
        prismatic_bar_axial_response(BASE_L, -1.0, BASE_H, E, NU, BASE_F)  # W < 0
    with pytest.raises(ValueError):
        prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, 0.0, NU, BASE_F)  # E = 0
    with pytest.raises(ValueError):
        prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, 0.5, BASE_F)   # nu = 0.5
    with pytest.raises(ValueError):
        prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, -1.0, BASE_F)  # nu = -1


# --- property-based invariants -------------------------------------------------
# The exact σ = F/A law is an invariant over the whole (force, geometry) space,
# not just the hand-picked cases above. Hypothesis explores it.

@settings(max_examples=40, deadline=None)
@given(
    force=st.floats(min_value=-5000.0, max_value=5000.0),
    width=st.floats(min_value=0.5, max_value=5.0),
    height=st.floats(min_value=0.5, max_value=5.0),
    length=st.floats(min_value=4.0, max_value=40.0),
)
def test_property_mean_stress_is_force_over_area(force, width, height, length):
    area = width * height
    r = prismatic_bar_axial_response(length, width, height, E, NU, force)
    assert math.isclose(r.axial_stress, force / area, rel_tol=1e-6, abs_tol=1e-9)


@settings(max_examples=30, deadline=None)
@given(scale=st.floats(min_value=0.1, max_value=8.0))
def test_property_force_scaling_is_exactly_linear(scale):
    """For any positive scale c: response(c·F) == c·response(F) (a linear system)."""
    r1 = prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, NU, BASE_F)
    rc = prismatic_bar_axial_response(BASE_L, BASE_W, BASE_H, E, NU, scale * BASE_F)
    assert np.isclose(rc.axial_stress, scale * r1.axial_stress, rtol=1e-9, atol=1e-9)
    assert np.isclose(rc.axial_deflection, scale * r1.axial_deflection,
                      rtol=1e-9, atol=1e-9)
