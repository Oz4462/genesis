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


def _rules_from_safety(safety: "SafetyStagePlan") -> tuple[list[LearningRule], list[FailureMode]]:
    """X2: extract rules/failure modes from real SafetyStagePlan stages (not only traum string)."""
    rules: list[LearningRule] = []
    failures: list[FailureMode] = []
    stages = list(getattr(safety, "stages", None) or [])
    for st in stages:
        name = getattr(st, "name", None) or getattr(st, "stufe", None) or "stage"
        gate = getattr(st, "gate", None) or getattr(st, "gate_name", None) or ""
        mess = list(getattr(st, "messkriterien", None) or [])
        abbruch = getattr(st, "abbruch", None) or getattr(st, "abbruchkriterium", None) or ""
        if mess:
            rules.append(
                LearningRule(
                    regel=f"Safety stage {name}: gate requires measurable criteria — {'; '.join(mess[:3])}",
                    evidenz=f"stage={name}; gate={gate}; n_criteria={len(mess)}",
                    quelle="learning_integrator ← safety_ladder.stages (X2 live extract)",
                )
            )
        if abbruch:
            abbruch_s = (
                "; ".join(str(x) for x in abbruch)
                if isinstance(abbruch, (list, tuple))
                else str(abbruch)
            )
            failures.append(
                FailureMode(
                    modus=abbruch_s[:200],
                    aus_stufe=str(name),
                    evidenz=f"abbruch criterion on stage {name}",
                    quelle="learning_integrator ← safety_ladder.stages.abbruch (X2)",
                )
            )
    return rules, failures


def _rules_from_revised(revised: "RevisedFrontMap") -> list[LearningRule]:
    """X2: surface boundary revisions as learning rules (verified vs synthetic labels)."""
    out: list[LearningRule] = []
    for rev in list(getattr(revised, "revisions", None) or []):
        upgraded = rev.new_typ != rev.old_typ
        out.append(
            LearningRule(
                regel=(
                    f"Boundary '{rev.changed_boundary}': {rev.old_typ} → {rev.new_typ}"
                    + (" (UPGRADE)" if upgraded else " (candidate only, no upgrade)")
                ),
                evidenz=rev.reason,
                quelle=rev.quelle or "boundary_reviser.revisions",
            )
        )
    return out


def apply_learning_cycle(
    safety: Optional["SafetyStagePlan"] = None,
    revised: Optional["RevisedFrontMap"] = None,
    *,
    run_id: str | None = None,
) -> LearningDelta:
    """
    Learning integrator (8-Schritt §3.8) over Grenz outputs.

    X2: **consumes** safety.stages (messkriterien/abbruch) and revised.revisions
    in addition to the Jetpack template knowledge. Synthetic frontier evidence
    remains explicitly labeled (Review F6).
    """
    traum = (safety.source_traum if safety else (revised.source_traum if revised else "unbekannt"))

    rules: list[LearningRule] = []
    failures: list[FailureMode] = []
    wissens: list[WissensEintrag] = []
    vorschlaege: list[str] = []

    # X2: always mine real inputs when present
    if safety is not None:
        s_rules, s_fail = _rules_from_safety(safety)
        rules.extend(s_rules)
        failures.extend(s_fail)
    if revised is not None:
        rules.extend(_rules_from_revised(revised))

    if is_jetpack_traum(traum):  # Wortgrenzen-Trigger (Review F5)
        # X2: keep stage/revision extracts, then append Jetpack template knowledge
        rules = list(rules) + [
            LearningRule(
                regel="Solid-State Battery (Sulfid, >350 Wh/kg Pack-Level) WÜRDE portable Energie von needs_breakthrough zu possible_but_unsafe_directly verschieben — Aufwertung erst nach verifizierter Evidenz (synthetische Front-Items werten nicht auf).",
                evidenz="Synthetisches Frontier Item (unverifiziert); boundary_reviser notiert nur Kandidaten.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + breakthrough_watch Solid-State (synthetisch) + boundary_reviser",
            ),
            LearningRule(
                regel="Dissimilar redundant FC + <50ms Switch + <1kg erlaubt leichtere P2-Architektur; Recovery-Zeit <3s bleibt hartes Gate.",
                evidenz="Frontier Verfahren + S2/S4 messkriterien (Recovery <3s in allen Failure-Tests).",
                quelle="breakthrough_watch dissimilar FC (synthetisch) + safety_ladder S2/S4 + teststand",
            ),
            LearningRule(
                regel="Jede Safety-Stufe muss ein explizites Gate + messkriterien + abbruch haben; fehlendes Gate = Abbruch vor nächster Stufe.",
                evidenz="Alle 6 Stufen in safety_ladder; S3 (gesichert bemannt) fordert 100% sichere Aborts.",
                quelle="safety_ladder.py (6 Stages) + PLAN §3.3 safety_ladder",
            ),
        ]
        failures = list(failures) + [
            FailureMode(
                modus="Single-Failure ohne sichere Recovery in Simulation/Stand (S0/S1)",
                aus_stufe="S0 — Modell + Simulation / S1 — Prüfstand",
                evidenz="Abbruchkriterium in S0: 'Simulation zeigt ungelöste Single-Failure'; S1 erbt Bench-Abbruch.",
                quelle="safety_ladder S0/S1 + bench_test_runner",
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
            f"LearningDelta (Jetpack): {len(rules)} rules, {len(failures)} failure-modes, "
            f"{len(wissens)} knowledge entries, {len(vorschlaege)} proposals. "
            "8-Schritt (§3.8): safety.stages + revised.revisions extracted (X2) + template knowledge."
        )
    else:
        if not rules:
            rules = [
                LearningRule(
                    regel="Generische Idee → minimales Delta: mindestens eine Rule aus erster Safety-Stufe extrahieren.",
                    evidenz="S0 Gate 'Vollständige Coverage' als Basis.",
                    quelle="GENESIS_PLATFORM_PLAN.md §3.3 + safety_ladder generic",
                ),
            ]
        if not vorschlaege:
            vorschlaege = ["Nächster Zyklus: volle Analyse mit breakthrough + bench erforderlich."]
        zusammenfassung = (
            f"Minimal LearningDelta (generic): {len(rules)} rules from safety/revised extract; "
            f"{len(failures)} failure-modes. 8-Schritt angetippt (X2)."
        )

    return LearningDelta(
        source_traum=traum,
        rules=rules,
        failure_modes=failures,
        wissens_eintraege=wissens,
        naechste_verbesserungsvorschlaege=vorschlaege,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle=(
            "learning_integrator X2 + safety.stages + revised.revisions + "
            "GENESIS_PLATFORM_PLAN.md §3.3 + §3.8"
        ),
    )


def run_grenz_learning_loop(traum: str, *, run_id: str | None = None) -> dict:
    """X2/X3: full offline chain front → frontier → revise → safety → learning delta.

    Deterministic end-to-end Grenz learning path for tests and CLI demos.
    """
    from .development_front import map_development_front
    from .breakthrough_watch import watch_frontier
    from .boundary_reviser import revise_boundary
    from .safety_ladder import build_safety_ladder

    rid = run_id or "grenz-learn"
    front = map_development_front(traum, run_id=rid)
    frontier = watch_frontier(front, run_id=rid)
    revised = revise_boundary(front, frontier, run_id=rid)
    safety = build_safety_ladder(revised, run_id=rid)
    delta = apply_learning_cycle(safety=safety, revised=revised, run_id=rid)
    # X3: feed delta suggestions back as revision notes on the map (no fake upgrades)
    looped = apply_delta_to_front(revised, delta, run_id=rid)
    return {
        "schema": "genesis-grenz-learning-loop-v1",
        "run_id": rid,
        "traum": traum,
        "n_frontier_items": len(frontier.items),
        "n_revisions": len(revised.revisions),
        "n_safety_stages": len(safety.stages),
        "n_rules": len(delta.rules),
        "n_failure_modes": len(delta.failure_modes),
        "n_proposals": len(delta.naechste_verbesserungsvorschlaege),
        "delta_summary": delta.zusammenfassung,
        "loop_notes": looped.get("notes", []),
        "quelle": "learning_integrator.run_grenz_learning_loop",
    }


def apply_delta_to_front(
    revised: "RevisedFrontMap",
    delta: LearningDelta,
    *,
    run_id: str | None = None,
) -> dict:
    """X3: close the loop — LearningDelta proposals become explicit front notes.

    Does **not** upgrade Grenztypen (that still requires verified frontier evidence).
    """
    notes = []
    for v in delta.naechste_verbesserungsvorschlaege[:8]:
        notes.append(f"learning→front: {v}")
    for r in delta.rules[:5]:
        if "UPGRADE" in r.regel or "candidate only" in r.regel:
            notes.append(f"learning→boundary: {r.regel[:160]}")
    return {
        "run_id": run_id or revised.run_id,
        "source_traum": revised.source_traum,
        "notes": notes,
        "n_notes": len(notes),
        "upgrades_applied": 0,
        "honest": "no Grenztyp change without verified frontier evidence",
        "quelle": "learning_integrator.apply_delta_to_front",
    }
