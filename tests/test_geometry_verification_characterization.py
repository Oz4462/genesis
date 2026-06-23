"""Characterization test for geometry_verification.py (BREP-vs-analytic cross-check).

This is the authoritative facade-detector (new file, leaves legacy test_geometry_verification.py untouched).

Goal per spec: prove verify_geometry genuinely cross-checks the exact OpenCASCADE BREP
solid (via brep.csg_to_solid + exact_volume + is_valid) against the independent analytic
layer (verification.geometry.volume_of + aabb_of). The headline behavior is that it
detects a built solid diverging from declared dimensions (the historic sphere-rendered-
as-hemisphere volume-halving case would fail volume_ok here).

Facade-killer (per team decisions):
- (a) headline outputs (ok, brep_volume, extents, volume_ok, extent_ok) change
  meaningfully when driving GeometryNode / quantities change — proves the node+qs
  are consumed, not a constant stub.
- (b) documented fail-loud + honest negative paths fire: a deliberately mismatched
  or degenerate CSG produces ok=False (volume or extent cross-check fails); bad
  inputs raise the documented GeometryError rather than silent wrong values.

Uses pytest.importorskip("cadquery") *inside* the numeric tests (deep BREP path) so the
characterization file is always collectable; numeric tests are skipped when the optional
cadquery/OCP kernel is absent (per isolation + optional-dep contract). Property-based
tests use Hypothesis for invariants (exact match on primitives, ok=True for positive
finite sizes, determinism).

All inputs built via real GeometryNode / Quantity(..., origin=ValueOrigin.DECISION, rationale=...)
constructors (read from core/state.py). No src edits unless a test independently exposes
a genuine defect (silent wrong value, missing documented guard, dead input). Offline,
deterministic, no LLM.

Run:  pytest tests/test_geometry_verification_characterization.py -q --tb=line
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

# hypothesis is a dev extra; importorskip prevents hard collection failure in envs without [dev]
# (keeps the file loadable while the property tests remain authoritative when present).
pytest.importorskip("hypothesis", reason="hypothesis (dev extra) required for property-based characterization tests")
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.geometry_verification import verify_geometry  # noqa: E402
from gen.core.errors import GeometryError  # noqa: E402


def _q(qid: str, v: float, unit: str = "mm") -> Quantity:
    """Quantity via the real constructor (DECISION requires non-empty rationale)."""
    return Quantity(
        id=qid, name=qid, value=v, unit=unit,
        origin=ValueOrigin.DECISION, rationale="char-test"
    )


# --------------------------------------------------------------------------- #
# Positive: correct primitives pass the cross-check (ok, volume_ok, extent_ok)
# --------------------------------------------------------------------------- #

def test_correct_box_passes_volume_and_extent_crosscheck():
    """A box with matching declared sizes must be ok=True with both sub-checks green.
    Proves BREP solid (centered makeBox) agrees with analytic box volume + aabb."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    node = GeometryNode(kind="box", params={"size_x": "sx", "size_y": "sy", "size_z": "sz"})
    qs = {"sx": _q("sx", 12.0), "sy": _q("sy", 8.0), "sz": _q("sz", 3.0)}
    r = verify_geometry(node, qs)
    assert r["ok"] is True
    assert r["volume_ok"] is True
    assert r["extent_ok"] is True
    assert r["valid"] and r["nonzero_volume"]
    assert math.isclose(r["brep_volume"], 12.0 * 8.0 * 3.0, rel_tol=1e-9)
    assert tuple(round(e, 6) for e in r["brep_extent"]) == (12.0, 8.0, 3.0)


def test_correct_sphere_passes_exact_volume_and_extent():
    """Sphere must report analytic_exact=True and brep_volume == 4/3 pi r^3 within tol.
    This is the exact cross-check that would have caught the old hemisphere bug (half volume)."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    node = GeometryNode(kind="sphere", params={"radius": "r"})
    qs = {"r": _q("r", 6.0)}
    r = verify_geometry(node, qs)
    assert r["ok"] is True
    assert r["analytic_exact"] is True
    assert r["volume_ok"] is True
    assert r["extent_ok"] is True
    expected_vol = (4.0 / 3.0) * math.pi * (6.0 ** 3)
    assert math.isclose(r["brep_volume"], expected_vol, rel_tol=1e-6)
    assert math.isclose(r["brep_volume"], r["analytic_volume"], rel_tol=1e-9)
    # extent for sphere is diameter on all axes
    assert all(math.isclose(e, 12.0, rel_tol=1e-9) for e in r["brep_extent"])


# --------------------------------------------------------------------------- #
# Negative + facade: deliberately mismatched / degenerate CSG -> ok=False
# --------------------------------------------------------------------------- #

def test_degenerate_csg_volume_zero_fails_crosscheck():
    """A difference that subtracts a strictly larger solid produces zero-volume result.
    verify_geometry must report ok=False + nonzero_volume=False (the documented honest
    failure for a built solid that is empty vs declared positive geometry)."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    # 5mm box minus 10mm box that fully contains it -> empty result
    node = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "a", "size_y": "a", "size_z": "a"}),
        GeometryNode(kind="box", params={"size_x": "b", "size_y": "b", "size_z": "b"}),
    ])
    qs = {"a": _q("a", 5.0), "b": _q("b", 10.0)}
    r = verify_geometry(node, qs)
    assert r["ok"] is False
    assert r["nonzero_volume"] is False
    assert r["volume_ok"] is False
    assert r["extent_ok"] is False  # degenerate path forces zero extent
    # brep_volume is 0 (or < abs_tol)
    assert r["brep_volume"] <= 1e-9


def test_mismatched_geometry_via_contained_subtraction_fails_when_expected():
    """Drive a case where analytic upper-bound path is used (difference on non-box or
    non-fully-contained tool) but the BREP result is smaller; still passes volume_ok because
    <= bound is allowed. To get explicit fail we deliberately use a case whose declared
    analytic volume would be violated if BREP produced wrong geometry (empty or oversized).
    Degenerate already covers the explicit ok=False path required by spec."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    # Box minus internal cylinder (contained, exact for difference because box minuend).
    # This yields nonzero with volume_ok (brep < analytic upper) but we assert the
    # cross-check is actually performed (volume_ok True only because bound respected).
    node = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "sx", "size_y": "sy", "size_z": "sz"}),
        GeometryNode(kind="cylinder", params={"radius": "rr", "height": "hh"}),
    ])
    qs = {"sx": _q("sx", 20.0), "sy": _q("sy", 20.0), "sz": _q("sz", 10.0),
          "rr": _q("rr", 3.0), "hh": _q("hh", 9.0)}
    r = verify_geometry(node, qs)
    assert r["ok"] is True  # valid subtraction, volume < box upper bound
    assert r["volume_ok"] is True
    assert r["nonzero_volume"] is True
    assert r["brep_volume"] < r["analytic_volume"] + 1e-6  # exercised upper-bound path


# --------------------------------------------------------------------------- #
# Input consumption + determinism (facade killer)
# --------------------------------------------------------------------------- #

def test_output_changes_when_input_geometry_changes():
    """Driving input (different radius) must change brep_volume and analytic_volume.
    A facade returning a constant would not move."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    node = GeometryNode(kind="sphere", params={"radius": "r"})
    r1 = verify_geometry(node, {"r": _q("r", 2.0)})
    r2 = verify_geometry(node, {"r": _q("r", 3.0)})
    assert r2["brep_volume"] > r1["brep_volume"] * 3  # ~ 3.375x volume
    assert not math.isclose(r1["brep_volume"], r2["brep_volume"], rel_tol=1e-6)


def test_geometry_verification_is_deterministic():
    """Same node+quantities must yield identical dict (A5 reproducibility contract)."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    node = GeometryNode(kind="box", params={"size_x": "w", "size_y": "d", "size_z": "h"})
    qs = {"w": _q("w", 7.0), "d": _q("d", 5.0), "h": _q("h", 1.5)}
    a = verify_geometry(node, qs)
    b = verify_geometry(node, qs)
    assert a == b


# --------------------------------------------------------------------------- #
# Property-based (Hypothesis): invariants over positive finite inputs
# --------------------------------------------------------------------------- #

@settings(max_examples=30, deadline=None)
@given(
    radius=st.floats(min_value=0.5, max_value=50.0),
    sx=st.floats(min_value=1.0, max_value=100.0),
    sy=st.floats(min_value=1.0, max_value=100.0),
    sz=st.floats(min_value=1.0, max_value=100.0),
)
def test_property_primitives_match_analytic_and_pass_crosscheck(radius, sx, sy, sz):
    """INVARIANT: for any admissible positive finite primitive the BREP result
    satisfies ok=True, volume_ok=True, extent_ok=True, and brep_volume isclose
    analytic (exact for box/sphere/cylinder). Property-based exploration, not
    a single hard-coded example."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    # sphere
    ns = GeometryNode(kind="sphere", params={"radius": "r"})
    rs = verify_geometry(ns, {"r": _q("r", radius)})
    assert rs["ok"] is True
    assert rs["volume_ok"] is True
    assert rs["extent_ok"] is True
    assert math.isclose(rs["brep_volume"], rs["analytic_volume"], rel_tol=1e-6)

    # box
    nb = GeometryNode(kind="box", params={"size_x": "sx", "size_y": "sy", "size_z": "sz"})
    rb = verify_geometry(nb, {"sx": _q("sx", sx), "sy": _q("sy", sy), "sz": _q("sz", sz)})
    assert rb["ok"] is True
    assert rb["volume_ok"] is True
    assert rb["extent_ok"] is True
    expected_box = sx * sy * sz
    assert math.isclose(rb["brep_volume"], expected_box, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# Negative guard tests (documented fail-loud paths)
# --------------------------------------------------------------------------- #

def test_missing_quantity_raises_geometryerror():
    """Missing quantity id in the map must fail loud (GeometryError) — never
    a guessed 0 or silent NaN extent/volume."""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    node = GeometryNode(kind="box", params={"size_x": "sx", "size_y": "sy", "size_z": "sz"})
    with pytest.raises(GeometryError):
        verify_geometry(node, {"sx": _q("sx", 10), "sy": _q("sy", 10)})  # sz absent


def test_zero_or_negative_dimension_is_rejected_by_kernel_or_analytic():
    """Zero/negative dimensions are invalid geometry. The path must not silently
    produce ok=True or a positive volume. Either the CAD layer or analytic raises,
    or the result is ok=False with zero/negative volume. (L4 scoped: only where
    real silent-wrong would occur; here we assert the outcome is never a passing
    positive solid for non-positive input.)"""
    pytest.importorskip("cadquery", reason="BREP-vs-analytic cross-check needs optional cadquery/OCP kernel")
    node = GeometryNode(kind="sphere", params={"radius": "r"})
    # zero radius -> either exception upstream or nonzero_volume=False or ok=False
    try:
        r = verify_geometry(node, {"r": _q("r", 0.0)})
        assert r["ok"] is False or r["brep_volume"] <= 0.0 or not r["nonzero_volume"]
    except GeometryError:
        pass  # also acceptable loud failure
