"""The dimensional guard, applied: each input-homogeneous closed-form check keeps its dimensionless
safety_factor INVARIANT under a coherent change of base units — an automatic detector of dimensional
formula errors (wrong power, mixed terms, a rogue dimensional constant) that needs no per-formula
anchor. A deliberately dimension-mixing control proves the guard is NOT vacuous: it fires.

This is the systematic net for the dimensional class of formula bug; wrong dimensionless coefficients
(m·L²/3 vs /12) are caught by the canonical mechanics_formulas anchors instead — the two together
cover the spectrum that per-value anchors alone let slip.

Offline, stdlib + in-repo units only. Run:  pytest tests/test_dimensional_invariance.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.actuation import (  # noqa: E402
    electric_actuator_check,
    hydraulic_cylinder_check,
    hydraulic_flow_check,
)
from gen.dimensional_guard import (  # noqa: E402
    DimensionalInconsistencyError,
    assert_scale_invariant,
    scale_invariance_report,
)

# (validator, {arg: (value, unit)}) — each homogeneous in its declared inputs, so its dimensionless
# safety_factor must survive a coherent unit rescaling. Units are the ones the recipes already carry.
HOMOGENEOUS_CHECKS = [
    ("electric_actuator", electric_actuator_check, {
        "joint_torque": (28.0, "N*m"), "joint_speed": (3.0, "rad/s"),
        "motor_stall_torque": (2.0, "N*m"), "motor_noload_speed": (300.0, "rad/s"),
        "gear_ratio": (40.0, "1"), "efficiency": (0.85, "1")}),
    ("hydraulic_cylinder", hydraulic_cylinder_check, {
        "pressure": (2.0e7, "Pa"), "bore_area": (1.0e-3, "m^2"),
        "required_force": (1500.0, "N"), "friction": (50.0, "N")}),
    ("hydraulic_flow", hydraulic_flow_check, {
        "bore_area": (1.0e-3, "m^2"), "piston_velocity": (0.1, "m/s"),
        "pump_flow": (2.0e-4, "m^3/s")}),
]


@pytest.mark.parametrize("name,fn,inputs", HOMOGENEOUS_CHECKS, ids=[c[0] for c in HOMOGENEOUS_CHECKS])
def test_check_is_dimensionally_homogeneous(name, fn, inputs):
    """The dimensionless safety_factor does not move when every input is re-expressed in a coherently
    rescaled unit system — proof the formula mixes no dimensions."""
    rep = assert_scale_invariant(fn, inputs)
    assert rep["rel_change"] < 1e-9


def test_guard_fires_on_a_dimensionally_broken_formula():
    """Non-vacuity: a check that ADDS an area to a force (incommensurable) is not scale-invariant —
    the guard catches it. If this passed, the guard would be proving nothing."""
    def broken(force_n: float, area_m2: float) -> dict:
        # nonsense: N + m^2 — dimensionally illegal; the sum scales differently than `force_n` alone
        return {"safety_factor": (force_n + area_m2) / force_n}

    rep = scale_invariance_report(broken, {"force_n": (100.0, "N"), "area_m2": (5.0, "m^2")})
    assert not rep["invariant"]
    with pytest.raises(DimensionalInconsistencyError):
        assert_scale_invariant(broken, {"force_n": (100.0, "N"), "area_m2": (5.0, "m^2")})


def test_a_correct_dimensionless_ratio_is_invariant():
    """Sanity: a genuinely homogeneous ad-hoc ratio (force/force) is invariant, so the guard does not
    cry wolf on correct formulas."""
    def ok_ratio(have_n: float, need_n: float) -> dict:
        return {"safety_factor": have_n / need_n}

    rep = scale_invariance_report(ok_ratio, {"have_n": (300.0, "N"), "need_n": (100.0, "N")})
    assert rep["invariant"] and rep["rel_change"] < 1e-12
