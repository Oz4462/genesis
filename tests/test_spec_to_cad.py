"""G3 (P1-1) tests: the Specification→CAD bridge for the realize path.

Contract:
  * a γ-Specification WITH component geometry yields a BuildArtifact carrying
    the real CSG tree + quantities (and a real, non-empty kernel STL when the
    kernel is available) — no template, no placeholder file.
  * a Specification WITHOUT geometry yields None (nothing invented).
  * PrototypeSpecs derived from AssemblyConcepts carry the REAL assembly name,
    purpose and material hint — not a hardcoded "Jetpack …" label.
  * the generic plate geometry is PARAMETRIC on bounding_box_hint_mm.
"""

from __future__ import annotations

import dataclasses
import os

import pytest

from gen.cad.cadquery_bridge import cad_available
from gen.cad.prototype_cad_builder import PrototypeSpec, build_prototype_cad
from gen.cad.spec_to_cad import (
    prototype_spec_from_assembly,
    specification_to_build_artifact,
)
from gen.demo import capstone_spec
from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec


def test_specification_without_geometry_returns_none():
    spec = capstone_spec()
    bare_components = [
        dataclasses.replace(c, geometry=None) for c in spec.components
    ]
    bare = dataclasses.replace(spec, components=bare_components)
    assert specification_to_build_artifact(bare, run_id="g3-none") is None


def test_specification_artifact_carries_real_csg_and_quantities():
    art = specification_to_build_artifact(capstone_spec(), run_id="g3-csg")
    assert art is not None
    assert art.geometry is not None
    assert art.geometry.kind in ("difference", "union", "box", "intersection")
    assert len(art.geometry_quantities) > 0
    # never a 0-byte artifact: either a real file or an honest hint string
    stl = art.exports["stl"]
    if os.path.exists(stl):
        assert os.path.getsize(stl) > 0
    else:
        assert "kernel unavailable" in stl or "honest gap" in stl


@pytest.mark.skipif(not cad_available(), reason="cad-venv kernel not installed")
def test_specification_artifact_writes_real_kernel_stl():
    art = specification_to_build_artifact(capstone_spec(), run_id="g3-kernel")
    assert art is not None and art.is_buildable
    stl = art.exports["stl"]
    assert os.path.isfile(stl) and os.path.getsize(stl) > 0


def test_prototype_spec_derived_from_real_assembly_not_template():
    concept = map_to_system_concept(
        "Ein modularer Vertikal-Garten mit Bewässerung", run_id="g3-derive"
    )
    ingenieur = map_to_ingenieur_spec(concept, run_id="g3-derive")
    target = concept.main_assemblies[0]
    proto = prototype_spec_from_assembly(
        target, ingenieur, source_idea=concept.source_idea
    )
    assert proto.name == target.name
    assert "Jetpack" not in proto.name
    assert "DECISION default" in proto.description
    assert proto.quelle and "prototype_spec_from_assembly" in proto.quelle


def test_prototype_spec_anchor_family_keeps_canon_reachable():
    concept = map_to_system_concept(
        "Ich will ein Jetpack bauen, das sicher fliegt.", run_id="g3-canon"
    )
    ingenieur = map_to_ingenieur_spec(concept, run_id="g3-canon")
    tether = next(a for a in concept.main_assemblies if "tether" in a.name.lower())
    proto = prototype_spec_from_assembly(
        tether, ingenieur, source_idea=concept.source_idea
    )
    # builder's anchor-plate branch triggers on name or description keywords
    triggered = (
        "jetpack" in proto.name.lower()
        or "tether" in proto.name.lower()
        or "recovery" in proto.description.lower()
    )
    assert triggered
    assert proto.bounding_box_hint_mm == (120.0, 80.0, 10.0)


def test_generic_plate_geometry_is_parametric_on_bbox():
    small = build_prototype_cad(
        PrototypeSpec(
            name="Small Widget", description="tiny", bounding_box_hint_mm=(30, 20, 3)
        ),
        run_id="g3-small",
    )
    large = build_prototype_cad(
        PrototypeSpec(
            name="Large Widget", description="big", bounding_box_hint_mm=(200, 120, 8)
        ),
        run_id="g3-large",
    )
    sq = {q.id: q.value for q in small.geometry_quantities.values()}
    lq = {q.id: q.value for q in large.geometry_quantities.values()}
    assert (sq["plate_x"], sq["plate_y"], sq["plate_z"]) == (30.0, 20.0, 3.0)
    assert (lq["plate_x"], lq["plate_y"], lq["plate_z"]) == (200.0, 120.0, 8.0)
    # corner mount holes only on the large plate
    assert "mount_dx_pos" in lq and "mount_dx_pos" not in sq
    # emitted build123d code reflects the real dimensions
    assert "Rectangle(200.0, 120.0)" in large.generated_code
