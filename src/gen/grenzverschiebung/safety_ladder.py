"""safety_ladder — elfter Grenzverschiebungs-Modul (nächster aktiver Stein nach boundary_reviser).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: definiert sichere Zwischenformen: Modell, Simulation, Prüfstand, unbemannt, gesichert, bemannt.
- Output: `SafetyStagePlan`.

Dieses Modul nimmt die revised FrontMap (oder die kumulierten) und
produziert einen gestuften SafetyStagePlan mit zunehmendem Risiko, jede Stufe mit safe form (Modell, Sim, Stand, unmanned, secured, manned), Gate, Messkriterien, Abbruch.

Erster Stein: Datamodel + deterministischer Ladder für das Jetpack-Beispiel
( baut auf den Meilensteinen und revised Map auf, mit 6 Stufen).
Später: Volle Verknüpfung mit learning_integrator, Wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .boundary_reviser import RevisedFrontMap


@dataclass(frozen=True)
class SafetyStage:
    """Eine einzelne sichere Stufe (für die Leiter)."""

    name: str
    beschreibung: str
    safe_form: str                   # Modell, Simulation, Prüfstand, unbemannt, gesichert, bemannt
    gate: str
    messkriterien: list[str]
    abbruch: list[str]
    quelle: str | None = None


@dataclass(frozen=True)
class SafetyStagePlan:
    """Der vollständige SafetyStagePlan (Output des Moduls)."""

    source_traum: str
    stages: list[SafetyStage]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def build_safety_ladder(
    revised: "RevisedFrontMap",
    *,
    run_id: str | None = None,
) -> SafetyStagePlan:
    """
    Erste Version des safety_ladder.

    Für das Jetpack-Beispiel (PLAN) erzeugt sie die 6-stufige Leiter mit safe forms, Gates und Kriterien, die die revised Grenze schrittweise mit zunehmendem Risiko (aber immer sicher) erproben.
    """
    traum = revised.source_traum

    stages: list[SafetyStage] = []

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        stages = [
            SafetyStage(
                name="S0 — Modell + Simulation",
                beschreibung="Vollständige Simulation und mathematisches Modell der revised Map (inkl. neuer Tech aus Frontier). Kein physisches Risiko.",
                safe_form="Modell, Simulation",
                gate="Vollständige Coverage der revised grenzen + Simulation der Experimente",
                messkriterien=["Simulation matcht revised Map", "Alle Experimente simulierbar ohne Absturz"],
                abbruch=["Simulation zeigt ungelöste Single-Failure"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + revised_front + breakthrough Items",
            ),
            SafetyStage(
                name="S1 — Prüfstand (Bench + tethered unmanned)",
                beschreibung="Bench-Tests der Prototypen + tethered unmanned Demonstrator auf den existierenden Ständen (T0-T2).",
                safe_form="Prüfstand, unbemannt (getethert)",
                gate="Erfolgreiche Bench + tethered unmanned mit revised specs",
                messkriterien=["Alle T0-T2 Kriterien aus TestStandPlan erfüllt", "Revised Grenze in realer Messung bestätigt"],
                abbruch=["Abbruchkriterien aus BenchTestPlan"],
                quelle="teststand_architect + revised",
            ),
            SafetyStage(
                name="S2 — Unbemannt free (low altitude, no public)",
                beschreibung="Ungebundener unbemannter Test in sicherer Höhe, mit den revised Recovery-Systemen.",
                safe_form="unbemannt, free flight (low, unpopulated)",
                gate="Erfolgreiche free unmanned mit revised Recovery",
                messkriterien=["5+ min free mit revised Energy/Control", "Recovery <3s in allen Failure-Tests"],
                abbruch=["Jede Failure ohne sichere Recovery"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + safety_ladder + revised",
            ),
            SafetyStage(
                name="S3 — Gesichert bemannt (tethered, small public simuliert)",
                beschreibung="Bemannter tethered mit SafetyStage (Wasser, redundanter Abort, Distanz-Messung), simuliert public.",
                safe_form="bemannt, gesichert (tethered, small crowd sim)",
                gate="Erfolgreiche tethered bemannt mit allen SafetyStage Kriterien",
                messkriterien=["100% sichere Aborts", "Sicherheitsabstand immer >10m"],
                abbruch=["Publikums-Risiko oder Wetterbedingte Probleme"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + safety_ladder",
            ),
            SafetyStage(
                name="S4 — Bemannt free low (unpopulated, mit Ground-Team)",
                beschreibung="Freier bemannter Test in low altitude, unpopulated, mit Ground-Team und revised Systems.",
                safe_form="bemannt, free (low, unpopulated, Ground-Team)",
                gate="Erfolgreiche free bemannt low mit revised Specs",
                messkriterien=["5+ min free mit Pilot-äquivalenter Last", "Notfall-Abstieg <3s"],
                abbruch=["Jede Deviation von revised Map"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + revised + breakthrough",
            ),
            SafetyStage(
                name="S5 — Bemannt free (mit regulatorischer Freigabe, public demo vorbereitet)",
                beschreibung="Vorbereitung für public free bemannt mit voller regulatorischer Freigabe und revised Map.",
                safe_form="bemannt, free (mit regulatorischer Freigabe, public demo)",
                gate="Regulatorische Freigabe + alle previous Gates + revised Frontier bestätigt",
                messkriterien=["Alle previous Kriterien + regulatorische Bestätigung"],
                abbruch=["Regulatorische oder Perception Probleme"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 + boundary_reviser + safety_ladder",
            ),
        ]
        zusammenfassung = (
            "6-stufige SafetyStagePlan (S0 Modell/Sim → S5 bemannt public), jede Stufe mit safe form, Gate, Messkriterien und Abbruch. "
            "Die Leiter erprobt die revised Grenze schrittweise mit zunehmendem Risiko (aber immer sicher kontrolliert)."
        )
    else:
        stages = [
            SafetyStage(
                name="S0 — Modell + Simulation (generic)",
                beschreibung="Vollständige Simulation der generic revised Map.",
                safe_form="Modell, Simulation",
                gate="Vollständige Coverage",
                messkriterien=["Simulation matcht revised"],
                abbruch=["Ungelöste Gaps"],
                quelle="GENESIS_PLATFORM_PLAN.md §3.3",
            ),
        ]
        zusammenfassung = "Minimal-SafetyLadder für noch nicht detailliert analysierte Idee."

    return SafetyStagePlan(
        source_traum=traum,
        stages=stages,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="safety_ladder (erster Stein) + revised_front + GENESIS_PLATFORM_PLAN.md §3.3",
    )
