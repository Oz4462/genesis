"""learning_integrator — zwölfter (letzter) Grenzverschiebungs-Modul (Meta: 8-Schritt Lern- und Verbesserungsmaschine).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3 Tabelle + §3.8:
- Aufgabe: zieht aus jedem Test neue Regeln, Failure-Modes und Wissenseinträge.
- Output: `LearningDelta`.
- Meta: Der 8-Schritt-Prozess (Lern- und Verbesserungsmaschine) wird auf die Grenzverschiebung selbst angewendet:
  1. Lücke erkennen (aus SafetyGate / Bench / Frontier / revised)
  2. Verbesserungsvorschlag beschreiben
  3. Quellen/Beispiele/Gegenbeispiele sammeln (Provenance)
  4. Modul/Regel erweitern oder neue Regel
  5. Gate/Validator erzeugen
  6. Mit Test beweisen
  7. In Wissensbasis schreiben (hier: Delta)
  8. Erst dann als Teil des Systems gelten (nächster Zyklus nutzt Delta)

Erster Stein: Datamodel + deterministischer Integrator für das Jetpack-Beispiel
( extrahiert aus safety_ladder + prior revised/breakthrough konkrete Regeln + Failure-Modes + Vorschläge für nächste Front-Revision ).
Später: Volle Verknüpfung mit Wissensbasis, boundary_reviser (füttert Delta zurück), live Zyklen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .development_front import is_jetpack_traum

if TYPE_CHECKING:
    from .safety_ladder import SafetyStagePlan
    from .boundary_reviser import RevisedFrontMap


@dataclass(frozen=True)
class LearningRule:
    """Eine neue oder verbesserte Regel (mit Evidence)."""
    regel: str
    evidenz: str
    quelle: str | None = None


@dataclass(frozen=True)
class FailureMode:
    """Ein identifizierter Failure-Mode aus Test/Gate."""
    modus: str
    aus_stufe: str
    evidenz: str
    quelle: str | None = None


@dataclass(frozen=True)
class WissensEintrag:
    """Ein Eintrag für die spätere Wissensbasis (Formel, Lesson, Trade-off)."""
    titel: str
    inhalt: str
    evidenz: str
    quelle: str | None = None


@dataclass(frozen=True)
class LearningDelta:
    """Der Output des learning_integrator (Meta 8-Schritt)."""
    source_traum: str
    rules: list[LearningRule]
    failure_modes: list[FailureMode]
    wissens_eintraege: list[WissensEintrag]
    naechste_verbesserungsvorschlaege: list[str]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def apply_learning_cycle(
    safety: Optional["SafetyStagePlan"] = None,
    revised: Optional["RevisedFrontMap"] = None,
    *,
    run_id: str | None = None,
) -> LearningDelta:
    """
    Erste Version des learning_integrator.

    Wendet den 8-Schritt-Prozess (§3.8) auf die kumulierten Grenz-Outputs an.
    Für Jetpack: extrahiert konkrete Regeln/Failure-Modes aus den 6 Safety-Stufen + revised Tech + breakthrough.
    Produziert Delta, das später boundary_reviser / neue front / safety verbessern kann.

    Hinweis (ehrlich, Review F4): aus ``safety``/``revised`` wird derzeit nur
    ``source_traum`` konsumiert; Stufen/Revisions sind reservierte Inputs (API)
    und werden noch nicht ausgewertet (Lücke — keine Schein-Auswertung). Die
    Modul-Namen in den Regel-quellen sind Plan-Anker, keine Input-Auswertung.
    Review F6: Erkenntnisse, die auf synthetischer Front-Evidenz beruhen
    (fabrizierte breakthrough_watch-Items), sind explizit so gelabelt.
    """
    traum = (safety.source_traum if safety else (revised.source_traum if revised else "unbekannt"))

    rules: list[LearningRule] = []
    failures: list[FailureMode] = []
    wissens: list[WissensEintrag] = []
    vorschlaege: list[str] = []

    if is_jetpack_traum(traum):  # Wortgrenzen-Trigger (Review F5)
        # 8-Schritt angewendet (hier als Delta kodiert; Schritte 1-3 aus Input, 4-7 in Delta, 8 = nächste Nutzung)
        rules = [
            LearningRule(
                regel="Solid-State Battery (Sulfid, >350 Wh/kg Pack-Level) WÜRDE portable Energie von needs_breakthrough zu possible_but_unsafe_directly verschieben — Aufwertung erst nach verifizierter Evidenz (synthetische Front-Items werten nicht auf).",
                evidenz="Synthetisches Frontier Item (unverifiziert); boundary_reviser notiert nur Kandidaten.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + breakthrough_watch Solid-State (synthetisch) + boundary_reviser (Plan-Anker, Input nicht ausgewertet — Review F4)",
            ),
            LearningRule(
                regel="Dissimilar redundant FC + <50ms Switch + <1kg erlaubt leichtere P2-Architektur; Recovery-Zeit <3s bleibt hartes Gate.",
                evidenz="Frontier Verfahren + S2/S4 messkriterien (Recovery <3s in allen Failure-Tests).",
                quelle="breakthrough_watch dissimilar FC (synthetisch) + safety_ladder S2/S4 + teststand (Plan-Anker, Input nicht ausgewertet — Review F4)",
            ),
            LearningRule(
                regel="Jede Safety-Stufe muss ein explizites Gate + messkriterien + abbruch haben; fehlendes Gate = Abbruch vor nächster Stufe.",
                evidenz="Alle 6 Stufen in safety_ladder; S3 (gesichert bemannt) fordert 100% sichere Aborts.",
                quelle="safety_ladder.py (6 Stages) + PLAN §3.3 safety_ladder",
            ),
        ]
        failures = [
            FailureMode(
                modus="Single-Failure ohne sichere Recovery in Simulation/Stand (S0/S1)",
                aus_stufe="S0 — Modell + Simulation / S1 — Prüfstand",
                evidenz="Abbruchkriterium in S0: 'Simulation zeigt ungelöste Single-Failure'; S1 erbt Bench-Abbruch.",
                quelle="safety_ladder S0/S1 + bench_test_runner (Plan-Anker, Input nicht ausgewertet — Review F4)",
            ),
            FailureMode(
                modus="Recovery >3s oder fehlende dissimilar Redundanz bei free flight (S2/S4)",
                aus_stufe="S2 — Unbemannt free / S4 — Bemannt free low",
                evidenz="Messkriterium 'Recovery <3s in allen Failure-Tests' + revised Recovery aus breakthrough.",
                quelle="safety_ladder S2/S4 + revised + breakthrough",
            ),
        ]
        wissens = [
            WissensEintrag(
                titel="Jetpack Energy Model Update 2026 (SYNTHETISCH, unverifiziert)",
                inhalt="SYNTHETISCHE Front-Evidenz (fabriziertes Plan-Beispiel, keine echte Messung): WENN Solid-State >350 Wh/kg (Lab) verifiziert würde, wäre portable Energie für 5+ min free flight unter 100kg+ Pilot-Last möglich (Kandidat possible_but_unsafe_directly).",
                evidenz="Synthetisches Frontier-Item (evidence_level='synthetic') — kein Wissens-Fakt, nur Kandidat bis zur Verifikation (Review F6).",
                quelle="breakthrough_watch (synthetisch) + boundary_reviser Kandidaten-Notiz + safety S4 (Plan-Anker)",
            ),
            WissensEintrag(
                titel="Safety Gate Invariante",
                inhalt="Jede Stufe muss Gate + messkriterien + abbruch haben. Ohne Gate keine Freigabe zur nächsten Stufe (Defense-in-depth).",
                evidenz="Vollständige 6-Stufen-Leiter in safety_ladder.",
                quelle="safety_ladder + GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        vorschlaege = [
            "boundary_reviser + development_front: 'portable Energie' Grenztyp erst nach VERIFIZIERTER Solid-State-Evidenz aufwerten (synthetische Items werten nicht auf).",
            "safety_ladder S2/S4: Recovery <3s als hartes Gate in allen free-flight Stufen beibehalten; neue dissimilar FC als zusätzliches Kriterium prüfen.",
            "learning_integrator nächste Runde: Delta in Wissensbasis schreiben und bei neuer Idee als Kontext für front_mapper nutzen.",
            "8-Schritt-Zyklus schließen: Nach Bench/Safety neue Delta erzeugen und revised_front füttern (Lernmaschine aktiv).",
        ]
        zusammenfassung = (
            "LearningDelta (Jetpack): 3 Rules (Solid-State Shift, dissimilar FC + Recovery, Gate-Invariante), "
            "2 Failure-Modes (Single-Failure in Sim/Stand, Recovery >3s), 2 Wissens-Einträge, 4 Verbesserungsvorschläge. "
            "8-Schritt-Prozess (§3.8) angewendet: Lücken aus safety/revised erkannt → Delta mit Evidence → Vorschläge für nächsten Zyklus."
        )
    else:
        rules = [
            LearningRule(
                regel="Generische Idee → minimales Delta: mindestens eine Rule aus erster Safety-Stufe extrahieren.",
                evidenz="S0 Gate 'Vollständige Coverage' als Basis.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + safety_ladder generic",
            ),
        ]
        failures = []
        wissens = []
        vorschlaege = ["Nächster Zyklus: volle Analyse mit breakthrough + bench erforderlich."]
        zusammenfassung = "Minimal-LearningDelta für noch nicht detailliert analysierte Idee (8-Schritt nur angetippt)."

    return LearningDelta(
        source_traum=traum,
        rules=rules,
        failure_modes=failures,
        wissens_eintraege=wissens,
        naechste_verbesserungsvorschlaege=vorschlaege,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="learning_integrator (12/12 letzter Stein) + safety/revised (nur source_traum konsumiert; Stufen/Revisions noch nicht ausgewertet — Lücke) + GENESIS_PLATFORM_PLAN.md §3.3 + §3.8",
    )
