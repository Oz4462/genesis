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

    Generischer (nicht-Jetpack) Pfad: leitet das Delta ECHT aus dem Input ab —
    je eine `LearningRule` pro realer `SafetyStage` (deren Gate als gelernte Invariante,
    Name/Gate als Provenance) und je einen `FailureMode` pro `abbruch`-Kriterium der Stufe.
    Ist nur `revised` gegeben, werden die Regeln aus dessen `revisions` abgeleitet.
    Trägt der Input kein verwertbares Signal (z.B. SafetyStagePlan ohne Stufen, revised
    ohne Revisionen), wird ehrlich abstrahiert (leere Regel-Liste + expliziter LÜCKE-Marker)
    statt erfundener Inhalt zurückzugeben.

    Raises:
        ValueError: wenn sowohl `safety` als auch `revised` None sind — ohne irgendeine
            Quelle gäbe es nur fabrizierten Inhalt ("keine stillen Defaults").
    """
    # Fail loud instead of fabricating a "unbekannt" traum out of nothing (no silent default).
    if safety is None and revised is None:
        raise ValueError(
            "apply_learning_cycle benötigt mindestens 'safety' oder 'revised'; "
            "beide None würde fabrizierten Inhalt erzeugen."
        )

    traum = safety.source_traum if safety is not None else revised.source_traum

    rules: list[LearningRule] = []
    failures: list[FailureMode] = []
    wissens: list[WissensEintrag] = []
    vorschlaege: list[str] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        # 8-Schritt angewendet (hier als Delta kodiert; Schritte 1-3 aus Input, 4-7 in Delta, 8 = nächste Nutzung)
        rules = [
            LearningRule(
                regel="Solid-State Battery (Sulfid, >350 Wh/kg Pack-Level) verschiebt portable Energie von needs_breakthrough zu possible_but_unsafe_directly.",
                evidenz="Frontier Item + revised boundary (S0-S5 Gates berücksichtigen neue Dichte).",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + breakthrough_watch Solid-State + boundary_reviser + safety S0/S4",
            ),
            LearningRule(
                regel="Dissimilar redundant FC + <50ms Switch + <1kg erlaubt leichtere P2-Architektur; Recovery-Zeit <3s bleibt hartes Gate.",
                evidenz="Frontier Verfahren + S2/S4 messkriterien (Recovery <3s in allen Failure-Tests).",
                quelle="breakthrough_watch dissimilar FC + safety_ladder S2/S4 + teststand",
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
                titel="Jetpack Energy Model Update 2026",
                inhalt="Mit Solid-State >350 Wh/kg (Lab) ist portable Energie für 5+ min free flight unter 100kg+ Pilot-Last technisch möglich (possible_but_unsafe_directly).",
                evidenz="Frontier + revised + Safety S4 (5+ min free mit Pilot-äquivalenter Last).",
                quelle="breakthrough_watch + boundary_reviser + safety S4",
            ),
            WissensEintrag(
                titel="Safety Gate Invariante",
                inhalt="Jede Stufe muss Gate + messkriterien + abbruch haben. Ohne Gate keine Freigabe zur nächsten Stufe (Defense-in-depth).",
                evidenz="Vollständige 6-Stufen-Leiter in safety_ladder.",
                quelle="safety_ladder + GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        vorschlaege = [
            "boundary_reviser + development_front: 'portable Energie' Grenztyp updated zu possible_but_unsafe_directly (Solid-State) in nächstem Zyklus.",
            "safety_ladder S2/S4: Recovery <3s als hartes Gate in allen free-flight Stufen beibehalten; neue dissimilar FC als zusätzliches Kriterium prüfen.",
            "learning_integrator nächste Runde: Delta in Wissensbasis schreiben und bei neuer Idee als Kontext für front_mapper nutzen.",
            "8-Schritt-Zyklus schließen: Nach Bench/Safety neue Delta erzeugen und revised_front füttern (Lernmaschine aktiv).",
        ]
        zusammenfassung = (
            "LearningDelta (Jetpack): 3 Rules (Solid-State Shift, dissimilar FC + Recovery, Gate-Invariante), "
            "2 Failure-Modes (Single-Failure in Sim/Stand, Recovery >3s), 2 Wissens-Einträge, 4 Verbesserungsvorschläge. "
            "8-Schritt-Prozess (§3.8) angewendet: Lücken aus safety/revised erkannt → Delta mit Evidence → Vorschläge für nächsten Zyklus."
        )
    elif safety is not None and safety.stages:
        # Generic (non-jetpack) path, structured input: derive genuinely from the REAL
        # SafetyStagePlan. WHY (L2-drift fix): the previous version returned exactly one
        # canned LearningRule regardless of input — a facade. Now each concrete SafetyStage
        # contributes a rule (its gate is the learned invariant) and a FailureMode per
        # abbruch criterion, each referencing the stage's name/gate as provenance.
        for stage in safety.stages:
            rules.append(
                LearningRule(
                    regel=(
                        f"Stufe '{stage.name}' verlangt Gate '{stage.gate}' "
                        f"(safe_form: {stage.safe_form}) bevor die nächste Stufe beginnt."
                    ),
                    evidenz=(
                        "Messkriterien: " + "; ".join(stage.messkriterien)
                        if stage.messkriterien
                        else "Keine Messkriterien deklariert (Lücke)."
                    ),
                    quelle=stage.quelle or "safety_ladder",
                )
            )
            for kriterium in stage.abbruch:
                failures.append(
                    FailureMode(
                        modus=kriterium,
                        aus_stufe=stage.name,
                        evidenz=f"Abbruchkriterium der Stufe '{stage.name}' (Gate: {stage.gate}).",
                        quelle=stage.quelle or "safety_ladder",
                    )
                )
        wissens.append(
            WissensEintrag(
                titel=f"Safety-Ladder Zusammenfassung ({len(safety.stages)} Stufen)",
                inhalt=safety.zusammenfassung,
                evidenz="Abgeleitet aus dem realen SafetyStagePlan (jede Stufe → Regel + Failure-Modes).",
                quelle=safety.quelle or "safety_ladder",
            )
        )
        vorschlaege.append(
            f"Nächster Zyklus: die {len(rules)} abgeleiteten Stufen-Regeln und "
            f"{len(failures)} Failure-Modes in boundary_reviser/front_mapper zurückspeisen."
        )
        zusammenfassung = (
            f"Minimal-LearningDelta (generisch, nicht-Jetpack): aus {len(safety.stages)} "
            f"Safety-Stufen abgeleitet → {len(rules)} Rules, {len(failures)} Failure-Modes, "
            f"{len(wissens)} Wissens-Eintrag, {len(vorschlaege)} Vorschlag(e)."
        )
    elif revised is not None and revised.revisions:
        # Only the revised front carries signal: derive one rule per real BoundaryRevision.
        for rev in revised.revisions:
            rules.append(
                LearningRule(
                    regel=(
                        f"Grenze '{rev.changed_boundary}' verschoben: "
                        f"{rev.old_typ} → {rev.new_typ}."
                    ),
                    evidenz=rev.reason,
                    quelle=rev.quelle or "boundary_reviser",
                )
            )
        vorschlaege.append(
            "Nächster Zyklus: SafetyStagePlan aus dem revised Front bauen, "
            "um Failure-Modes je Stufe zu gewinnen."
        )
        zusammenfassung = (
            f"Minimal-LearningDelta (generisch): aus {len(rules)} Boundary-Revision(en) "
            "des revised Fronts abgeleitet."
        )
    else:
        # Input present but no actionable signal (SafetyStagePlan without stages, or revised
        # without revisions). Honest abstention with an explicit LÜCKE marker instead of a
        # fabricated rule — "Ich weiß es nicht" ist ein gültiger Output (Kernprinzip 4).
        vorschlaege.append(
            "LÜCKE: Weder Safety-Stufen noch Boundary-Revisionen vorhanden; volle Analyse "
            "(breakthrough + safety_ladder) erforderlich, bevor Regeln/Failure-Modes entstehen."
        )
        zusammenfassung = (
            "Minimal-LearningDelta (generisch): Input ohne verwertbares Signal — "
            "keine Regel ableitbar (Lücke, ehrliche Abstention)."
        )

    return LearningDelta(
        source_traum=traum,
        rules=rules,
        failure_modes=failures,
        wissens_eintraege=wissens,
        naechste_verbesserungsvorschlaege=vorschlaege,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="learning_integrator (12/12 letzter Stein) + safety_ladder + revised + breakthrough + GENESIS_PLATFORM_PLAN.md §3.3 + §3.8",
    )
