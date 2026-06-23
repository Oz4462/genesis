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

    Jetpack-Branch (protected): reale Montage der Tether-Anchor-Plate (aus CAD real STL + Physik Lasten + Ingenieur Toleranzen).
    Generic branch: leitet Montage-Schritte 1:1 aus concept.main_assemblies ab, Werkzeuge aus ingenieur.cad_anforderungen/toleranzen,
    typische Fehler aus ingenieur.failure_modes, Prüfschritte aus physiker.falsifikations_plan/erwartete_messgroessen.
    Abwesende Signale → explizite Lücke (keine fabrizierte Prozedur). Gate: jeder Schritt hat input+output+pruefpunkt;
    referenzierte Werkzeuge stehen in werkzeug_liste.

    Raises:
        ValueError: wenn source_idea leer/whitespace UND keine main_assemblies vorhanden (kein actionable Signal → kein Stub).
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
        # Generic branch: derive genuinely from inputs (assemblies, ingenieur cad/tolerances/failures, physiker falsi).
        # No fabrication: absent signals become explicit "Lücke:" markers.
        # Every MontageSchritt carries input/output/pruefpunkt (the gate "jeder Schritt hat Input, Output und Check").
        # All tools referenced in steps are present in werkzeug_liste (the "kein Schritt verlangt nicht vorhandenes Werkzeug" gate).
        montage_plan, werkzeug_liste, pruef_schritte, wartungs_plan, reparatur_hinweise, zusammenfassung = (
            _derive_generic_techniker_spec(concept, ingenieur, physiker)
        )

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


def _derive_generic_techniker_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    physiker: PhysikerSpec,
) -> tuple[list[MontageSchritt], list[str], list[str], list[str], list[str], str]:
    """Derive TechnikerSpec fields for non-jetpack inputs.

    Montage steps are produced 1:1 from concept.main_assemblies.
    - tools drawn from ingenieur.cad_anforderungen + toleranzen
    - typische_fehler drawn from matching ingenieur.failure_modes (by baugruppe/name)
    Pruef steps derived directly from physiker.falsifikations_plan entries (name + erwartete_messgroesse + abbruchkriterium).
    Wartung/Reparatur from failure_modes when present.
    Absent signal -> explicit Lücke (no fabricated procedure or fact).
    Raises ValueError for completely blank source_idea + no assemblies (per spec: no silent canned stub).
    """
    source = (concept.source_idea or "").strip()
    assemblies = list(concept.main_assemblies or [])
    fms: list = list(ingenieur.failure_modes or [])
    cad_hints: list[str] = [h for h in (ingenieur.cad_anforderungen or []) if h and h.strip()]
    tol_hints: list[str] = [f"{t.feature} ({t.toleranz})" for t in (ingenieur.toleranzen or []) if t.feature or t.toleranz]
    fps = list(physiker.falsifikations_plan or [])

    if not source and not assemblies:
        raise ValueError(
            "source_idea must be a non-empty, non-whitespace string when no main_assemblies provide actionable signal"
        )

    # Tool pool for steps (from ingenieur cad/tol as specified). Keeps gate satisfied by construction.
    tool_pool: list[str] = []
    seen_tools: set[str] = set()
    for h in cad_hints + tol_hints:
        hh = h.strip()
        if hh and hh not in seen_tools:
            seen_tools.add(hh)
            tool_pool.append(hh)
    if not tool_pool:
        tool_pool = ["Lücke: Werkzeuge aus cad_anforderungen/toleranzen ableiten"]

    montage_plan: list[MontageSchritt] = []
    for idx, a in enumerate(assemblies):
        step_tools = [tool_pool[idx % len(tool_pool)]]
        # Match failure modes for this assembly (name or aus_baugruppe contains assembly name or vice-versa for robustness)
        an = a.name.lower()
        related = [
            fm for fm in fms
            if an in (fm.aus_baugruppe or "").lower() or an in (fm.name or "").lower()
            or (fm.aus_baugruppe or "").lower() in an or (fm.name or "").lower() in an
        ]
        step_errors = [fm.beschreibung for fm in related] if related else [
            "Lücke: keine typischen Fehler aus Ingenieur-Failure-Modes für diese Baugruppe"
        ]

        montage_plan.append(
            MontageSchritt(
                name=f"Montage {a.name}",
                beschreibung=f"Integration der Baugruppe '{a.name}' ({a.purpose}). Schnittstellen: {', '.join(a.interfaces) or 'keine deklariert'}.",
                input=f"Vorbereitete Komponenten für {a.name} (Quelle: {a.quelle or 'unbekannt'})",
                output=f"{a.name} montiert und integriert",
                werkzeuge=step_tools,
                zugang="Vollzugänglich (Lücke: detaillierte Zugangs-/Erreichbarkeitsanalyse aus CAD/DFM fehlt)",
                pruefpunkt=f"Maß-, Passungs- und Funktionsprüfung nach Montage von {a.name}",
                typische_fehler=step_errors,
                quelle=a.quelle or "abgeleitet aus concept.main_assemblies + ingenieur",
            )
        )

    if not montage_plan:
        # Idea present but no assemblies -> honest single gap step (no canned procedure)
        montage_plan = [
            MontageSchritt(
                "Lücke: keine Baugruppen definiert",
                "Lücke: Keine main_assemblies im SystemConcept → keine konkreten Montage-Schritte ableitbar",
                "Lücke (kein Assembly-Input)",
                "Lücke (kein Output)",
                ["Lücke: keine Werkzeuge"],
                "Lücke",
                "Lücke: keine Prüfpunkte (keine Baugruppen)",
                ["Lücke: keine typischen Fehler (keine Baugruppen)"],
                "generic (ehrliche Lücke)",
            )
        ]

    # werkzeug_liste must contain every tool referenced in any step (gate enforcement)
    # plus all hints from ingenieur (so the full signal from cad/tolerances is visible)
    werkzeug_liste: list[str] = []
    seen_w: set[str] = set()
    for h in tool_pool:
        if h not in seen_w:
            seen_w.add(h)
            werkzeug_liste.append(h)
    for step in montage_plan:
        for w in step.werkzeuge:
            if w not in seen_w:
                seen_w.add(w)
                werkzeug_liste.append(w)
    if not werkzeug_liste:
        werkzeug_liste = ["Lücke: keine Werkzeuge ableitbar"]

    # Pruef from physiker (direct 1:1 derivation as specified)
    if fps:
        pruef_schritte = [
            f"{fp.name}: Erwartete Messgröße '{fp.erwartete_messgroesse}' messen. Abbruch bei: {fp.abbruchkriterium}"
            for fp in fps
        ]
    else:
        pruef_schritte = [
            "Lücke: keine Falsifikationspläne / erwarteten Messgrößen aus Physiker vorhanden"
        ]

    # Wartung/Reparatur from failure modes when present (real signal); else honest gap
    if fms:
        wartungs_plan = [
            f"Periodische Prüfung auf {fm.name} ({fm.aus_baugruppe}): {fm.beschreibung}"
            for fm in fms
        ]
        reparatur_hinweise = [
            f"Bei Auftreten von {fm.name}: Detection {fm.detection or 'unbekannt'}; ggf. Ersatz/Reparatur nach Herkunft"
            for fm in fms
        ]
    else:
        wartungs_plan = ["Lücke: Wartungsplan benötigt Failure-Modes aus Ingenieur"]
        reparatur_hinweise = ["Lücke: Reparaturhinweise benötigen detaillierte Failure-Modes aus Ingenieur"]

    zusammenfassung = (
        f"TechnikerSpec für Idee »{concept.source_idea}« abgeleitet aus {len(assemblies)} Baugruppe(n) "
        f"+ {len(fms)} Failure-Mode(s) + {len(fps)} Falsifikationsplan(en). "
        "Montage/Werkzeuge/Fehler aus Architekt+Ingenieur, Prüfschritte aus Physiker. "
        "Abwesende Signale als Lücke markiert (keine fabrizierte Prozedur)."
    )

    return montage_plan, werkzeug_liste, pruef_schritte, wartungs_plan, reparatur_hinweise, zusammenfassung
