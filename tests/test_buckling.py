"""Euler column buckling — the FEM eigenproblem cross-checked against the closed form.

The computed buckling load (beam-element geometric-stiffness eigenproblem) must agree
with Euler's P_cr = π²EI/(KL)² for ALL four classic end conditions — two independent
methods agreeing. The design check is honest about WHEN Euler governs: a stocky column
yields before it buckles, so the governing failure is the smaller of the Euler load
and the squash load.

Offline, no LLM, pure numpy (no mesher).

Run:  pytest tests/test_buckling.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.buckling import (  # noqa: E402
    END_CONDITION_FACTORS,
    buckling_check,
    critical_buckling_load,
    euler_critical_load,
    radius_of_gyration,
)

_E, _I, _L = 210000.0, 100.0, 1000.0          # MPa, mm^4, mm


# --- the FEM matches the Euler closed form (defense in depth) -------------------

@pytest.mark.parametrize("end_condition,k", sorted(END_CONDITION_FACTORS.items()))
def test_fem_buckling_matches_euler(end_condition, k):
    fem = critical_buckling_load(_E, _I, _L, end_condition=end_condition, n_elements=8)
    closed = euler_critical_load(_E, _I, _L, k_factor=k)
    assert abs(fem - closed) / closed < 3e-3       # < 0.3% with 8 elements


def test_buckling_converges_with_refinement():
    closed = euler_critical_load(_E, _I, _L, k_factor=0.5)   # fixed-fixed (largest error)
    coarse = critical_buckling_load(_E, _I, _L, end_condition="fixed-fixed", n_elements=2)
    fine = critical_buckling_load(_E, _I, _L, end_condition="fixed-fixed", n_elements=8)
    assert abs(fine - closed) < abs(coarse - closed)         # refining converges
    assert fine > closed                                     # discrete model is stiffer


def test_end_condition_factor_physics():
    # fixed-free (K=2) is exactly 1/4 as strong as pinned-pinned (K=1): P_cr ~ 1/K^2
    pp = euler_critical_load(_E, _I, _L, k_factor=1.0)
    ff = euler_critical_load(_E, _I, _L, k_factor=2.0)
    assert np.isclose(ff, pp / 4.0)
    # and the FEM reproduces that ratio
    pp_fem = critical_buckling_load(_E, _I, _L, end_condition="pinned-pinned")
    ff_fem = critical_buckling_load(_E, _I, _L, end_condition="fixed-free")
    assert abs(ff_fem / pp_fem - 0.25) < 5e-3


# --- the design check: buckling vs yield governs --------------------------------

def _square(side):
    area = side * side
    inertia = side ** 4 / 12.0
    return area, inertia


def test_slender_strut_buckles_before_it_yields():
    area, inertia = _square(10.0)                 # 10x10 mm, r = 2.887 mm
    length = 350.0                                # slenderness ~121 > transition ~91
    r = buckling_check(5000.0, _E, inertia, length, area,
                       end_condition="pinned-pinned", yield_strength=250.0)
    assert r["governs"] == "buckling"
    assert r["slenderness"] > r["transition_slenderness"]
    assert r["p_euler"] < r["squash_load"]        # Euler load below the squash load
    assert r["ok"] and r["safety_factor"] > 1.0   # 5 kN is safe here


def test_stocky_column_yields_before_it_buckles():
    area, inertia = _square(10.0)
    length = 100.0                                # slenderness ~35 < transition ~91
    r = buckling_check(5000.0, _E, inertia, length, area,
                       end_condition="pinned-pinned", yield_strength=250.0)
    assert r["governs"] == "yield"
    assert r["slenderness"] < r["transition_slenderness"]
    assert np.isclose(r["governing_load"], 250.0 * area)      # squash load governs
    assert r["p_euler"] > r["squash_load"]                    # Euler would over-predict


def test_safety_factor_flags_overload():
    area, inertia = _square(10.0)
    safe = buckling_check(1000.0, _E, inertia, 350.0, area, end_condition="pinned-pinned")
    over = buckling_check(50000.0, _E, inertia, 350.0, area, end_condition="pinned-pinned")
    assert safe["ok"] and safe["safety_factor"] > 1.0
    assert not over["ok"] and over["safety_factor"] < 1.0


# --- guards & determinism ------------------------------------------------------

def test_radius_of_gyration_and_guards():
    assert np.isclose(radius_of_gyration(100.0, 4.0), 5.0)    # sqrt(I/A)
    with pytest.raises(ValueError):
        radius_of_gyration(100.0, 0.0)
    with pytest.raises(ValueError):
        buckling_check(-1.0, _E, _I, _L, 100.0)


def test_unknown_end_condition_errors():
    with pytest.raises(GeometryError):
        critical_buckling_load(_E, _I, _L, end_condition="clamped-springy")
    with pytest.raises(GeometryError):
        buckling_check(1000.0, _E, _I, _L, 100.0, end_condition="nope")


def test_is_deterministic():
    a = critical_buckling_load(_E, _I, _L, end_condition="fixed-pinned", n_elements=6)
    b = critical_buckling_load(_E, _I, _L, end_condition="fixed-pinned", n_elements=6)
    assert a == b
