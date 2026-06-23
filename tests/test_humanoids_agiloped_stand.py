"""Tests for gen.humanoids.agiloped_stand — the wide-sole robust stand + push survival for AGILOped.

Runs REAL PyBullet on the inertia-repaired, no-parallel AGILOped URDF with the wider re-centred soles, so
they skip cleanly when PyBullet or the asset is absent. The asserted facts are the honest measured stand
outcomes: the wide-sole stand holds the full horizon AND survives a 0.3 m/s sagittal push (the prior
narrow-sole stand toppled on that exact push — the regression this hardening fixes).
"""

from __future__ import annotations

import os

import pytest

from gen.humanoids import agiloped_feet
from gen.humanoids import agiloped_stand as ast
from gen.humanoids import insim

_NOPAR = agiloped_feet.AGILOPED_NOPARALLEL_URDF
_have_pybullet = insim.pybullet_available()
_have_model = os.path.isfile(_NOPAR)

pytestmark = pytest.mark.skipif(
    not (_have_pybullet and _have_model),
    reason="PyBullet and/or the AGILOped no-parallel URDF not available",
)


def test_build_wide_feet_writes_urdf():
    out = ast.build_wide_feet()
    assert os.path.isfile(out)
    # the wide sole is 0.20 m fore-aft (vs the old 0.135) — assert the spec, not just file existence
    sx = {s.parent_link: s.size_x for s in ast.WIDE_FOOT_SPECS}
    assert sx["left_ankle_link"] == 0.200 and sx["right_ankle_link"] == 0.200


def test_wide_feet_static_stand_holds():
    wide = ast.build_wide_feet()
    r = ast.stand_with_push(wide, ast.ROBUST_STANDING_POSE, seconds=4.0, push_xy=(0.0, 0.0))
    assert r.held_full_horizon, f"static stand should hold; got {r.upright_seconds}s tilt {r.base_tilt_max_deg}"
    assert r.base_tilt_max_deg < 10.0


def test_wide_feet_survives_sagittal_push():
    # THE hardening result: a 0.3 m/s sagittal (fore-aft) push that the narrow sole could not survive
    wide = ast.build_wide_feet()
    fwd = ast.stand_with_push(wide, ast.ROBUST_STANDING_POSE, seconds=5.0, push_xy=(0.3, 0.0), push_at_s=2.0)
    back = ast.stand_with_push(wide, ast.ROBUST_STANDING_POSE, seconds=5.0, push_xy=(-0.3, 0.0), push_at_s=2.0)
    assert fwd.held_full_horizon, f"forward push: {fwd.upright_seconds}s tilt {fwd.base_tilt_max_deg}"
    assert back.held_full_horizon, f"backward push: {back.upright_seconds}s tilt {back.base_tilt_max_deg}"


def test_wide_feet_survives_lateral_push():
    wide = ast.build_wide_feet()
    r = ast.stand_with_push(wide, ast.ROBUST_STANDING_POSE, seconds=5.0, push_xy=(0.0, 0.3), push_at_s=2.0)
    assert r.held_full_horizon, f"lateral push: {r.upright_seconds}s tilt {r.base_tilt_max_deg}"


def test_push_result_is_deterministic():
    wide = ast.build_wide_feet()
    a = ast.stand_with_push(wide, ast.ROBUST_STANDING_POSE, seconds=4.0, push_xy=(0.3, 0.0), push_at_s=2.0)
    b = ast.stand_with_push(wide, ast.ROBUST_STANDING_POSE, seconds=4.0, push_xy=(0.3, 0.0), push_at_s=2.0)
    assert a.upright_seconds == b.upright_seconds
    assert a.base_tilt_max_deg == b.base_tilt_max_deg
