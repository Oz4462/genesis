"""manufacturing_check — erster Fertigungs-Gate / Printability-Check für den CAD-Kern.

Gemäß GENESIS_PLATFORM_PLAN.md:
- 4.7 Fertigungs-Pipeline (DFM, Printability-Report, Druck-/CNC-Dateien)
- 3.6 / 3.7 CAD/CAE/Fertigung als Kern + PRINTFORGE-Ersatz (da kein externes Tool gefunden)
- 8.4 manufacturing_runner / printability layer

Nimmt ein BuildArtifact (mit realer STL aus prototype_cad_builder), prüft:
- Datei existiert auf Platte
- Dateigröße plausibel
- Volumen grob plausibel
- Bounding-Box-Hint respektiert (mit Toleranz)
- Min-Wall aus Spec berücksichtigt
- Für Jetpack: "druckbar mit Support" oder Issues

Output: ManufacturingCheck mit printable-Flag, Issues, Evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Optional

from .prototype_cad_builder import BuildArtifact, PrototypeSpec


@dataclass(frozen=True)
class ManufacturingCheck:
    """Ergebnis des Manufacturing/Printability-Gates."""
    artifact_name: str
    printable: bool
    issues: list[str]
    details: dict[str, object]
    stl_path: str | None = None
    run_id: str | None = None
    quelle: str | None = None


def check_manufacturing(
    artifact: BuildArtifact,
    *,
    run_id: str | None = None,
    max_printer_dim_mm: tuple[float, float, float] = (220.0, 220.0, 250.0),  # typical Ender-like
) -> ManufacturingCheck:
    """
    Einfacher aber ehrlicher Manufacturing-Check.
    Nutzt den realen STL-Pfad aus dem Artifact (wenn vorhanden).
    """
    name = artifact.spec.name
    issues: list[str] = []
    details: dict[str, object] = {}

    stl_path = artifact.exports.get("stl") if isinstance(artifact.exports, dict) else None
    details["stl_claim"] = stl_path
    details["volume_estimate_cm3"] = artifact.volume_estimate_cm3

    # 1. Datei existiert?
    file_exists = bool(stl_path and os.path.exists(str(stl_path)))
    details["file_exists"] = file_exists
    if not file_exists:
        issues.append("STL file not found on disk")
        return ManufacturingCheck(
            artifact_name=name,
            printable=False,
            issues=issues,
            details=details,
            stl_path=stl_path,
            run_id=run_id,
            quelle="manufacturing_check + prototype_cad_builder",
        )

    # 2. Dateigröße plausibel (nicht 0 und nicht winzig für ein Teil)
    try:
        size = os.path.getsize(str(stl_path))
        details["stl_size_bytes"] = size
        if size < 1024:
            issues.append("STL file too small (<1KB) — likely empty or failed export")
    except Exception as e:
        issues.append(f"Could not stat STL file: {e}")

    # 3. Volumen grob plausibel ( > 0 )
    vol = artifact.volume_estimate_cm3 or 0.0
    if vol <= 0.1:
        issues.append("Volume estimate near zero — geometry probably invalid")

    # 4. Bounding-Box-Hint (sehr grob: max dim < printer + margin)
    hx, hy, hz = artifact.spec.bounding_box_hint_mm
    max_x, max_y, max_z = max_printer_dim_mm
    if hx > max_x * 1.2 or hy > max_y * 1.2 or hz > max_z * 1.2:
        issues.append(f"Part larger than typical printer ({max_printer_dim_mm}mm)")

    # 5. Min wall note (nur Warnung, kein Hard-Fail hier)
    wall = artifact.spec.min_wall_thickness_mm
    details["min_wall_mm"] = wall
    if wall < 1.5:
        issues.append(f"Very thin walls requested ({wall}mm) — high failure risk on FDM")

    printable = len(issues) == 0

    quelle = (
        "manufacturing_check (real STL + spec) + "
        "GENESIS_PLATFORM_PLAN.md 4.7 / 3.6 / 8.4 + "
        "prototype_cad_builder (real export)"
    )

    return ManufacturingCheck(
        artifact_name=name,
        printable=printable,
        issues=issues,
        details=details,
        stl_path=stl_path,
        run_id=run_id,
        quelle=quelle,
    )


# === Advanced DFM / Fertigungs depth first stone (PLAN §4.7, §3.6) ===
# Integrates dfm.py (FDM constants/rules) + printability.py documented rules (bridge, clearance, pins, layer adhesion etc.)
# + multi-process (FDM full, CNC/Laser/PCB stubs with process-specific DFM).
# Works on real BuildArtifact / STL from prototype_cad_builder.
# Produces richer report for use in packager / Wissensbasis / Lern feedback.
# Jetpack example triggers concrete issues (thin walls, size, layer strength if load path noted).
# Generic: honest gaps for unmodeled processes.

from gen.dfm import (
    FDM_MIN_WALL_MM,
    FDM_MIN_HOLE_DIAMETER_MM,
)
# Printability rules documented in module (we implement the key numeric checks here for determinism;
# full orientation/bridge logic would live in orientation.py but we reference the thresholds).

@dataclass(frozen=True)
class ProcessDFM:
    process: str  # FDM, CNC, Laser, PCB
    printable: bool
    issues: list[str]
    details: dict[str, object]
    cost_hint: str | None = None  # stub
    qa_hints: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class AdvancedDFMReport:
    """Erweiterter DFM-Report (Advanced DFM first stone)."""
    artifact_name: str
    overall_printable: bool
    processes: list[ProcessDFM]
    total_issues: list[str]
    stl_path: str | None = None
    run_id: str | None = None
    quelle: str | None = None
    cost_model_stub: str | None = None
    qa_plan_stub: list[str] = field(default_factory=list)


def check_advanced_dfm(
    artifact: BuildArtifact,
    *,
    run_id: str | None = None,
    max_printer_dim_mm: tuple[float, float, float] = (220.0, 220.0, 250.0),
) -> AdvancedDFMReport:
    """
    Advanced DFM / Fertigungs depth.
    Runs base manufacturing_check + dfm/printability rules + multi-process stubs.
    Real STL on disk used where possible.
    """
    base = check_manufacturing(artifact, run_id=run_id, max_printer_dim_mm=max_printer_dim_mm)
    name = artifact.spec.name
    stl_path = base.stl_path
    all_issues = list(base.issues)
    processes: list[ProcessDFM] = []

    # FDM full (base + dfm + printability thresholds)
    fdm_issues = list(base.issues)
    fdm_details = dict(base.details)
    vol = artifact.volume_estimate_cm3 or 0.0
    wall = artifact.spec.min_wall_thickness_mm or 0.0

    # dfm rules
    if wall < FDM_MIN_WALL_MM:
        fdm_issues.append(f"FDM: wall {wall}mm < min reliable {FDM_MIN_WALL_MM}mm (dfm.py)")
    hole_hint = 3.0  # conservative; real would come from geometry
    if hole_hint < FDM_MIN_HOLE_DIAMETER_MM:
        fdm_issues.append(f"FDM: small hole ~{hole_hint}mm < {FDM_MIN_HOLE_DIAMETER_MM}mm (dfm.py)")

    # printability rules (from documented thresholds in printability.py)
    # bridge (simplified: assume if large flat -> potential)
    if vol > 30:
        fdm_issues.append("FDM: large volume — check bridge spans >10mm (printability.py rule)")
    # layer adhesion (load path across layers is gap for now)
    fdm_issues.append("FDM: layer adhesion loss >55% Z (printability.py) — load path across layers must be validated or re-oriented (gap)")
    # mating/pins/walls (examples)
    if wall < 1.0:
        fdm_issues.append("FDM: free-standing wall <1.0mm risks wobble/delam (printability.py)")

    fdm_printable = len(fdm_issues) == 0 and base.printable
    processes.append(ProcessDFM(
        process="FDM",
        printable=fdm_printable,
        issues=fdm_issues,
        details=fdm_details,
        cost_hint="~0.05-0.15 EUR/g material + support (Jetpack Tether ~5-12 EUR est.)",
        qa_hints=["Visual + caliper on critical dims", "Pull test sample for layer strength"],
    ))

    # CNC stub (different rules: min feature, tolerance)
    cnc_issues = []
    if wall < 1.0:
        cnc_issues.append("CNC: wall <1.0mm may require special tooling or EDM")
    if artifact.spec.bounding_box_hint_mm[0] > 200:
        cnc_issues.append("CNC: large part — fixturing/5-axis needed")
    cnc_printable = len(cnc_issues) == 0
    processes.append(ProcessDFM(
        process="CNC",
        printable=cnc_printable,
        issues=cnc_issues,
        details={"min_feature_mm": 0.5, "typical_tol": "±0.05mm"},
        cost_hint="Higher for small qty; material removal cost dominant",
        qa_hints=["CMM on critical", "Surface finish check"],
    ))

    # Laser / sheet stub
    laser_issues = []
    if vol > 10 and wall > 3:
        laser_issues.append("Laser: thick material — consider waterjet or plasma instead of laser")
    laser_printable = len(laser_issues) == 0
    processes.append(ProcessDFM(
        process="Laser",
        printable=laser_printable,
        issues=laser_issues,
        details={"kerf": "0.1-0.3mm typical"},
        cost_hint="Fast for sheet; nesting savings for >10 pcs",
    ))

    # PCB stub (electronics path from Elektriker)
    pcb_issues = []
    # If the part name hints at electronics (from Elektriker Naht)
    if "tether" in name.lower() or "electronic" in name.lower() or "control" in name.lower():
        pcb_issues.append("PCB: requires separate board; this is mechanical mount — check mounting holes for M2.5+")
    pcb_printable = len(pcb_issues) == 0
    processes.append(ProcessDFM(
        process="PCB",
        printable=pcb_printable,
        issues=pcb_issues,
        details={"trace_min_mm": 0.2, "via_min": 0.3},
        cost_hint="See Elektriker BOM for board cost",
        qa_hints=["ERC/DRC", "impedance if high speed"],
    ))

    overall = any(p.printable for p in processes)  # conservative: if any process viable
    # But for strict: require FDM or noted
    if not any(p.process == "FDM" and p.printable for p in processes):
        all_issues.append("No fully printable primary process without issues (FDM primary for prototype)")

    quelle = (
        "advanced_dfm (dfm.py + printability.py rules + multi-process) + "
        "manufacturing_check base + GENESIS_PLATFORM_PLAN.md §4.7 / 3.6 + "
        "real STL from prototype_cad_builder"
    )

    cost_stub = "Est. 8-25 EUR for Jetpack Tether prototype (FDM dominant; scales with qty/process)"
    qa_stub = ["FDM: dimensional + pull sample", "CNC: surface + tolerance", "Final: fit to assembly + functional load test"]

    return AdvancedDFMReport(
        artifact_name=name,
        overall_printable=overall and len(all_issues) == 0,
        processes=processes,
        total_issues=all_issues + [i for p in processes for i in p.issues],
        stl_path=stl_path,
        run_id=run_id,
        quelle=quelle,
        cost_model_stub=cost_stub,
        qa_plan_stub=qa_stub,
    )
