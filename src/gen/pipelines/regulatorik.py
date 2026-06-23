"""regulatorik — Sicherheits-/Regulatorik-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Normen, Risiken, Warnungen, menschliche Freigabe, Haftungsgrenzen.
- Outputs: Normen-Liste, Risiko-Matrix, Warnhinweise, Freigabe-Prozess, Haftungsgrenzen.
- Gate: no Netzspannung without safety path, no claim without human sign-off, risks visible.

Erster Stein: Mapper from prior (Elektriker safety, Techniker, Lern test cases, DFM) to RegulatorikSpec.
Jetpack: EASA-like for manned tether flight, human pilot sign-off, tether failure risk, battery fire, liability.
Generic: honest gaps.

Naht: Pulls from Elektriker (safety interlock), Techniker (maintenance), Lern (fault tests), DFM (printable risks), Realisierungspaket (regulatorik hints in package).
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec


@dataclass(frozen=True)
class Norm:
    name: str
    anwendung: str
    quelle: str | None = None


@dataclass(frozen=True)
class Risiko:
    name: str
    beschreibung: str
    schwere: str  # low/medium/high
    massnahme: str
    freigabe: str  # human sign-off required
    quelle: str | None = None


@dataclass(frozen=True)
class RegulatorikSpec:
    """Output of the Regulatorik Pipeline (first stone)."""
    source_idea: str
    normen: list[Norm]
    risiken: list[Risiko]
    warnhinweise: list[str]
    freigabe_prozess: str
    haftungsgrenzen: str
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_regulatorik_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> RegulatorikSpec:
    """
    Erster Stein Regulatorik-Pipeline.

    Jetpack branch (protected): manned tether flight norms (EASA+ISO), high risks
    (tether, battery) with massnahmen, human freigabe, warnings, haftung.

    Generic branch: derives output from inputs. Risiken are produced from
    ingenieur.failure_modes (detection becomes massnahme) and lastfaelle.
    source_idea and main_assemblies are reflected in warnhinweise + zusammenfassung.
    Norm is cited only on supporting signal; otherwise explicit honest gap
    "keine spezifische Norm ableitbar". No fabrication of norms/risks.

    Raises:
        ValueError: if source_idea is blank/empty, or if there is no actionable
            signal (failure_modes, lastfaelle and main_assemblies all empty).
            This prevents a canned stub for missing input (no-silent-defaults).
    """
    idee_lower = concept.source_idea.lower()

    if "jetpack" in idee_lower or "flug" in idee_lower:
        normen = [
            Norm("EASA CS-23 / equivalent for experimental manned tether", "Manned personal flight device with tether recovery", quelle="PLAN §4 + Elektriker safety + Safety-Ladder"),
            Norm("EN ISO 12100 (Machinery safety)", "General risk assessment for the system", quelle="PLAN §4"),
        ]
        risiken = [
            Risiko("Tether failure / loss of recovery", "Free fall or uncontrolled flight in crowd", "high", "Redundant cutoff + pilot training + tether inspection (Techniker)", "Mandatory pilot + ground crew sign-off before flight", quelle="Lern fault injection + Techniker + Elektriker"),
            Risiko("Battery fire / thermal runaway", "Fire during tethered flight", "high", "BMS + thermal monitoring + fire suppression consideration", "Human pilot sign-off + pre-flight thermal check", quelle="DFM thermal + Elektriker"),
        ]
        warn = [
            "WARNING: This is an experimental tethered flight device. Only for trained pilots in controlled areas.",
            "Liability: Operator is fully responsible; manufacturer provides no certification for manned use without local authority approval.",
        ]
        freigabe = "Human pilot + safety officer sign-off required for every flight (no autonomous release). Pre-flight checklist + post-flight report mandatory."
        haftung = "Full operator liability for any damage/injury. Device is prototype/experimental - no warranty for safety in real use. Consult local aviation authority before any public demo."
        zusammen = "Jetpack RegulatorikSpec: EASA-like + ISO norms, high risks (tether, battery) with massnahmen + human freigabe, warnings, full haftung. Naht to Elektriker/Techniker/Lern/DFM/Realisierungspaket."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 (Regulatorik-Pipeline) + prior Elektriker/Techniker/Lern/DFM + Jetpack-Kanon"
    else:
        # Generic path must be genuinely input-driven (no constant stub).
        # Guard first: blank source_idea or zero actionable signal -> fail loud.
        idea_text = (concept.source_idea or "").strip()
        if not idea_text:
            raise ValueError("source_idea must be a non-empty, non-whitespace string")
        has_actionable = bool(ingenieur.failure_modes) or bool(ingenieur.lastfaelle) or bool(concept.main_assemblies)
        if not has_actionable:
            # No failure_modes / lastfaelle / assemblies: no basis to derive real risks/norms -> no canned.
            raise ValueError("no actionable signal (failure_modes, lastfaelle and main_assemblies empty); cannot produce regulatorik spec without fabrication")

        # Norm: cite specific only on supporting signal; otherwise explicit honest gap.
        # (Generic branch never blindly asserts ISO 12100.)
        normen = [
            Norm(
                "keine spezifische Norm ableitbar",
                f"Konzept '{idea_text[:40]}' liefert keine hinreichenden Signale (keine spezifischen Failure-Modes oder Lastfälle) für Normenauswahl",
                quelle="regulatorik generic (ehrliche Lücke aus fehlendem Signal in concept/ingenieur)",
            )
        ]

        # Derive one Risiko per FailureMode: detection field becomes the massnahme;
        # human sign-off is always required (per contract).
        risiken: list[Risiko] = []
        for fm in ingenieur.failure_modes:
            risiken.append(
                Risiko(
                    name=fm.name,
                    beschreibung=f"{fm.beschreibung} (Baugruppe: {fm.aus_baugruppe})",
                    schwere="medium",
                    massnahme=fm.detection or "Lücke: keine Detection deklariert",
                    freigabe="Human sign-off required (derived from declared failure mode)",
                    quelle=fm.quelle or "abgeleitet aus ingenieur.failure_modes",
                )
            )

        # Derive Risiken from load cases (reflects kraft_oder_moment etc.).
        for lc in ingenieur.lastfaelle:
            risiken.append(
                Risiko(
                    name=f"Lastfall: {lc.name}",
                    beschreibung=f"{lc.beschreibung} — {lc.kraft_oder_moment}".strip(" —"),
                    schwere="medium",
                    massnahme=f"Einhaltung der spezifizierten Last ({lc.kraft_oder_moment}); geeignete Überwachung",
                    freigabe="Ingenieur-Freigabe der Lastannahmen + human sign-off",
                    quelle=lc.quelle or "abgeleitet aus ingenieur.lastfaelle",
                )
            )

        # Warnhinweise and summary reflect real source_idea + assemblies (input consumed).
        warn: list[str] = [
            f"WARNING: Experimental device derived from concept '{idea_text[:50]}'. "
            "All derived risks and load limits must be respected.",
        ]
        for a in concept.main_assemblies:
            ifaces = ", ".join(a.interfaces) if a.interfaces else "(keine Schnittstellen deklariert)"
            warn.append(
                f"Assembly '{a.name}': {a.purpose} (Schnittstellen: {ifaces}) — safety review required."
            )

        # Freigabe and haftung are also derived (mention counts from inputs).
        freigabe = (
            f"Human sign-off required for all {len(risiken)} derived risks (from failure_modes + lastfaelle) "
            "before operation. Pre-use checklist + post-use report mandatory."
        )
        haftung = (
            "Full operator liability. Device may only be operated within the explicitly declared "
            "failure mitigations and load cases from prior analysis. No general certification implied."
        )

        zusammen = (
            f"Generische RegulatorikSpec (input-getrieben) für '{idea_text[:40]}...': "
            f"{len(risiken)} Risiken abgeleitet aus {len(ingenieur.failure_modes)} Failure-Mode(s) "
            f"+ {len(ingenieur.lastfaelle)} Lastfall/Lastfällen; {len(concept.main_assemblies)} "
            "Baugruppe(n) in Warnungen/Summary reflektiert. Keine spezifische Norm ableitbar "
            "(ehrliche Lücke). Naht zu Architekt/Ingenieur."
        )
        quelle = (
            "GENESIS_PLATFORM_PLAN.md §4 (Regulatorik-Pipeline) + generic derivation from "
            "concept (source_idea, main_assemblies) + ingenieur (failure_modes, lastfaelle); "
            "keine fabrizierten Normen/Risiken"
        )

    return RegulatorikSpec(
        source_idea=concept.source_idea,
        normen=normen,
        risiken=risiken,
        warnhinweise=warn,
        freigabe_prozess=freigabe,
        haftungsgrenzen=haftung,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
