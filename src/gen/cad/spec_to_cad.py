"""spec_to_cad — the Specification→CAD bridge for the realize path (G3 / P1-1).

Re-Audit 2026-07-15 finding: the realize path built its CAD from a hardcoded
template (`prototype_cad_builder` knew exactly two shapes, both named
"Jetpack …"), while the REAL parametric geometry of a γ-Specification
(``Component.geometry`` CSG trees + ``Quantity`` dimensions) only flowed through
the separate bundle/print exports. This module closes that seam:

  * ``specification_to_build_artifact`` turns a γ-Specification into the same
    ``BuildArtifact`` currency the Integrator/Assembly consume — real kernel
    STL on disk, CSG tree + quantities attached, honest ``None``/hint when the
    spec carries no geometry or no kernel is available. No placeholder files.
  * ``prototype_spec_from_assembly`` derives a ``PrototypeSpec`` from the REAL
    ``AssemblyConcept`` + ``IngenieurSpec`` (name, purpose, material) instead of
    a hardcoded "Jetpack …" label. Dimensions without a numeric source stay
    DECISION defaults and are declared as such — never invented measurements.

Reuses the existing export plumbing (``export.brep_stl``) — no parallel world.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from ..core.errors import GeometryError
from ..core.state import GeometryNode, Quantity, Specification
from .prototype_cad_builder import BuildArtifact, PrototypeSpec

#: Default plate hint (mm) when neither concept nor ingenieur carry numeric
#: dimensions — a DECISION, declared in the artifact's quelle + dfm_report.
_DEFAULT_BBOX_MM: tuple[float, float, float] = (100.0, 60.0, 5.0)


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "part"


def _fused_geometry(spec: Specification) -> GeometryNode | None:
    """Union of all component CSG trees (single component → its own tree)."""
    nodes = [c.geometry for c in spec.components if c.geometry is not None]
    if not nodes:
        return None
    if len(nodes) == 1:
        return nodes[0]
    return GeometryNode(kind="union", params={}, children=list(nodes))


def specification_to_build_artifact(
    spec: Specification,
    *,
    run_id: str | None = None,
    tolerance: float = 0.1,
) -> BuildArtifact | None:
    """REAL CAD artifact from a γ-Specification's own parametric geometry.

    Returns ``None`` when the specification carries no component geometry (the
    honest answer — nothing is invented). When geometry exists but no kernel is
    available, the artifact is returned WITHOUT a file (hint string in exports),
    still carrying the CSG tree + quantities for downstream consumers.
    """
    geometry = _fused_geometry(spec)
    if geometry is None:
        return None

    raw_q = spec.quantities
    quantities: dict[str, Quantity] = (
        dict(raw_q) if isinstance(raw_q, dict) else {q.id: q for q in raw_q}
    )
    name = _safe_name(spec.idea or spec.run_id or "specification_part")

    stl_path: str | None = None
    try:
        from ..export.brep_stl import specification_to_brep_stl

        stl_text = specification_to_brep_stl(spec, tolerance=tolerance)
        if stl_text and "facet" in stl_text:
            out_dir = Path("out") / "cad"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{name}_{run_id or spec.run_id or 'spec'}.stl"
            path.write_text(stl_text)
            if path.stat().st_size > 0:
                stl_path = str(path)
            else:  # never ship an empty artifact
                path.unlink()
    except (GeometryError, Exception):  # noqa: BLE001 — kernel absent/import guard
        stl_path = None

    proto = PrototypeSpec(
        name=spec.idea or "Specification part",
        description=(
            f"Real parametric geometry from γ-Specification "
            f"({len(spec.components)} component(s), {len(quantities)} quantities)"
        ),
        bounding_box_hint_mm=_DEFAULT_BBOX_MM,
        material_hint="see Specification quantities / BOM",
        quelle="spec_to_cad (G3): Specification.components CSG, no template",
    )

    n_geo = sum(1 for c in spec.components if c.geometry is not None)
    dfm = [
        f"Geometry from Specification: {n_geo} component(s) with CSG trees, "
        f"{len(quantities)} quantities resolved.",
    ]
    if stl_path is None:
        dfm.append(
            "Kernel STL not written (CAD kernel unavailable) — CSG tree attached, "
            "honest gap instead of a placeholder file."
        )

    return BuildArtifact(
        spec=proto,
        generated_code=(
            "# geometry source: Specification.components (parametric CSG) — "
            "see spec_to_cad.specification_to_build_artifact; no generated "
            "build123d template needed, the CSG tree itself is the model"
        ),
        exports={
            "stl": stl_path
            or "specification STL (kernel unavailable — no file emitted, honest gap)",
        },
        dfm_report=dfm,
        volume_estimate_cm3=None,
        is_buildable=stl_path is not None,
        run_id=run_id or spec.run_id,
        quelle="spec_to_cad (G3) + export.brep_stl (OCCT kernel) + γ-Specification",
        geometry=geometry,
        geometry_quantities=quantities,
    )


def prototype_spec_from_assembly(
    assembly,
    ingenieur=None,
    *,
    source_idea: str = "",
) -> PrototypeSpec:
    """Derive a ``PrototypeSpec`` from the REAL AssemblyConcept (+ IngenieurSpec).

    Name/purpose/material come from the actual pipeline data. Dimensions are a
    declared DECISION default (`_DEFAULT_BBOX_MM` for generic parts; the proven
    120×80×10 test-stand plate envelope for tether/recovery parts) — concept and
    ingenieur specs carry no numeric dimensions yet, and inventing them would
    violate the no-invented-measurements principle.
    """
    name = getattr(assembly, "name", None) or "Prototype part"
    purpose = getattr(assembly, "purpose", "") or ""
    material = None
    if ingenieur is not None:
        hints = getattr(ingenieur, "material_hinweise", None) or []
        if hints:
            material = getattr(hints[0], "name", None)

    lowered = f"{name} {purpose} {source_idea}".lower()
    is_anchor_family = any(k in lowered for k in ("tether", "recovery", "jetpack"))
    bbox = (120.0, 80.0, 10.0) if is_anchor_family else _DEFAULT_BBOX_MM

    # keep the proven tether/recovery anchor-plate canon reachable in the
    # builder (it triggers on "recovery" in the description)
    family_note = "Tether/Recovery anchor family. " if is_anchor_family else ""

    return PrototypeSpec(
        name=name,
        description=(
            f"{family_note}{purpose or 'Prototype part'} — derived from "
            f"SystemConcept assembly {name!r}; dimensions are DECISION defaults "
            f"(no numeric dims in concept/ingenieur yet)"
        ),
        bounding_box_hint_mm=bbox,
        material_hint=material or "PLA oder PETG für erste Prints",
        quelle=(
            "spec_to_cad.prototype_spec_from_assembly: Architekt AssemblyConcept "
            "+ IngenieurSpec material hints; bbox = declared DECISION default"
        ),
    )


__all__ = [
    "specification_to_build_artifact",
    "prototype_spec_from_assembly",
]
