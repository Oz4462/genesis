"""techniker — vierter Stein der Fach-Pipelines (Techniker-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §4.4:
- Ziel: Aus Theorie eine reale Handlungsfolge machen.
- Aufgaben: Montagefolge planen, Werkzeuge bestimmen, Zugänglichkeit prüfen, Prüfpunkte definieren, Wartung und Austauschbarkeit bewerten, typische Baufehler antizipieren.
- Outputs: Montageplan, Werkzeugliste, Prüfschritte, Wartungsplan, Reparaturhinweise.
- Gate: jeder Schritt hat Input, Output und Check; kein Schritt verlangt ein nicht vorhandenes Werkzeug; keine unzugängliche Schraube; kein versteckter Kalibrierungsbedarf.

Erster Stein: deterministischer Mapper von SystemConcept zu TechnikerSpec (Kanon-Vorlage).
Jetpack-Beispiel fokussiert auf die Montage einer Tether-Anchor-Plate mit Zugänglichkeit
für Recovery-Container, typischen Fehlern bei Fillet/Lochbohrungen, Wartung.

HONESTY (Schritt-9-Review #2, S-1-Muster): die Parameter ``ingenieur`` und ``physiker``
werden akzeptiert (API-Stabilität), aber derzeit NICHT konsumiert — kein Prior (Ingenieur/
Physiker/CAD/manufacturing_check) speist diesen Mapper. Jeder Output ist eine
PLAN-§4.4-Kanon-Vorlage; die deklarierte Lücke ist die echte Prior-Auswertung. Geplante
Naht (NOCH NICHT verdrahtet): Outputs in Manufacturing-Check, Prüfstände und
Realisierungspakete (Wartungsplan als Teil des Pakets).
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec
from .physiker import PhysikerSpec

#: Honest provenance label (S-1): a canon template, not a consumed prior.
_CANON_QUELLE = "PLAN §4.4 Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)"


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
    Erster Stein der Techniker-Pipeline: deterministische PLAN-§4.4-Kanon-Vorlage je Konzept.

    ``ingenieur`` und ``physiker`` sind für die geplante Prior-Naht reserviert und werden
    derzeit NICHT konsumiert (#2, S-1-Muster) — kein Schritt behauptet eine Ableitung aus
    CAD-STL, Physik-Lasten oder Manufacturing-Check; Lastannahmen sind Kanon-Annahmen.
    """
    if "jetpack" in concept.source_idea.lower():
        montage_plan = [
            MontageSchritt(
                "Vorbereitung Platte",
                "Reine 2mm Alu/CFK Platte einspannen, Kanten entgraten",
                "Rohplatte + Geometrie-Vorlage (Kanon-Annahme)",
                "Vorbereitete Platte",
                ["Schleifmaschine", "Entgrater"],
                "Vollflächig zugänglich",
                "Kantenradius visuell + Tastatur",
                ["Überhitzung → Verzug", "Zu aggressives Schleifen → Dünnstellen"],
                _CANON_QUELLE,
            ),
            MontageSchritt(
                "Tether-Löcher bohren (4x + zentrale 8mm)",
                "Geführte Bohrung mit H7/g6 Passung für Schäkel + Recovery",
                "Vorbereitete Platte + Lastannahme 5kN (Kanon-Annahme)",
                "Bohrungen mit korrekter Toleranz",
                ["Bohrmaschine", "HSS-Bohrer", "Reibahle für H7"],
                "Beidseitig + Unterseite zugänglich (keine Sacklöcher)",
                "Durchmesser + Position + Oberflächengüte",
                ["Verkanteter Bohrer → ovale Löcher", "Falsche Reihenfolge → Grat"],
                _CANON_QUELLE,
            ),
            MontageSchritt(
                "Recovery-Container Interface montieren",
                "Gewindebolzen + Container-Halter auf der Rückseite",
                "Bohrungen + Recovery-Entfaltungsannahme (Kanon-Annahme)",
                "Montiertes Interface",
                ["Inbus-Schlüssel", "Gewindeschneider"],
                "Zugang nur von einer Seite → spezielles Werkzeug",
                "Drehmoment + Ausrichtung",
                ["Zu hohes Drehmoment → Riss im CFK", "Schief → Recovery blockiert"],
                _CANON_QUELLE,
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
                _CANON_QUELLE,
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
            "Zugang, Prüfpunkten und typischen Fehlern; Wartungs- und Reparaturplan. "
            "Alle Schritte sind Kanon-Annahmen (aus keinem Prior abgeleitet) — die geplante "
            "Anbindung an CAD-STL, Physik-Lasten und Manufacturing-Check ist noch nicht verdrahtet."
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
        quelle="techniker (fourth pipeline stone) + GENESIS_PLATFORM_PLAN.md §4.4 — Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)",
    )
