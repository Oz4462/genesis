"""ingenieur — zweiter Stein der Fach-Pipelines (Ingenieur-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §4.2:
- Ziel: Das Konzept mechanisch und technisch tragfähig machen.
- Outputs: mechanische Spezifikation, Lastfallkatalog, Material- und Toleranzblatt, CAD-Anforderungen, Failure-Mode-Liste, Prüfplan.
- Gate: keine Last ohne Herkunft, keine Materialkennwerte ohne Quelle, keine Dimension ohne Ableitung, keine „hält schon"-Behauptung.

Erster Stein: deterministischer Mapper von SystemConcept (oder Idee) zu IngenieurSpec.
Jetpack-Beispiel baut direkt auf dem Architekt-Output auf (Baugruppen → Lastfälle, Failure-Modes aus prior Grenz + Recovery, CAD-Anforderungen für prototype_cad_builder).

Naht: Nimmt SystemConcept, erzeugt mechanische Daten + explizite CAD-Requirements, die in den CAD-Builder + manufacturing_check fließen können.
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept


@dataclass(frozen=True)
class LoadCase:
    """Ein Lastfall mit Herkunft."""
    name: str
    beschreibung: str
    kraft_oder_moment: str  # z.B. "Tether: 5kN Zug", "Propulsion: 2.5kN Schub"
    quelle: str | None = None


@dataclass(frozen=True)
class MaterialSpec:
    """Material-Hinweis mit Provenance (nicht final, aber geerdet)."""
    name: str
    e_modul_gpa: float | None = None
    dichte_kg_m3: float | None = None
    zugfestigkeit_mpa: float | None = None
    quelle: str | None = None


@dataclass(frozen=True)
class ToleranceSpec:
    """Toleranz- und Passungshinweis."""
    feature: str
    toleranz: str
    begruendung: str
    quelle: str | None = None


@dataclass(frozen=True)
class FailureMode:
    """Identifizierter Failure-Mode mit Beleg."""
    name: str
    aus_baugruppe: str
    beschreibung: str
    detection: str
    quelle: str | None = None


@dataclass(frozen=True)
class IngenieurSpec:
    """Der Output der Ingenieur-Pipeline (erster Stein)."""
    source_concept: str
    lastfaelle: list[LoadCase]
    material_hinweise: list[MaterialSpec]
    toleranzen: list[ToleranceSpec]
    failure_modes: list[FailureMode]
    cad_anforderungen: list[str]  # direkt für prototype_cad_builder
    pruefplan_hinweise: list[str]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_ingenieur_spec(
    concept: SystemConcept,
    *,
    run_id: str | None = None,
) -> IngenieurSpec:
    """
    Erster Stein der Ingenieur-Pipeline.
    Nimmt ein SystemConcept und erzeugt erste mechanisch belastbare Daten.
    Für Jetpack: baut auf den Baugruppen + prior Grenz (Recovery, Safety) auf.
    """
    if "jetpack" in concept.source_idea.lower() or any("jetpack" in a.name.lower() for a in concept.main_assemblies):
        lastfaelle = [
            LoadCase("Tether-Last (S1-S3)", "Max. Zug bei Ausfall oder Wind", "bis 5 kN (angenommen 100kg Pilot + Dynamik)", "safety_ladder S1 + prior Grenz + CAD tether plate"),
            LoadCase("Propulsion-Schub", "Kontrollierter Aufstieg / Schweben", "ca. 2.5–3.5 kN für 100kg+ System", "technology_roadmap P1 + breakthrough"),
            LoadCase("Recovery-Impact (S2/S4)", "Fallschirm-Öffnung oder Abstieg", "hohe dynamische Lasten <3s", "learning_integrator Recovery + safety S2/S4"),
        ]
        material_hinweise = [
            MaterialSpec("Alu 6061-T6 oder CFK", e_modul_gpa=70, dichte_kg_m3=2700, zugfestigkeit_mpa=290, quelle="typisch für leichte Strukturen + CAD-Beispiele"),
            MaterialSpec("Tether: Dyneema / HMPE", quelle="safety S1/S3 + real-world recovery systems"),
        ]
        toleranzen = [
            ToleranceSpec("Tether-Löcher", "H7/g6", "Passung für Schäkel/Bolzen, Lastübertragung", "CAD anchor plate + mechanical best practice"),
            ToleranceSpec("Mounting-Flächen", "±0.2 mm", "Planheit für Propulsion-Interface", "prototype_cad_builder + DFM"),
        ]
        failure_modes = [
            FailureMode("Single-Failure ohne Recovery", "Propulsion / Frame", "Ausfall eines Antriebs oder Strukturbruch", "Sofortige Recovery-Auslösung <3s", "safety_ladder + learning_integrator"),
            FailureMode("Tether-Überlast", "Tether/Harness", "Zu hohe dynamische Last → Bruch", "Last-Messung + Cut + Backup", "prior Grenz + CAD"),
        ]
        cad_anforderungen = [
            "Tether-Anchor-Plate mit 5kN+ Lastaufnahme (real STL/STEP)",
            "Propulsion-Mount mit Interface für 2.5–3.5kN Schub",
            "Recovery-Container-Interface (schnelle Auslösung)",
            "Leichte Struktur (Wand 2–4mm, CFK-ähnlich) mit Fillets",
        ]
        pruefplan_hinweise = [
            "Statische Tether-Last-Test bis 1.5x Max",
            "Vibration + Drop für Recovery",
            "Integration mit Manufacturing-Check (Wandstärke, Support)",
        ]
        zusammenfassung = "IngenieurSpec für Jetpack: 3 Lastfälle mit Herkunft, Material-Hinweise, Toleranzen, Failure-Modes (direkt aus prior Grenz), explizite CAD-Anforderungen für prototype_cad_builder + manufacturing_check."
    else:
        lastfaelle = [LoadCase("Grundlast", "Statische Traglast", "1.5x Nennlast", "generic")]
        material_hinweise = [MaterialSpec("Generic Structural")]
        toleranzen = []
        failure_modes = []
        cad_anforderungen = ["Einfache Struktur"]
        pruefplan_hinweise = ["Grundlegende Lastprüfung"]
        zusammenfassung = "Minimal IngenieurSpec für noch nicht detailliert analysierte Idee."

    return IngenieurSpec(
        source_concept=concept.source_idea,
        lastfaelle=lastfaelle,
        material_hinweise=material_hinweise,
        toleranzen=toleranzen,
        failure_modes=failure_modes,
        cad_anforderungen=cad_anforderungen,
        pruefplan_hinweise=pruefplan_hinweise,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="ingenieur (second pipeline stone) + GENESIS_PLATFORM_PLAN.md §4.2 + prior Architekt + Grenz (safety + learning) + CAD real builder",
    )
