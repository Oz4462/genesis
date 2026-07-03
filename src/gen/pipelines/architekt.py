"""architekt — erster Stein der Fach-Pipelines (Architekt-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §3.4 / 4.1:
- Ziel: Aus dem Funken eine belastbare Systemstruktur machen.
- Outputs: Systemkonzept, Variantenmatrix, Anforderungsliste, Baugruppenstruktur, Schnittstellenkarte, offene Entscheidungen.
- Gate: keine versteckten Anforderungen, jede Baugruppe hat Zweck + Schnittstelle, etc.

Erster Stein: deterministischer Mapper von Idee (oder später Grenz-Output) zu SystemConcept.
Jetpack-Beispiel nutzt die Struktur aus prior Safety-Ladder / Grenz-Modulen (Experimentleiter-Stufen, Recovery, Tether etc.).

Später: Integration mit CAD-Builder (erzeugt PrototypeSpec aus den Baugruppen) + Manufacturing-Gates.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SystemRequirement:
    """Eine einzelne Anforderung mit Provenance."""
    text: str
    quelle: str | None = None


@dataclass(frozen=True)
class AssemblyConcept:
    """Eine Hauptbaugruppe mit Zweck und Schnittstellen-Hinweis."""
    name: str
    purpose: str
    interfaces: list[str]
    quelle: str | None = None


@dataclass(frozen=True)
class SystemConcept:
    """Der Output der Architekt-Pipeline (erster Stein)."""
    source_idea: str
    requirements: list[SystemRequirement]
    main_assemblies: list[AssemblyConcept]
    variants: list[str]
    open_decisions: list[str]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_system_concept(
    idea: str,
    *,
    run_id: str | None = None,
) -> SystemConcept:
    """
    Erster Stein der Architekt-Pipeline.
    Für das Jetpack-Beispiel erzeugt es eine belastbare Systemstruktur,
    die direkt aus den prior Grenz- und Safety-Outputs abgeleitet ist (keine Erfindung).
    """
    if "jetpack" in idea.lower() or ("mensch" in idea.lower() and "fliegen" in idea.lower()):
        requirements = [
            SystemRequirement("Sichere Demonstration über Menschenmenge (kein unkontrollierter Absturz)", "PLAN 3.2 + safety_ladder S3/S5"),
            SystemRequirement("Erste Tests tethered / unbemannt / gesichert (kleinster sicherer Test)", "safety_ladder S0-S2 + prior Grenz"),
            SystemRequirement("Recovery <3s in allen Failure-Modi (aus breakthrough + revised)", "learning_integrator + boundary_reviser"),
            SystemRequirement("Energie-Dichte für 5+ min free flight unter Pilot-Last", "breakthrough Solid-State + revised"),
        ]
        assemblies = [
            AssemblyConcept("Frame / Structural", "Trägt Pilot + Propulsion + Recovery", ["Tether attachment", "Recovery pack mount", "Propulsion interface"], "safety S4 + prototype_cad_builder tether plate"),
            AssemblyConcept("Propulsion (Ducted Fan / eVTOL-like)", "Schub für kontrollierten Flug", ["Power", "Control signals", "Mounting to frame"], "prior technology_roadmap P1/P2"),
            AssemblyConcept("Recovery System", "Sichere Landung bei Ausfall (<3s)", ["Deployment trigger", "Attachment points", "Container interface"], "learning_integrator Recovery rule + safety S2/S4"),
            AssemblyConcept("Tether / Harness", "Sicherung für frühe Stufen (S1-S3)", ["Ground anchor", "Pilot attachment", "Load measurement"], "safety_ladder S1/S3 + CAD anchor plate"),
            AssemblyConcept("Control & Sensing", "Stabilität, Telemetrie, Abort", ["Flight controller", "Sensors", "Ground link"], "breakthrough dissimilar redundant FC"),
        ]
        variants = [
            "S0 — Full simulation + model (no hardware risk)",
            "S1 — Bench + tethered unmanned on existing test stands",
            "S2 — Free unmanned low altitude (unpopulated, revised recovery)",
            "S3 — Secured manned tethered (small crowd sim)",
            "S4 — Free manned low (unpopulated, ground team)",
            "S5 — Manned free with regulatory approval (public demo ready)",
        ]
        open_decisions = [
            "Exact propulsion architecture (number of ducted fans vs. other) — to be refined by Ingenieur-Pipeline",
            "Final tether material and load cell integration",
            "Regulatory path and public demo location",
        ]
        zusammenfassung = (
            "SystemConcept für Jetpack: 4 Kern-Anforderungen (Sicherheit, gestufte Tests, Recovery, Energie), "
            "5 Hauptbaugruppen mit Zweck + Schnittstellen, 6 Varianten direkt aus Safety-Ladder, "
            "offene Entscheidungen markiert. Naht zu CAD-Builder und Manufacturing-Gates vorbereitet."
        )
    else:
        requirements = [SystemRequirement("Grundlegende Stabilität und sichere Handhabung", "generic fallback")]
        assemblies = [AssemblyConcept("Main Structure", "Trägt die Funktion", ["Mounting points"], "generic")]
        variants = ["Minimal viable prototype (bench first)"]
        open_decisions = ["No detailed analysis yet — needs full Grenz + Fach-Pipeline run"]
        zusammenfassung = "Minimal SystemConcept für noch nicht detailliert analysierte Idee."

    return SystemConcept(
        source_idea=idea,
        requirements=requirements,
        main_assemblies=assemblies,
        variants=variants,
        open_decisions=open_decisions,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="architekt (first stone) + GENESIS_PLATFORM_PLAN.md §4.1 + prior Grenzverschiebung (safety_ladder, learning_integrator, boundary_reviser) + prototype_cad_builder",
    )
