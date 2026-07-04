"""architekt — erster Stein der Fach-Pipelines (Architekt-Pipeline).

Gemäß GENESIS_PLATFORM_PLAN.md §3.4 / 4.1:
- Ziel: Aus dem Funken eine belastbare Systemstruktur machen.
- Outputs: Systemkonzept, Variantenmatrix, Anforderungsliste, Baugruppenstruktur, Schnittstellenkarte, offene Entscheidungen.
- Gate: keine versteckten Anforderungen, jede Baugruppe hat Zweck + Schnittstelle, etc.

Erster Stein: deterministischer Mapper von Idee zu SystemConcept (Kanon-Vorlage).

HONESTY (Schritt-9-Review #11, S-1-Muster): die Funktion konsumiert NUR den Ideen-String —
kein Grenz-Output (safety_ladder/learning_integrator/boundary_reviser) und kein
CAD-Artefakt speist diesen Mapper. Die Jetpack-Struktur (inkl. S0–S5-Stufen) ist eine
PLAN-§4.1-Kanon-Vorlage; die deklarierte Lücke ist die echte Prior-Auswertung.

Später: Integration mit CAD-Builder (erzeugt PrototypeSpec aus den Baugruppen) + Manufacturing-Gates.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._triggers import has_fliegen_word

#: Honest provenance label (S-1): a canon template, not a consumed prior.
_CANON_QUELLE = "PLAN §4.1 Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)"


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
    Erster Stein der Architekt-Pipeline: deterministische PLAN-§4.1-Kanon-Vorlage je Idee.

    Konsumiert NUR den Ideen-String (#11, S-1-Muster) — kein quelle-Feld behauptet eine
    Ableitung aus Grenz-/Safety-/CAD-Prioren; die Stufen S0–S5 sind Kanon-Annahmen.
    """
    if "jetpack" in idea.lower() or ("mensch" in idea.lower() and has_fliegen_word(idea)):
        requirements = [
            SystemRequirement("Sichere Demonstration über Menschenmenge (kein unkontrollierter Absturz)", _CANON_QUELLE),
            SystemRequirement("Erste Tests tethered / unbemannt / gesichert (kleinster sicherer Test)", _CANON_QUELLE),
            SystemRequirement("Recovery <3s in allen Failure-Modi (Kanon-Annahme)", _CANON_QUELLE),
            SystemRequirement("Energie-Dichte für 5+ min free flight unter Pilot-Last (Kanon-Annahme)", _CANON_QUELLE),
        ]
        assemblies = [
            AssemblyConcept("Frame / Structural", "Trägt Pilot + Propulsion + Recovery", ["Tether attachment", "Recovery pack mount", "Propulsion interface"], _CANON_QUELLE),
            AssemblyConcept("Propulsion (Ducted Fan / eVTOL-like)", "Schub für kontrollierten Flug", ["Power", "Control signals", "Mounting to frame"], _CANON_QUELLE),
            AssemblyConcept("Recovery System", "Sichere Landung bei Ausfall (<3s)", ["Deployment trigger", "Attachment points", "Container interface"], _CANON_QUELLE),
            AssemblyConcept("Tether / Harness", "Sicherung für frühe Stufen (S1-S3)", ["Ground anchor", "Pilot attachment", "Load measurement"], _CANON_QUELLE),
            AssemblyConcept("Control & Sensing", "Stabilität, Telemetrie, Abort", ["Flight controller", "Sensors", "Ground link"], _CANON_QUELLE),
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
            "5 Hauptbaugruppen mit Zweck + Schnittstellen, 6 Stufen-Varianten (S0–S5, Kanon-Annahme), "
            "offene Entscheidungen markiert. Kein Prior konsumiert — die geplante Naht zu "
            "CAD-Builder und Manufacturing-Gates ist noch nicht verdrahtet."
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
        quelle="architekt (first stone) + GENESIS_PLATFORM_PLAN.md §4.1 — Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)",
    )
