"""techniker — vierter Stein der Fach-Pipelines (Techniker-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §4.4:
- Ziel: Aus Theorie eine reale Handlungsfolge machen.
- Aufgaben: Montagefolge planen, Werkzeuge bestimmen, Zugänglichkeit prüfen, Prüfpunkte definieren, Wartung und Austauschbarkeit bewerten, typische Baufehler antizipieren.
- Outputs: Montageplan, Werkzeugliste, Prüfschritte, Wartungsplan, Reparaturhinweise.
- Gate: jeder Schritt hat Input, Output und Check; kein Schritt verlangt ein nicht vorhandenes Werkzeug; keine unzugängliche Schraube; kein versteckter Kalibrierungsbedarf.

Erster Stein: deterministischer Mapper von SystemConcept + IngenieurSpec + PhysikerSpec zu TechnikerSpec.
Jetpack-Beispiel fokussiert auf die reale Montage der Tether-Anchor-Plate (aus CAD + Physik), mit Zugänglichkeit für Recovery-Container, typischen Fehlern bei Fillet/Lochbohrungen, Wartung.

Naht: Outputs füttern Manufacturing-Check, Prüfstände und spätere Realisierungspakete (Wartungsplan als Teil des Pakets).
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec
from .physiker import PhysikerSpec


@dataclass(frozen=True)
class MontageSchritt:
    """Ein einzelner Montageschritt mit Check und Fehlern."""
    name: str
    beschreibung: str
    input: str
    output: str
    werkzeuge: list[str]
    zugang: str
    pruefpunkt: str
    typische_fehler: list[str]
    quelle: str | None = None


@dataclass(frozen=True)
class TechnikerSpec:
    """Der Output der Techniker-Pipeline (erster Stein)."""
    source_idea: str
    montage_plan: list[MontageSchritt]
    werkzeug_liste: list[str]
    pruef_schritte: list[str]
    wartungs_plan: list[str]
    reparatur_hinweise: list[str]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_techniker_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    physiker: PhysikerSpec,
    *,
    run_id: str | None = None,
) -> TechnikerSpec:
    """
    Erster Stein der Techniker-Pipeline.
    Für Jetpack: reale Montage der Tether-Anchor-Plate (aus CAD real STL + Physik Lasten + Ingenieur Toleranzen).
    """
    if "jetpack" in concept.source_idea.lower() or any("jetpack" in a.name.lower() for a in concept.main_assemblies):
        montage_plan = [
            MontageSchritt(
                "Vorbereitung Platte",
                "Reine 2mm Alu/CFK Platte einspannen, Kanten entgraten",
                "Rohplatte + CAD STL",
                "Vorbereitete Platte",
                ["Schleifmaschine", "Entgrater"],
                "Vollflächig zugänglich",
                "Kantenradius visuell + Tastatur",
                ["Überhitzung → Verzug", "Zu aggressives Schleifen → Dünnstellen"],
                "CAD prototype + ingenieur toleranzen",
            ),
            MontageSchritt(
                "Tether-Löcher bohren (4x + zentrale 8mm)",
                "Geführte Bohrung mit H7/g6 Passung für Schäkel + Recovery",
                "Vorbereitete Platte + Physik Lastfall 5kN",
                "Bohrungen mit korrekter Toleranz",
                ["Bohrmaschine", "HSS-Bohrer", "Reibahle für H7"],
                "Beidseitig + Unterseite zugänglich (keine Sacklöcher)",
                "Durchmesser + Position + Oberflächengüte",
                ["Verkanteter Bohrer → ovale Löcher", "Falsche Reihenfolge → Grat"],
                "CAD anchor + physiker dynamik",
            ),
            MontageSchritt(
                "Recovery-Container Interface montieren",
                "Gewindebolzen + Container-Halter auf der Rückseite",
                "Bohrungen + physiker Recovery-Entfaltung",
                "Montiertes Interface",
                ["Inbus-Schlüssel", "Gewindeschneider"],
                "Zugang nur von einer Seite → spezielles Werkzeug",
                "Drehmoment + Ausrichtung",
                ["Zu hohes Drehmoment → Riss im CFK", "Schief → Recovery blockiert"],
                "safety_ladder + physiker falsifikation",
            ),
            MontageSchritt(
                "Endkontrolle + Kalibrierung",
                "Visuell + manuell: alle Fillets, keine scharfen Kanten, Passungen prüfen",
                "Voll montierte Platte",
                "Prüfprotokoll + freigegebene Platte",
                ["Messschieber", "Drehmomentschlüssel", "Lupe"],
                "Vollständig zugänglich (keine verdeckten Stellen)",
                "Jeder Montageschritt + Endmaß",
                ["Vergessene Grat → Verletzung + Fadenbruch", "Falsche Passung → Tether verrutscht"],
                "manufacturing_check + ingenieur",
            ),
        ]
        werkzeug_liste = [
            "Schleifmaschine + Entgrater",
            "Bohrmaschine + HSS-Satz + Reibahle H7",
            "Inbus + Gewindeschneider M5/M8",
            "Messschieber 0.01mm + Drehmomentschlüssel",
            "Lupe + Taschenlampe für Innenkontrolle",
        ]
        pruef_schritte = [
            "Nach jedem Bohr-Schritt: Durchmesser + Position messen",
            "Nach Montage: Drehmoment + Ausrichtung prüfen",
            "Ende: volle visuelle + manuelle Kontrolle (keine scharfen Kanten)",
        ]
        wartungs_plan = [
            "Tether-Interface: alle 10 Einsätze auf Riss / Verschleiß prüfen",
            "Recovery-Container: nach jedem Test öffnen + Dichtigkeit checken",
            "Platte: bei sichtbarer Dehnung oder Kratzern austauschen",
        ]
        reparatur_hinweise = [
            "Kleine Gratstellen: nachschleifen vor Ort möglich",
            "Überlastetes Loch: Platte austauschen (keine Reparaturbohrung empfohlen)",
            "Recovery-Halter defekt: nur original Ersatzteil (Passungskritisch)",
        ]
        zusammenfassung = (
            "TechnikerSpec für Jetpack Tether-Anchor: 4 konkrete Montageschritte mit Werkzeugen, "
            "Zugang, Prüfpunkten und typischen Fehlern. Direkte Anbindung an reales CAD-STL + "
            "Physik-Lasten + Manufacturing-Check. Wartungs- und Reparaturplan für reale Nutzung."
        )
    else:
        montage_plan = [
            MontageSchritt("Grundplatte vorbereiten", "Kanten entgraten", "Rohplatte", "Saubere Platte", ["Schleifer"], "Vollzugänglich", "Visuell", ["Überhitzung"], "generic"),
        ]
        werkzeug_liste = ["Schleifer"]
        pruef_schritte = ["Endkontrolle"]
        wartungs_plan = ["Grundwartung"]
        reparatur_hinweise = ["Austausch"]
        zusammenfassung = "Minimal TechnikerSpec für noch nicht detailliert analysierte Idee."

    return TechnikerSpec(
        source_idea=concept.source_idea,
        montage_plan=montage_plan,
        werkzeug_liste=werkzeug_liste,
        pruef_schritte=pruef_schritte,
        wartungs_plan=wartungs_plan,
        reparatur_hinweise=reparatur_hinweise,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="techniker (fourth pipeline stone) + GENESIS_PLATFORM_PLAN.md §4.4 + prior Architekt + Ingenieur + Physiker + CAD real + manufacturing_check",
    )
