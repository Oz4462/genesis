"""boundary_reviser — zehnter Grenzverschiebungs-Modul (nächster aktiver Stein nach breakthrough_watch).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: aktualisiert die Grenze, wenn neue Evidenz oder Technik auftaucht.
- Output: neue `DevelopmentFrontMap`.

Dieses Modul nimmt die FrontierUpdate (von breakthrough_watch) + die aktuelle DevelopmentFrontMap und
produziert eine revised DevelopmentFrontMap mit aktualisierter heutige_grenze, grenzen-Typen (z.B. ein "needs_breakthrough" wird zu "known_possible" durch neue Tech), experimentleiter (neue Stufen), etc.

Erster Stein: Datamodel + deterministischer Reviser für das Jetpack-Beispiel
( integriert die neuen Items aus dem FrontierUpdate, z.B. neue Energie-Tech macht "portable Energie" less critical, updated grenzen und ladder).
Später: Volle Verknüpfung mit safety_ladder, learning_integrator, Wissensbasis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .development_front import ExperimentleiterSchritt

if TYPE_CHECKING:
    from .development_front import DevelopmentFrontMap
    from .breakthrough_watch import FrontierUpdate


@dataclass(frozen=True)
class BoundaryRevision:
    """Ein einzelnes Update zur Grenze (für interne Verwendung)."""

    changed_boundary: str
    old_typ: str
    new_typ: str
    reason: str
    quelle: str | None = None


@dataclass(frozen=True)
class RevisedFrontMap:
    """Die revised FrontMap (Output des Moduls)."""

    source_traum: str
    revised_map: "DevelopmentFrontMap"
    revisions: list[BoundaryRevision]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def revise_boundary(
    current_front: "DevelopmentFrontMap",
    frontier_update: "FrontierUpdate",
    *,
    run_id: str | None = None,
) -> RevisedFrontMap:
    """
    Erste Version des boundary_reviser.

    Für das Jetpack-Beispiel (PLAN) nimmt sie die aktuellen Grenzen und die neuen Frontier-Items
    und revised die Map (z.B. "portable Energie" von NEEDS_BREAKTHROUGH zu possible_but_unsafe_directly dank Solid-State, neue Stufen in ladder).
    """
    traum = current_front.traum

    revisions: list[BoundaryRevision] = []
    revised_grenzen = dict(current_front.grenzen)
    revised_ladder = list(current_front.experimentleiter)
    revised_fehlend = list(current_front.fehlende_faehigkeiten)

    if "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower()):
        # Incorporate new items from frontier_update
        for item in frontier_update.items:
            if "Solid-State" in item.titel or "Energie" in item.titel:
                if "portable Energie für 5+ min bemannten Hover >80kg" in revised_grenzen:
                    old = revised_grenzen["portable Energie für 5+ min bemannten Hover >80kg"]
                    revised_grenzen["portable Energie für 5+ min bemannten Hover >80kg"] = "possible_but_unsafe_directly"  # downgraded thanks to new tech
                    revisions.append(BoundaryRevision(
                        changed_boundary="portable Energie für 5+ min bemannten Hover >80kg",
                        old_typ=str(old),
                        new_typ="possible_but_unsafe_directly",
                        reason="New Solid-State Battery results (2026) make it less breakthrough-dependent.",
                        quelle=item.quelle,
                    ))
                    revised_fehlend = [f for f in revised_fehlend if "Energie-Dichte" not in f]  # remove from fehlend if addressed
            if "Redundant" in item.titel or "Control" in item.titel:
                if "validierte Manned Single-Failure Recovery <0.1s" in revised_grenzen:
                    old = revised_grenzen["validierte Manned Single-Failure Recovery <0.1s"]
                    revised_grenzen["validierte Manned Single-Failure Recovery <0.1s"] = "known_possible"  # now known thanks to paper
                    revisions.append(BoundaryRevision(
                        changed_boundary="validierte Manned Single-Failure Recovery <0.1s",
                        old_typ=str(old),
                        new_typ="known_possible",
                        reason="New dissimilar redundant architecture paper (2026) provides path.",
                        quelle=item.quelle,
                    ))
            if "Parachute" in item.titel or "Recovery" in item.titel:
                if "bemannter freier Flug über Menschenmenge ohne Failure-Risiko" in revised_grenzen:
                    old = revised_grenzen["bemannter freier Flug über Menschenmenge ohne Failure-Risiko"]
                    revised_grenzen["bemannter freier Flug über Menschenmenge ohne Failure-Risiko"] = "possible_but_unsafe_directly"
                    revisions.append(BoundaryRevision(
                        changed_boundary="bemannter freier Flug über Menschenmenge ohne Failure-Risiko",
                        old_typ=str(old),
                        new_typ="possible_but_unsafe_directly",
                        reason="New ultra-light parachute system makes recovery path feasible.",
                        quelle=item.quelle,
                    ))

        # Add new step to ladder based on new evidence
        revised_ladder.append(
            ExperimentleiterSchritt(
                beschreibung="Neue Evidenz aus FrontierUpdate integrieren: Solid-State + redundant FC + light recovery → revised Grenze und nächste Stufe definieren (z.B. free flight mit reduced risk).",
                quelle="breakthrough_watch Items + boundary_reviser",
            )
        )

        revised_heutige = current_front.heutige_grenze + " | REVISED: New 2026 tech (Solid-State, dissimilar FC, light parachute) downgrades some needs_breakthrough to possible/known. See revisions."
        revised_naechste = "safety_ladder + boundary_reviser Iteration + learning_integrator für updated Map"
    else:
        revised_heutige = current_front.heutige_grenze + " | REVISED: New frontier items incorporated (generic)."
        revised_grenzen = current_front.grenzen
        revised_ladder = current_front.experimentleiter
        revised_fehlend = current_front.fehlende_faehigkeiten
        revised_naechste = current_front.naechste_stufe
        revisions.append(BoundaryRevision(
            changed_boundary="generische Machbarkeit der Idee",
            old_typ="missing_measurement",
            new_typ="to be re-evaluated",
            reason="Generic frontier scan.",
            quelle="breakthrough_watch generic item",
        ))

    # Reconstruct revised map (copy and update)
    revised_map = type(current_front)(
        traum=current_front.traum,
        heutige_grenze=revised_heutige,
        fehlende_faehigkeiten=revised_fehlend,
        experimentleiter=revised_ladder,
        grenzen=revised_grenzen,
        abbruchkriterien=current_front.abbruchkriterien,
        naechste_stufe=revised_naechste,
        run_id=run_id,
        quelle="boundary_reviser (erster Stein) + frontier_update + GENESIS_PLATFORM_PLAN.md §3.3",
    )

    return RevisedFrontMap(
        source_traum=traum,
        revised_map=revised_map,
        revisions=revisions,
        zusammenfassung=f"{len(revisions)} Boundary revisions applied based on new frontier evidence. Grenze updated for {traum[:60]}...",
        run_id=run_id,
        quelle="boundary_reviser (erster Stein) + frontier_update + GENESIS_PLATFORM_PLAN.md §3.3",
    )
