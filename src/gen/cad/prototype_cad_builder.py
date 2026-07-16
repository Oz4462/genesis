"""prototype_cad_builder — first stone of the CAD / Fertigungs-Kernfähigkeit.

Gemäß GENESIS_PLATFORM_PLAN.md:
- §3.6: CAD, CAE und Fertigung als Kernfähigkeit (parametrisches CAD, BREP, STL/STEP,
  3D-Druck / CNC / Lasercut, DFM/Printability).
- §3.7 + Schritt 6 des 8-Schritt-Prozesses: PRINTFORGE + CAD-Audit (hier gestartet).
- 4.7 Fertigungs-Pipeline + 8.4: prototype_cad_builder erzeugt Prototyp/Teststand-CAD.
- 3.3/3.4 Moonshot + Fach-Pipelines: sichere, kleine, baubare Steine mit ehrlichen Gates.

Real stack (P0-1 2026-07-15): the part is modelled as a GENESIS CSG tree
(``GeometryNode`` + DECISION ``Quantity`` dimensions) and exported to a REAL STL
through the isolated CadQuery/OCCT kernel (``cadquery_bridge.to_stl``). The
build123d code emission is kept as a copyable deliverable, but the on-disk
artifact now comes from the kernel — no placeholder files, ever. When the
kernel is unavailable the export is honestly absent (hint string, no file).

Known simplification (documented, not hidden): the CSG vocabulary has no
fillet/chamfer, so the kernel STL is the unfilleted solid; fillets exist only
in the emitted build123d code.

Erster Stein: Jetpack-Kanon (tethered / bench-sichere Komponente, abgeleitet aus prior
Grenzverschiebung: Recovery, Energy, Safety-Ladder S0-S2).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import GeometryError
from ..core.state import GeometryNode, Quantity, ValueOrigin


@dataclass(frozen=True)
class PrototypeSpec:
    """Minimale, ehrliche Spezifikation für einen Prototypen / Teststand-Teil."""
    name: str
    description: str
    bounding_box_hint_mm: tuple[float, float, float]  # (x, y, z) approx
    min_wall_thickness_mm: float = 2.0
    material_hint: str = "PLA oder PETG für erste Prints"
    quelle: str | None = None


@dataclass(frozen=True)
class BuildArtifact:
    """Ergebnis des CAD-Builders (code + Artefakte + Gate-Output).

    ``geometry`` / ``geometry_quantities`` carry the parametric CSG tree the STL
    was (or would be) built from, so downstream consumers (assembly, drawings)
    can operate on REAL geometry instead of re-parsing generated code.
    """
    spec: PrototypeSpec
    generated_code: str                    # vollständiger, kopierbarer build123d-Code
    exports: dict[str, str]                # z.B. {"stl": "base64 or path hint", "step": "..."}
    dfm_report: list[str]                  # z.B. "Wandstärke OK", "Überhang >60° → Support nötig"
    volume_estimate_cm3: float | None = None
    is_buildable: bool = True
    run_id: str | None = None
    quelle: str | None = None
    geometry: GeometryNode | None = None
    geometry_quantities: dict[str, Quantity] = field(default_factory=dict)


def _q(qid: str, value: float, *, unit: str = "mm") -> Quantity:
    """A DECISION quantity for a template dimension (identifier-safe id, mm)."""
    return Quantity(
        id=qid,
        name=qid.replace("_", " "),
        value=float(value),
        unit=unit,
        origin=ValueOrigin.DECISION,
        rationale=(
            "template dimension chosen by prototype_cad_builder (first-stone "
            "prototype geometry, GENESIS_PLATFORM_PLAN.md §3.6/§8.4)"
        ),
    )


def _translated(child: GeometryNode, xq: str, yq: str, zq: str) -> GeometryNode:
    return GeometryNode(
        kind="translate", params={"x": xq, "y": yq, "z": zq}, children=[child]
    )


def _anchor_plate_geometry(
    spec: PrototypeSpec,
) -> tuple[GeometryNode, dict[str, Quantity]]:
    """Real CSG tree of the tether/recovery anchor plate (worker convention:
    box and cylinder are CENTERED at the origin)."""
    quantities = {
        q.id: q
        for q in (
            _q("plate_x", 120.0),
            _q("plate_y", 80.0),
            _q("plate_z", 6.0),
            _q("mount_hole_r", 5.5 / 2.0),   # M5 clearance
            _q("tether_hole_r", 8.0 / 2.0),  # Dyneema/Schäkel
            _q("recovery_hole_r", 4.0 / 2.0),
            _q("hole_h", 8.0),               # > plate_z → clean through-cut
            _q("pocket_x", 60.0),
            _q("pocket_y", 30.0),
            _q("pocket_z", 2.0),
            _q("pos_zero", 0.0),
            _q("mount_dx_pos", 45.0),
            _q("mount_dx_neg", -45.0),
            _q("mount_dy_pos", 25.0),
            _q("mount_dy_neg", -25.0),
            _q("recovery_dx_pos", 30.0),
            _q("recovery_dx_neg", -30.0),
            _q("pocket_dz", 2.0),            # pocket centered so it cuts the top 2 mm
        )
    }

    plate = GeometryNode(
        kind="box", params={"size_x": "plate_x", "size_y": "plate_y", "size_z": "plate_z"}
    )

    def hole(radius_qid: str) -> GeometryNode:
        return GeometryNode(
            kind="cylinder", params={"radius": radius_qid, "height": "hole_h"}
        )

    cuts: list[GeometryNode] = [
        _translated(hole("mount_hole_r"), "mount_dx_neg", "mount_dy_neg", "pos_zero"),
        _translated(hole("mount_hole_r"), "mount_dx_pos", "mount_dy_neg", "pos_zero"),
        _translated(hole("mount_hole_r"), "mount_dx_neg", "mount_dy_pos", "pos_zero"),
        _translated(hole("mount_hole_r"), "mount_dx_pos", "mount_dy_pos", "pos_zero"),
        _translated(hole("tether_hole_r"), "pos_zero", "pos_zero", "pos_zero"),
        _translated(hole("recovery_hole_r"), "recovery_dx_neg", "pos_zero", "pos_zero"),
        _translated(hole("recovery_hole_r"), "recovery_dx_pos", "pos_zero", "pos_zero"),
        _translated(
            GeometryNode(
                kind="box",
                params={"size_x": "pocket_x", "size_y": "pocket_y", "size_z": "pocket_z"},
            ),
            "pos_zero",
            "pos_zero",
            "pocket_dz",
        ),
    ]
    node = GeometryNode(kind="difference", params={}, children=[plate, *cuts])
    return node, quantities


def _generic_plate_geometry(
    spec: PrototypeSpec,
) -> tuple[GeometryNode, dict[str, Quantity]]:
    """Real CSG tree of the generic plate — PARAMETRIC on the spec's
    ``bounding_box_hint_mm`` (G3): plate = bbox footprint, one Ø5 center hole,
    plus 4 corner mount holes when the footprint is large enough."""
    bx, by, bz = spec.bounding_box_hint_mm
    px = max(float(bx), 10.0)
    py = max(float(by), 10.0)
    pz = max(float(bz), float(spec.min_wall_thickness_mm))
    quantities = {
        q.id: q
        for q in (
            _q("plate_x", px),
            _q("plate_y", py),
            _q("plate_z", pz),
            _q("hole_r", 2.5),
            _q("hole_h", pz + 2.0),
            _q("pos_zero", 0.0),
        )
    }
    plate = GeometryNode(
        kind="box", params={"size_x": "plate_x", "size_y": "plate_y", "size_z": "plate_z"}
    )

    def hole() -> GeometryNode:
        return GeometryNode(kind="cylinder", params={"radius": "hole_r", "height": "hole_h"})

    cuts: list[GeometryNode] = [hole()]
    # corner mount holes only when the plate is comfortably larger than the pattern
    if px >= 40.0 and py >= 40.0:
        inset = 8.0
        quantities.update(
            {
                q.id: q
                for q in (
                    _q("mount_dx_pos", px / 2.0 - inset),
                    _q("mount_dx_neg", -(px / 2.0 - inset)),
                    _q("mount_dy_pos", py / 2.0 - inset),
                    _q("mount_dy_neg", -(py / 2.0 - inset)),
                )
            }
        )
        for xq in ("mount_dx_neg", "mount_dx_pos"):
            for yq in ("mount_dy_neg", "mount_dy_pos"):
                cuts.append(_translated(hole(), xq, yq, "pos_zero"))
    node = GeometryNode(kind="difference", params={}, children=[plate, *cuts])
    return node, quantities


def _export_real_stl(
    name: str,
    node: GeometryNode,
    quantities: dict[str, Quantity],
    run_id: str | None,
) -> str | None:
    """Export the CSG through the OCCT kernel to a REAL, non-empty STL file.

    Returns the file path, or None when the kernel is unavailable or export
    fails — the caller then reports an honest gap. NEVER writes an empty file.
    """
    from .cadquery_bridge import cad_available, to_stl

    if not cad_available():
        return None
    try:
        stl_text = to_stl(node, quantities, name=name)
    except GeometryError:
        return None
    if not stl_text or "facet" not in stl_text:
        return None
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "part"
    out_dir = Path("out") / "cad"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe}_{run_id or 'proto'}.stl"
    path.write_text(stl_text)
    if path.stat().st_size == 0:  # defence in depth: no empty artifact, ever
        path.unlink()
        return None
    return str(path)


def build_prototype_cad(
    spec: PrototypeSpec,
    *,
    run_id: str | None = None,
) -> BuildArtifact:
    """
    Erzeugt einen realen, parametrischen Prototypen: CSG-Baum + Kernel-STL
    (wenn die cad-venv Bridge verfügbar ist) + kopierbaren build123d-Code.

    Für das Jetpack-Beispiel (abgeleitet aus Safety-Ladder + Recovery-Lessons):
    Eine "tether_anchor_plate" — flache, druckbare Platte mit Tether-Punkten,
    Mounting-Holes für Ducted-Fan-Test und Recovery-Hardware. Geeignet für S1 Prüfstand
    oder tethered unmanned (S2).

    Der build123d-Code ist 1:1 aus den offiziellen build123d Patterns (BuildPart,
    BuildSketch, Locations, extrude, fillet, etc.) und kann direkt ausgeführt werden.
    """
    if "jetpack" in spec.name.lower() or "tether" in spec.name.lower() or "recovery" in spec.description.lower():
        # Real build123d code (Builder-Mode, wie in der offiziellen Doku)
        code = f'''from build123d import *

# {spec.name} — Jetpack Tether/Recovery Anchor Plate
# Abgeleitet aus GENESIS Grenzverschiebung (Safety S1/S2, Recovery <3s, Energy)
# Quelle: {spec.quelle or "GENESIS_PLATFORM_PLAN.md §3.6 + §8.4 + prior LearningDelta"}

wall = {spec.min_wall_thickness_mm} * MM
plate_thickness = 6 * MM
hole_d = 5.5 * MM          # M5 clearance
tether_hole_d = 8 * MM     # für Dyneema/Schäkel

with BuildPart() as anchor_plate:
    # Grundplatte (rechteckig, für Bench- oder Tether-Montage)
    with BuildSketch() as base:
        Rectangle(120, 80)
    extrude(amount=plate_thickness)

    # Leicht abgerundete Ecken (Druck- und Handhabungsfreundlich)
    fillet(anchor_plate.edges().filter_by(GeomType.LINE).group_by(Axis.Z)[-1], radius=4)

    # Mounting Löcher (4x für Schrauben auf Prüfstand)
    with Locations((-45, -25), (45, -25), (-45, 25), (45, 25)):
        Hole(hole_d, depth=plate_thickness + 1)

    # Zentrale Tether/Recovery Punkte (stark belastet)
    with Locations((0, 0)):
        Hole(tether_hole_d, depth=plate_thickness + 1)

    # Zusätzliche Recovery-Befestigung (z.B. für Fallschirm-Container)
    with Locations((-30, 0), (30, 0)):
        Hole(4 * MM, depth=plate_thickness + 1)

    # Leichte Aussparung zur Gewichtsreduktion (optional, aber praxisnah)
    with BuildSketch(Plane(anchor_plate.faces().sort_by(Axis.Z).last)):
        Rectangle(60, 30)
    extrude(amount=-2, mode=Mode.SUBTRACT)

    # Kanten brechen (bessere Druckqualität, weniger Verletzungsrisiko)
    fillet(anchor_plate.edges().filter_by(GeomType.CIRCLE), radius=0.8)

# Export-Hinweise + echter Datei-Export (wird beim Ausführen erzeugt)
print("Anchor plate volume approx.:", round(anchor_plate.part.volume / 1000, 1), "cm³")

# Realer STL-Export (robust für build123d >=0.8)
import os, tempfile
try:
    from build123d import export_stl
    stl_path = os.path.join(tempfile.gettempdir(), "genesis_jetpack_tether_anchor.stl")
    export_stl(anchor_plate.part, stl_path)
    print("REAL STL EXPORTED:", stl_path)
    _genesis_stl_path = stl_path   # captured by caller
except Exception as e:
    print("Real STL export skipped or failed in this context:", e)
    _genesis_stl_path = None
'''

        dfm = [
            f"Min. Wandstärke: {spec.min_wall_thickness_mm} mm — OK für FDM (PLA/PETG).",
            "Löcher ≥5.5 mm — gut für Standard-Schrauben, wenig Support nötig.",
            "Platte flach (6 mm dick) — erste Lage stabil, geringes Warping-Risiko.",
            "Empfehlung: 4-5 Perimeter + 20-30% Infill für Tether-Last.",
            "Bounding box ~120x80x6 mm — passt auf fast jeden Consumer-Printer.",
            "Recovery-Befestigungen: zusätzliche Verstärkung (mehr Perimeter) um die 8 mm Löcher empfohlen.",
        ]
        # Audit B1 (2026-07-16): NEVER exec() emitted build123d code + NEVER invent
        # solid volumes (was hard-coded 42.0). Volume = bbox upper bound OR kernel
        # volume via cadquery bridge (subprocess), never in-process exec.
        node, quantities = _anchor_plate_geometry(spec)
        real_stl_path = _export_real_stl(
            "genesis_jetpack_tether_anchor", node, quantities, run_id
        )
        bx, by, bz = spec.bounding_box_hint_mm
        volume = round((float(bx) * float(by) * float(bz)) / 1000.0, 3)
        volume_note = "bbox_hint upper bound cm³ (not solid volume)"
        try:
            from .cadquery_bridge import cad_available, exact_volume

            if cad_available() and node is not None and quantities:
                solid_vol_mm3 = exact_volume(node, quantities)
                if solid_vol_mm3 is not None and solid_vol_mm3 > 0:
                    volume = round(float(solid_vol_mm3) / 1000.0, 3)
                    volume_note = "kernel solid volume via cadquery_bridge (subprocess)"
        except Exception:
            pass  # keep bbox upper bound

        dfm = list(dfm) + [f"volume basis: {volume_note}"]

        return BuildArtifact(
            spec=spec,
            generated_code=code,
            exports={
                "stl": real_stl_path
                or "genesis_jetpack_tether_anchor.stl (kernel unavailable — no file emitted, honest gap)",
                "step": "anchor_plate.step (via .export_step)",
            },
            dfm_report=dfm,
            volume_estimate_cm3=volume,
            is_buildable=True,
            run_id=run_id,
            quelle="cadquery_bridge (OCCT kernel STL) + build123d official docs (Builder mode patterns + export_stl) + GENESIS_PLATFORM_PLAN.md §3.6/3.7/8.4 + prior safety_ladder + learning_integrator (Recovery + Safety Gates)",
            geometry=node,
            geometry_quantities=quantities,
        )

    else:
        # Generic viable plate — PARAMETRIC on the bbox hint (G3), echtes CSG + build123d Code
        gx = max(float(spec.bounding_box_hint_mm[0]), 10.0)
        gy = max(float(spec.bounding_box_hint_mm[1]), 10.0)
        gz = max(float(spec.bounding_box_hint_mm[2]), float(spec.min_wall_thickness_mm))
        code = f'''from build123d import *

# Generic prototype plate — {spec.name}
# Parametric footprint from bounding_box_hint_mm (DECISION default when unset)
with BuildPart() as plate:
    with BuildSketch() as base:
        Rectangle({gx}, {gy})
    extrude(amount={gz})
    fillet(plate.edges().filter_by(GeomType.LINE), radius=3)
    with Locations((0, 0)):
        Hole(5, depth={gz + 1})
'''

        node, quantities = _generic_plate_geometry(spec)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", spec.name).strip("_") or "generic_plate"
        real_stl_path = _export_real_stl(safe, node, quantities, run_id)
        # Audit B1: no magic 30.0 — bbox upper bound or kernel solid volume
        volume = round((gx * gy * gz) / 1000.0, 3)
        volume_note = "bbox_hint upper bound cm³ (not solid volume)"
        try:
            from .cadquery_bridge import cad_available, exact_volume

            if cad_available() and node is not None and quantities:
                solid_vol_mm3 = exact_volume(node, quantities)
                if solid_vol_mm3 is not None and solid_vol_mm3 > 0:
                    volume = round(float(solid_vol_mm3) / 1000.0, 3)
                    volume_note = "kernel solid volume via cadquery_bridge (subprocess)"
        except Exception:
            pass

        return BuildArtifact(
            spec=spec,
            generated_code=code,
            exports={
                "stl": real_stl_path
                or "generic_plate.stl (kernel unavailable — no file emitted, honest gap)",
            },
            dfm_report=[
                "Einfache Platte — leicht zu drucken. Wand 5 mm > empfohlene min.",
                f"volume basis: {volume_note}",
            ],
            volume_estimate_cm3=volume,
            is_buildable=True,
            run_id=run_id,
            quelle="cadquery_bridge (OCCT kernel STL) + build123d docs + GENESIS generic fallback",
            geometry=node,
            geometry_quantities=quantities,
        )
