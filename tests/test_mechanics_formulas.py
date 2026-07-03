"""Anchors for the canonical rigid-body formulas — the single tested place each coefficient lives.

These pin the exact textbook values AND the parallel-axis identity that links the two rod inertias
(I_end = I_com + m·(L/2)²) — precisely the relationship two cross-model reviews found confused when
the formula was inlined. With one named, anchored definition, that confusion cannot recur.

Offline, stdlib only. Run:  pytest tests/test_mechanics_formulas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.mechanics_formulas import (  # noqa: E402
    parallel_axis_inertia,
    point_mass_inertia,
    rod_inertia_about_center,
    rod_inertia_about_end,
    solid_cylinder_inertia_axial,
)


def test_rod_inertia_about_center_is_mL2_over_12():
    """Uniform rod about its COM: m·L²/12. Hand value for m=2.0 kg, L=0.40 m → 0.0266667 kg·m²."""
    assert rod_inertia_about_center(2.0, 0.40) == pytest.approx(2.0 * 0.40**2 / 12.0)
    assert rod_inertia_about_center(2.0, 0.40) == pytest.approx(0.0266666667, rel=1e-7)


def test_rod_inertia_about_end_is_mL2_over_3():
    """Uniform rod about one end: m·L²/3. Hand value for m=2.0 kg, L=0.18 m → 0.0216 kg·m²
    (the leg's swing inertia about the hip — the exact number the demo spec must carry)."""
    assert rod_inertia_about_end(2.0, 0.18) == pytest.approx(2.0 * 0.18**2 / 3.0)
    assert rod_inertia_about_end(2.0, 0.18) == pytest.approx(0.0216, rel=1e-9)


def test_parallel_axis_links_the_two_rod_inertias():
    """The identity that was confused: about-end = about-COM shifted by the parallel-axis term with
    d = L/2. So rod_inertia_about_end(m, L) == parallel_axis_inertia(rod_about_center, m, L/2),
    and about-end is exactly 4× about-COM. Proven here so the two coefficients can never drift apart."""
    m, L = 3.5, 0.27
    i_com = rod_inertia_about_center(m, L)
    i_end = rod_inertia_about_end(m, L)
    assert i_end == pytest.approx(parallel_axis_inertia(i_com, m, L / 2.0))
    assert i_end == pytest.approx(4.0 * i_com)


def test_point_mass_and_cylinder_anchors():
    assert point_mass_inertia(2.0, 0.5) == pytest.approx(0.5)        # m·r² = 2·0.25
    assert solid_cylinder_inertia_axial(4.0, 0.1) == pytest.approx(0.02)  # ½·m·r² = 0.5·4·0.01


def test_negative_inputs_raise():
    for fn in (rod_inertia_about_center, rod_inertia_about_end, point_mass_inertia,
               solid_cylinder_inertia_axial):
        with pytest.raises(ValueError):
            fn(-1.0, 0.4)
        with pytest.raises(ValueError):
            fn(1.0, -0.4)
    with pytest.raises(ValueError):
        parallel_axis_inertia(-1.0, 1.0, 0.2)
