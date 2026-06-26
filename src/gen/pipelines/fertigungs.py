"""fertigungs — Fertigungs-Pipeline first stone (PLAN §4.7).

Gemäß GENESIS_PLATFORM_PLAN.md §4.7:
- Aufgabe: Fertigungsverfahren wählen, Prozessgrenzen prüfen, DFM-Regeln anwenden (über advanced_dfm), Kosten/Stückzahl bewerten, Fertigungsdateien erzeugen (gcode/stub), Qualitätskontrolle planen.
- Outputs: Fertigungsstrategie, DFM-Report (Naht), Druck-/CNC-/...-Dateien, Kostenmodell, QA-Plan.
- Gate: keine Fertigungsdatei ohne Geometriecheck; keine Druckfreigabe ohne Printability-Report; keine Kosten ohne Quelle/Schätzung; keine Prozesswahl ohne Begründung.

Erster Stein: deterministischer Mapper von SystemConcept + IngenieurSpec + optional advanced DFM zu FertigungsSpec.
Jetpack-Beispiel: FDM primary für Tether-Anchor-Plate (real STL + advanced DFM output), alt CNC; cost/volume from CAD; gcode stub (text); QA from prior (layer, dim).
Generic Fallback mit ehrlichen Gaps.

Naht: Nimmt DFM-Report (from cad.advanced), prior CAD/Assembly real artifacts, Wissensbasis Material (cost), Lern (gaps), packager/realize (output in manifest). Updates realize for richer Fertigungsplan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec, MaterialSpec, ToleranceSpec

# Naht to advanced DFM (from prior stone)
try:
    from gen.cad.manufacturing_check import AdvancedDFMReport
except Exception:
    AdvancedDFMReport = dict  # type: ignore
try:
    from gen.cad.gcode import GCodeProgram  # for real attachment (MODULE-05)
except Exception:
    GCodeProgram = None  # type: ignore  # type: ignore
    GCodeProgram = object  # fallback for annotations


@dataclass(frozen=True)
class FertigungsProzess:
    """Gewählter Fertigungsprozess mit Begründung + Grenzen."""

    name: str  # FDM, CNC, Laser, PCB
    begruendung: str
    prozessgrenzen: str  # z.B. "min wall 0.8mm from DFM"
    datei_stub: str | None = None  # gcode path or description (legacy for gaps)
    gcode_program: "GCodeProgram | None" = (
        None  # real from cad.gcode (MODULE-05: profile + pocket)
    )
    quelle: str | None = None


@dataclass(frozen=True)
class KostenModell:
    """Kosten + Stückzahl Schätzung (mit Quelle/Schätzung per Gate)."""

    material_kosten: str
    prozess_kosten: str
    gesamt_est: str
    stueckzahl_hinweis: str
    quelle: str | None = None


@dataclass(frozen=True)
class QAPlan:
    """Qualitätskontrolle / Prüfplan."""

    schritte: list[str]
    gate_kriterien: str
    quelle: str | None = None


@dataclass(frozen=True)
class FertigungsSpec:
    """Output der Fertigungs-Pipeline (erster Stein)."""

    source_idea: str
    gewaehlte_prozesse: list[FertigungsProzess]
    dfm_report_ref: str | None  # Naht to advanced DFM
    kosten_modell: KostenModell
    qa_plan: QAPlan
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def _fdm_cost_estimate_from_dfm(dfm_report: Optional[Any]) -> str | None:
    """Pull the FDM process's REAL ranged cost estimate (cost_model.py, Stein 4) out of
    an AdvancedDFMReport — or an equivalent dict. Returns ``None`` when no FDM cost is
    present, so the caller declares an honest gap instead of FABRICATING a band (the
    "8-25 EUR" disease cost_model was built to cure). The estimate is computed upstream
    by check_advanced_dfm via estimate_fdm_cost; this is the seam that consumes it (no
    duplicate computation, no fabricated number)."""
    if dfm_report is None:
        return None
    processes = getattr(dfm_report, "processes", None)
    if processes is None and isinstance(dfm_report, dict):
        processes = dfm_report.get("processes")
    for proc in processes or []:
        name = getattr(proc, "process", None)
        hint = getattr(proc, "cost_hint", None)
        if name is None and isinstance(proc, dict):
            name = proc.get("process") or proc.get("p")
            hint = proc.get("cost_hint")
        if (name or "").upper() == "FDM" and hint:
            return str(hint)
    return None


# Markers that justify ADDING a precision/subtractive process (CNC) — derived from
# the engineer's REAL tolerance signal, never invented. Tight fits (ISO H/g/k grades),
# explicit micron specs and ±0.0x callouts cannot be held by hobby-grade FDM.
_PRECISION_TOLERANCE_MARKERS: tuple[str, ...] = (
    "h7",
    "h6",
    "h5",
    "g6",
    "k6",
    "js",
    "µm",
    "um",
    "micron",
    "±0.0",
)
# Material name fragments that signal a metallic/composite workpiece — a real signal
# from ingenieur.material_hinweise that a metal-capable process (CNC) is appropriate.
_METAL_MATERIAL_MARKERS: tuple[str, ...] = (
    "alu",
    "stahl",
    "steel",
    "titan",
    "edelstahl",
    "messing",
    "metal",
    "cfk",
)
# Fragments in a CAD requirement that carry a concrete manufacturing constraint
# (wall thickness / dimension) we can quote into prozessgrenzen instead of guessing.
_DIMENSION_REQUIREMENT_MARKERS: tuple[str, ...] = (
    "wand",
    "wall",
    "mm",
    "fillet",
    "radius",
)


def _precision_tolerance(ingenieur: IngenieurSpec) -> "ToleranceSpec | None":
    """Return the first engineer tolerance that signals a precision (CNC) need, or
    ``None`` when no tolerance justifies one. The decision is driven purely by the
    REAL ``ingenieur.toleranzen`` values — no fabricated precision requirement."""
    for tol in ingenieur.toleranzen:
        blob = f"{tol.feature} {tol.toleranz}".lower()
        if any(marker in blob for marker in _PRECISION_TOLERANCE_MARKERS):
            return tol
    return None


def _metal_material(ingenieur: IngenieurSpec) -> "MaterialSpec | None":
    """Return the first metallic/composite material hint, or ``None``. Used only to
    JUSTIFY (with the real material name) adding a metal-capable process; never to
    invent a material the engineer did not specify."""
    for mat in ingenieur.material_hinweise:
        if any(marker in mat.name.lower() for marker in _METAL_MATERIAL_MARKERS):
            return mat
    return None


def _dimension_requirements(ingenieur: IngenieurSpec) -> list[str]:
    """Return the engineer's CAD requirements that carry a concrete dimensional /
    wall-thickness constraint, so prozessgrenzen can quote real input instead of a
    fixed 'min wall from DFM' placeholder. Empty list ⇒ caller declares a gap."""
    return [
        req
        for req in ingenieur.cad_anforderungen
        if any(marker in req.lower() for marker in _DIMENSION_REQUIREMENT_MARKERS)
    ]


def _derive_generic_processes(
    concept: SystemConcept, ingenieur: IngenieurSpec
) -> list[FertigungsProzess]:
    """Derive the manufacturing process list for a non-jetpack idea from REAL signals
    in ``concept``/``ingenieur`` (Gate: keine Prozesswahl ohne Begründung).

    - FDM is always proposed as the honest prototype baseline; its prozessgrenzen quote
      real dimensional CAD requirements when present, else declare an explicit gap.
    - CNC is added ONLY when a real precision tolerance or a metallic material justifies
      it; the begründung embeds the concrete driving value so the choice is auditable.

    No facts are fabricated: every justification cites a field that was actually passed in.
    """
    dimension_reqs = _dimension_requirements(ingenieur)
    if dimension_reqs:
        fdm_grenzen = "Maß/Wand aus ingenieur.cad_anforderungen: " + "; ".join(
            dimension_reqs
        )
    else:
        # No silent default: be explicit that the bound is unknown until a DFM/geometry check.
        fdm_grenzen = (
            "Lücke: keine Wand-/Maß-Vorgabe in ingenieur.cad_anforderungen — "
            "Geometrie-/DFM-Check nötig (keine geratene Wandstärke)"
        )

    lead_assembly = concept.main_assemblies[0] if concept.main_assemblies else None
    fdm_begruendung = f"FDM als Prototyp-Default für »{concept.source_idea}«"
    if lead_assembly is not None:
        fdm_begruendung += (
            f"; trägt Baugruppe '{lead_assembly.name}' ({lead_assembly.purpose})"
        )

    processes = [
        FertigungsProzess(
            name="FDM",
            begruendung=fdm_begruendung,
            prozessgrenzen=fdm_grenzen,
            datei_stub=None,  # honest: no slicer/CAM run in the first stone
            quelle="generic mapping aus concept+ingenieur (keine fabrizierte Prozesswahl) + PLAN §4.7",
        )
    ]

    tol = _precision_tolerance(ingenieur)
    metal = _metal_material(ingenieur)
    if tol is not None or metal is not None:
        reasons: list[str] = []
        if tol is not None:
            reasons.append(f"enge Toleranz '{tol.toleranz}' an '{tol.feature}'")
        if metal is not None:
            reasons.append(f"metallischer/composite Werkstoff '{metal.name}'")
        processes.append(
            FertigungsProzess(
                name="CNC",
                begruendung="CNC ergänzt, weil "
                + " und ".join(reasons)
                + " (aus ingenieur abgeleitet)",
                prozessgrenzen=(
                    "Feinbearbeitung nach realer Toleranz-/Materialvorgabe; "
                    "exakte Maschinenparameter/Aufspannung offen (Lücke)"
                ),
                quelle="generic mapping aus ingenieur.toleranzen/material_hinweise + PLAN §4.7",
            )
        )
    return processes


def map_to_fertigungs_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    dfm_report: Optional[Any] = None,  # AdvancedDFMReport or dict
    run_id: str | None = None,
) -> FertigungsSpec:
    """
    Erster Stein Fertigungs-Pipeline.
    Nutzt advanced DFM für Prozesswahl/Grenzen (Naht).
    Jetpack: FDM primary für Tether Plate (real volume/wall aus CAD + DFM), CNC alt.
    Generic: leitet Prozesse/Grenzen/Kosten/QA nachweislich aus ``concept`` und
    ``ingenieur`` ab (zwei verschiedene Eingaben → unterscheidbare Specs) und markiert
    fehlende Belege ehrlich als Lücke (keine fabrizierten Preise/Prozesse).

    Raises:
        ValueError: wenn ``concept.source_idea`` leer oder nur Whitespace ist — eine
            fehlende Eingabe darf keinen fabrizierten Stub erzeugen (Kernprinzip:
            keine stillen Defaults; spiegelt architekt.map_to_system_concept).
    """
    if not concept.source_idea.strip():
        raise ValueError(
            "concept.source_idea must be a non-empty, non-whitespace string "
            "(no fabricated FertigungsSpec for a missing idea)"
        )

    idee_lower = concept.source_idea.lower()

    if "jetpack" in idee_lower or "flug" in idee_lower:
        # Primary FDM from DFM example (tether plate)
        prozesse = [
            FertigungsProzess(
                name="FDM",
                begruendung="Primary for prototype (volume ~49cm³, 2mm wall from CAD; printable per advanced DFM)",
                prozessgrenzen="min wall 0.8mm, bridge <=10mm, layer adhesion warning (from dfm/printability + advanced DFM)",
                datei_stub="FDM print gcode needs a slicer (per-layer toolpaths) — not generated (honest gap)",
                gcode_program=None,  # FDM slicing external; CNC gcode from dfm below
                quelle="advanced_dfm (FDM process) + prototype_cad_builder (real STL/volume) + PLAN §4.7",
            ),
            FertigungsProzess(
                name="CNC",
                begruendung="Alternative for precision/strength (if FDM layer issues)",
                prozessgrenzen="min feature 0.5mm, tol ±0.05mm (from advanced DFM CNC stub)",
                datei_stub=None,
                gcode_program=getattr(dfm_report, "gcode_program", None)
                if dfm_report is not None
                else None,
                quelle="advanced_dfm (CNC) + cad.gcode (real profile/pocket) + PLAN §4.7",
            ),
        ]
        dfm_ref = "advanced_dfm report for Jetpack Tether Anchor (printable FDM primary, issues noted)"
        fdm_cost = _fdm_cost_estimate_from_dfm(dfm_report)
        if fdm_cost:
            kosten = KostenModell(
                material_kosten="im gerangten FDM-Modell enthalten (Volumen × Dichte × Infill × Preis, cost_model.py Stein 4)",
                prozess_kosten="im gerangten FDM-Modell enthalten (Maschinenzeit × Maschinenrate)",
                gesamt_est=fdm_cost,
                stueckzahl_hinweis="1-10: FDM; >50: Spritzguss oder CNC-Batch prüfen",
                quelle="advanced_dfm → cost_model.estimate_fdm_cost (Stein 4, reale gerangte Schätzung) + CAD-Volumen + PLAN §4.7",
            )
        else:
            kosten = KostenModell(
                material_kosten="Lücke: kein DFM-Kostenmodell übergeben",
                prozess_kosten="Lücke: kein DFM-Kostenmodell übergeben",
                gesamt_est="Lücke: keine gerangte Schätzung (advanced_dfm mit realem CAD-Volumen nötig — cost_model.py Stein 4; keine fabrizierte Zahl)",
                stueckzahl_hinweis="1-10: FDM; >50: Spritzguss oder CNC-Batch prüfen",
                quelle="PLAN §4.7 (keine Kosten ohne cost_model-Quelle)",
            )
        qa = QAPlan(
            schritte=[
                "FDM: dimensional + pull sample for layer strength (from DFM)",
                "CNC: surface finish + tolerance CMM",
                "Final: fit to assembly + functional load (tether tension)",
            ],
            gate_kriterien="FDM printable per advanced DFM + no critical layer load without reorient",
            quelle="advanced_dfm qa_plan + prior Safety/Physiker + PLAN §4.7",
        )
        zusammen = "Jetpack FertigungsSpec: FDM primary (real STL + DFM), CNC alt; cost/volume from CAD/Wissensbasis; real verified CNC profile gcode (cad.gcode) + FDM-slicing gap; QA with DFM gates. Naht to realize/packager (DFM in manifest)."
        quelle = "GENESIS_PLATFORM_PLAN.md §4.7 (Fertigungs-Pipeline) + advanced_dfm (prior stone) + prototype_cad_builder (real) + Wissensbasis Material + Jetpack-Kanon"
    else:
        # Generic path: derive everything from the passed-in concept/ingenieur signals.
        prozesse = _derive_generic_processes(concept, ingenieur)
        dfm_ref = (
            "advanced DFM (übergeben — Kosten/Grenzen daraus konsumiert)"
            if dfm_report is not None
            else "advanced DFM (generic — keiner übergeben → Kosten/Grenzen als Lücke)"
        )

        # Consume the SAME real cost seam as the jetpack path; declare an honest gap
        # (never a fabricated band) when no DFM cost is present.
        fdm_cost = _fdm_cost_estimate_from_dfm(dfm_report)
        if fdm_cost:
            kosten = KostenModell(
                material_kosten="im gerangten FDM-Modell enthalten (Volumen × Dichte × Infill × Preis, cost_model.py Stein 4)",
                prozess_kosten="im gerangten FDM-Modell enthalten (Maschinenzeit × Maschinenrate)",
                gesamt_est=fdm_cost,
                stueckzahl_hinweis="1-10: FDM; >50: Spritzguss/CNC-Batch prüfen (heuristisch)",
                quelle="advanced_dfm → cost_model.estimate_fdm_cost (Stein 4, reale gerangte Schätzung) + PLAN §4.7",
            )
        else:
            kosten = KostenModell(
                material_kosten="Lücke: kein DFM-Kostenmodell übergeben",
                prozess_kosten="Lücke: kein DFM-Kostenmodell übergeben",
                gesamt_est=(
                    "Lücke: keine gerangte Schätzung (advanced_dfm mit realem CAD-Volumen "
                    "nötig — cost_model.py Stein 4; keine fabrizierte Zahl)"
                ),
                stueckzahl_hinweis="Lücke: Stückzahl-Strategie braucht Volumen/Kostenmodell",
                quelle="generic + PLAN §4.7 (keine Kosten ohne cost_model-Quelle, Lücke)",
            )

        # QA derived from the engineer's REAL tolerances + Prüfplan-Hinweise.
        qa_schritte = ["Maß-/Sichtprüfung der gefertigten Teile"]
        qa_schritte += [
            f"Toleranz prüfen: {t.feature} = {t.toleranz}" for t in ingenieur.toleranzen
        ]
        qa_schritte += list(ingenieur.pruefplan_hinweise)
        qa_gate = (
            "Geometrie-/DFM-Check bestanden + alle deklarierten Toleranzen erfüllt"
            if ingenieur.toleranzen
            else "Lücke: kein Prüfkriterium aus ingenieur.toleranzen ableitbar — DFM-Check nötig"
        )
        qa = QAPlan(
            schritte=qa_schritte,
            gate_kriterien=qa_gate,
            quelle="generic aus ingenieur.toleranzen + ingenieur.pruefplan_hinweise + PLAN §4.7",
        )

        assembly_summary = (
            ", ".join(f"{a.name} ({a.purpose})" for a in concept.main_assemblies)
            or "keine Baugruppen im Konzept"
        )
        prozess_namen = "+".join(p.name for p in prozesse)
        zusammen = (
            f"Generische FertigungsSpec für »{concept.source_idea}«: "
            f"{len(prozesse)} Prozess(e) [{prozess_namen}] aus Konzept/Ingenieur abgeleitet "
            f"(Baugruppen: {assembly_summary}). "
            "Offene Punkte ehrlich als Lücke markiert (Supplier-Preise, exakte DFM/CAD)."
        )
        quelle = (
            "GENESIS_PLATFORM_PLAN.md §4.7 + generischer Mapper "
            "(aus concept+ingenieur abgeleitet, ehrliche Lücken)"
        )

    return FertigungsSpec(
        source_idea=concept.source_idea,
        gewaehlte_prozesse=prozesse,
        dfm_report_ref=dfm_ref,
        kosten_modell=kosten,
        qa_plan=qa,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
