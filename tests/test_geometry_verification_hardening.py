"""Hardened geometry cross-check (D15) — lower bound, rotation containment, kernel guards.

Three false-verdict classes are pinned here:
  1. NON-EXACT VOLUME had no lower bound: a hemisphere-class bug (half the volume) slipped
     through whenever ``volume_of`` was only an upper bound. Now `lower - tol <= brep` fails it.
  2. ROTATION AABBs are conservative (a sound SUPERSET for non-quarter-turns) — comparing them
     with isclose produced FALSE NEGATIVES on perfectly correct rotated parts. Now a non-exact
     analytic box is checked by CONTAINMENT (brep extent <= analytic extent + tol) per axis.
  3. Kernel calls (isValid/Volume/BoundingBox) could raise raw OCCT errors — now they are
     translated to GeometryError with context (fail-loud, consistent with brep.py).

These tests run WITHOUT cadquery: the BREP side is a stub patched over
``gen.geometry_verification.csg_to_solid``, so the checking LOGIC is pinned independently of
the optional CAD kernel. Offline, deterministic, no LLM.

Run:  pytest tests/test_geometry_verification_hardening.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

import gen.geometry_verification as gv  # noqa: E402
from gen.core.errors import GeometryError  # noqa: E402
from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402


def _q(qid: str, v: float) -> Quantity:
    return Quantity(id=qid, name=qid, value=v, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="t")


def _qs(*pairs) -> dict[str, Quantity]:
    return {qid: _q(qid, v) for qid, v in pairs}


class _FakeBB:
    """A bounding box with the cadquery attribute surface, centered at the origin."""

    def __init__(self, ex: float, ey: float, ez: float):
        self.xmin, self.xmax = -ex / 2.0, ex / 2.0
        self.ymin, self.ymax = -ey / 2.0, ey / 2.0
        self.zmin, self.zmax = -ez / 2.0, ez / 2.0


class _FakeSolid:
    """A stub solid with the three kernel calls verify_geometry makes."""

    def __init__(self, volume: float, extent: tuple[float, float, float],
                 valid: bool = True, raise_on: str | None = None):
        self._volume = volume
        self._extent = extent
        self._valid = valid
        self._raise_on = raise_on

    def _maybe_raise(self, name: str) -> None:
        if self._raise_on == name:
            raise RuntimeError(f"OCCT blew up in {name}")

    def isValid(self):  # noqa: N802 - cadquery API name
        self._maybe_raise("isValid")
        return self._valid

    def Volume(self):  # noqa: N802 - cadquery API name
        self._maybe_raise("Volume")
        return self._volume

    def BoundingBox(self):  # noqa: N802 - cadquery API name
        self._maybe_raise("BoundingBox")
        return _FakeBB(*self._extent)


def _patch(monkeypatch, solid: _FakeSolid) -> None:
    # Force in-process path so a developer machine with .venv-cad does not
    # bypass the stub via cadquery_bridge (CI has no cad venv either way).
    monkeypatch.setattr(gv, "_in_process_cadquery", lambda: True)
    monkeypatch.setattr(gv, "csg_to_solid", lambda node, quantities: solid)


def _inexact_difference() -> tuple[GeometryNode, dict]:
    # cylinder (r=10, h=10) minus a small contained sphere (r=1): volume_of is NOT
    # exact (minuend is not a box) -> upper = pi*1000, lower = pi*1000 - 4/3*pi
    node = GeometryNode(kind="difference", children=[
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"}),
        GeometryNode(kind="sphere", params={"radius": "sr"}),
    ])
    return node, _qs(("r", 10.0), ("h", 10.0), ("sr", 1.0))


# --- 1. the non-exact path now has teeth (lower bound) ---------------------------

def test_hemisphere_class_bug_fails_even_on_the_non_exact_path(monkeypatch):
    # NEGATIVTEST: a BREP volume of HALF the true value used to pass the old
    # one-sided check (half <= upper bound). The sound lower bound catches it.
    node, q = _inexact_difference()
    _patch(monkeypatch, _FakeSolid(volume=0.5 * math.pi * 1000.0, extent=(20.0, 20.0, 10.0)))
    r = gv.verify_geometry(node, q)
    assert not r["volume_ok"] and not r["ok"]
    assert r["analytic_volume_lower"] == pytest.approx(math.pi * 1000.0 - (4 / 3) * math.pi)


def test_a_volume_within_the_sound_bracket_passes(monkeypatch):
    node, q = _inexact_difference()
    true_volume = math.pi * 1000.0 - (4 / 3) * math.pi  # inside [lower, upper]
    _patch(monkeypatch, _FakeSolid(volume=true_volume, extent=(20.0, 20.0, 10.0)))
    r = gv.verify_geometry(node, q)
    assert r["volume_ok"] and r["ok"]
    assert not r["analytic_exact"]


def test_a_volume_above_the_upper_bound_still_fails(monkeypatch):
    node, q = _inexact_difference()
    _patch(monkeypatch, _FakeSolid(volume=2.0 * math.pi * 1000.0, extent=(20.0, 20.0, 10.0)))
    assert not gv.verify_geometry(node, q)["volume_ok"]


# --- 2. rotated parts: containment instead of isclose (false-negative fix) -------

def _rotated_cylinder() -> tuple[GeometryNode, dict]:
    # cylinder (r=5, h=20) rotated 45 deg about z: the SOLID is invariant (true bbox
    # 10 x 10 x 20) but the analytic AABB is the conservative corner re-box
    # (10*sqrt(2) x 10*sqrt(2) x 20) — a sound superset, not the tight box.
    node = GeometryNode(
        kind="rotate",
        params={"axis_x": "ax", "axis_y": "ay", "axis_z": "az", "angle_deg": "ang"},
        children=[GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})],
    )
    return node, _qs(("r", 5.0), ("h", 20.0), ("ax", 0.0), ("ay", 0.0), ("az", 1.0), ("ang", 45.0))


def test_correct_rotated_cylinder_is_no_longer_a_false_negative(monkeypatch):
    node, q = _rotated_cylinder()
    _patch(monkeypatch, _FakeSolid(volume=math.pi * 25.0 * 20.0, extent=(10.0, 10.0, 20.0)))
    r = gv.verify_geometry(node, q)
    assert not r["analytic_extent_exact"]     # the analytic box is only a superset
    assert r["extent_ok"] and r["ok"]          # containment, not isclose -> passes


def test_an_extent_exceeding_the_conservative_bound_still_fails(monkeypatch):
    # soundness direction kept: bigger than the superset is provably wrong
    node, q = _rotated_cylinder()
    too_big = 10.0 * math.sqrt(2.0) + 1.0
    _patch(monkeypatch, _FakeSolid(volume=math.pi * 25.0 * 20.0, extent=(too_big, 10.0, 20.0)))
    r = gv.verify_geometry(node, q)
    assert not r["extent_ok"] and not r["ok"]


def test_exact_analytic_boxes_still_use_the_tight_isclose_check(monkeypatch):
    # a sphere's analytic AABB is exact: an undersized BREP box must STILL fail
    # (containment alone would wrongly accept it)
    node = GeometryNode(kind="sphere", params={"radius": "r"})
    q = _qs(("r", 5.0))
    _patch(monkeypatch, _FakeSolid(volume=(4 / 3) * math.pi * 125.0, extent=(6.0, 10.0, 10.0)))
    r = gv.verify_geometry(node, q)
    assert r["analytic_extent_exact"]
    assert not r["extent_ok"] and not r["ok"]


# --- 3. kernel-call guards (fail-loud GeometryError, never a raw OCCT crash) -----

@pytest.mark.parametrize("call", ["isValid", "Volume", "BoundingBox"])
def test_kernel_crashes_are_translated_to_geometry_error(monkeypatch, call):
    node = GeometryNode(kind="sphere", params={"radius": "r"})
    q = _qs(("r", 5.0))
    _patch(monkeypatch, _FakeSolid(volume=(4 / 3) * math.pi * 125.0,
                                   extent=(10.0, 10.0, 10.0), raise_on=call))
    with pytest.raises(GeometryError, match=call):
        gv.verify_geometry(node, q)
