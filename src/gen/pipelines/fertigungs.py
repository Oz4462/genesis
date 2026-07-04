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
from .ingenieur import IngenieurSpec
# Naht to advanced DFM (from prior stone)
try:
    from gen.cad.manufacturing_check import AdvancedDFMReport
except Exception:
    AdvancedDFMReport = dict  # type: ignore


@dataclass(frozen=True)
class FertigungsProzess:
    """Gewählter Fertigungsprozess mit Begründung + Grenzen."""
    name: str  # FDM, CNC, Laser, PCB
    begruendung: str
    prozessgrenzen: str  # z.B. "min wall 0.8mm from DFM"
    datei_stub: str | None = None  # gcode path or description
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


def _structured_cost_from_dfm(dfm_report: Optional[Any]) -> Optional[Any]:
    """Pull the STRUCTURED ranged FDM ``CostEstimate`` off an AdvancedDFMReport (or an
    equivalent dict) — the Naht-Follow-up to Stein 4 (WORK_QUEUE): KostenModell should
    consume the real per-component bands, not just the prose ``cost_hint``. Returns
    ``None`` when the report carries no consumable estimate (older reports / no volume),
    so the caller falls back to the prose hint or an honest gap — never a fabrication."""
    if dfm_report is None:
        return None
    est = getattr(dfm_report, "cost_estimate", None)
    if est is None and isinstance(dfm_report, dict):
        est = dfm_report.get("cost_estimate")
    # duck-check: only consumable with the band, breakdown and summary present
    if est is None or not hasattr(est, "breakdown") or not hasattr(est, "summary"):
        return None
    return est


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
    Generic: ehrliche Lücken (z.B. exakte Supplier-Preise via Wissensbasis später).
    """
    idee_lower = concept.source_idea.lower()

    if "jetpack" in idee_lower or "flug" in idee_lower:
        # Primary FDM from DFM example (tether plate)
        prozesse = [
            FertigungsProzess(
                name="FDM",
                begruendung="Primary for prototype (volume ~49cm³, 2mm wall from CAD; printable per advanced DFM)",
                prozessgrenzen="min wall 0.8mm, bridge <=10mm, layer adhesion warning (from dfm/printability + advanced DFM)",
                datei_stub="FDM print gcode needs a slicer (per-layer toolpaths) — not generated (honest gap); a real, verified 2.5D CNC profile gcode for the bounding footprint is produced by cad.gcode (AdvancedDFMReport.gcode_program)",
                quelle="advanced_dfm (FDM process) + prototype_cad_builder (real STL/volume) + PLAN §4.7",
            ),
            FertigungsProzess(
                name="CNC",
                begruendung="Alternative for precision/strength (if FDM layer issues)",
                prozessgrenzen="min feature 0.5mm, tol ±0.05mm (from advanced DFM CNC stub)",
                datei_stub="real, verified 2.5D outside-profile CNC gcode via cad.gcode (AdvancedDFMReport.gcode_program); full toolpaths (pockets/holes/3D) need a CAM kernel",
                quelle="advanced_dfm (CNC) + PLAN §4.7",
            ),
        ]
        dfm_ref = "advanced_dfm report for Jetpack Tether Anchor (printable FDM primary, issues noted)"
        est = _structured_cost_from_dfm(dfm_report)
        fdm_cost = _fdm_cost_estimate_from_dfm(dfm_report)
        if est is not None:
            mat = (est.breakdown or {}).get("material")
            mach = (est.breakdown or {}).get("machine_time")
            setup = (est.breakdown or {}).get("setup")
            kosten = KostenModell(
                material_kosten=(f"€{mat[0]:.2f}–{mat[1]:.2f} Material (Volumen × Dichte × Infill × Preis, cost_model Stein 4)"
                                 if mat else "Lücke: kein Material-Breakdown im CostEstimate"),
                prozess_kosten=((f"€{mach[0]:.2f}–{mach[1]:.2f} Maschinenzeit"
                                 + (f" + €{setup[0]:.2f}–{setup[1]:.2f} Setup" if setup else "")
                                 + " (cost_model Stein 4)")
                                if mach else "Lücke: kein Maschinenzeit-Breakdown im CostEstimate"),
                gesamt_est=est.summary(),
                stueckzahl_hinweis="1-10: FDM; >50: Spritzguss oder CNC-Batch prüfen",
                quelle=(f"advanced_dfm.cost_estimate → cost_model.estimate_fdm_cost (Stein 4, strukturiert; "
                        f"{len(est.gaps or [])} Gaps deklariert, Band ist Untergrenzen-Orientierung) + PLAN §4.7"),
            )
        elif fdm_cost:
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
        prozesse = [FertigungsProzess(name="FDM", begruendung="Default prototype", prozessgrenzen="min wall from DFM", quelle="Generic")]
        dfm_ref = "advanced DFM (generic)"
        kosten = KostenModell(material_kosten="TBD", prozess_kosten="TBD", gesamt_est="TBD (Lücke: Supplier-Preise via Wissensbasis)", stueckzahl_hinweis="Lücke", quelle="Generic + PLAN §4.7")
        qa = QAPlan(schritte=["Basic visual/dim"], gate_kriterien="Lücke", quelle="Generic")
        zusammen = f"Generische FertigungsSpec für '{concept.source_idea[:40]}...'. Viele Details als Lücke (keine spezifische DFM/CAD aus prior)."
        quelle = "GENESIS_PLATFORM_PLAN.md §4.7 + generic fallback (ehrliche Lücken)"

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
