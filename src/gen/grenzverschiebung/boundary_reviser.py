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

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .development_front import ExperimentleiterSchritt, Grenztyp, is_jetpack_traum

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
    und revised die Map (z.B. "portable Energie" von NEEDS_BREAKTHROUGH zu possible_but_unsafe_directly, neue Stufen in ladder).

    Evidenz-Regel (Review F6): Grenztypen werden NUR aus Items mit
    ``evidence_level == "verified"`` aufgewertet. Synthetische Items (der Default
    aus breakthrough_watch — fabrizierte Plan-Beispiele) erzeugen nur eine
    Kandidaten-Notiz (``old_typ == new_typ``) und lassen Map + fehlende
    Fähigkeiten unverändert.
    """
    traum = current_front.traum

    revisions: list[BoundaryRevision] = []
    revised_grenzen = dict(current_front.grenzen)
    revised_ladder = list(current_front.experimentleiter)
    revised_fehlend = list(current_front.fehlende_faehigkeiten)

    if is_jetpack_traum(traum):  # Wortgrenzen-Trigger (Review F5)
        # Incorporate new items from frontier_update (Review F6): NUR Items mit
        # evidence_level == "verified" dürfen einen Grenztyp aufwerten. Synthetische
        # Items (fabrizierte Plan-Beispiele aus breakthrough_watch) werden nur als
        # unverifizierte Kandidaten notiert — old_typ == new_typ, Map unverändert.
        def _apply(item, boundary: str, new_typ: Grenztyp, verified_reason: str) -> None:
            if boundary not in revised_grenzen:
                return
            old = revised_grenzen[boundary]
            if getattr(item, "evidence_level", "synthetic") == "verified":
                revised_grenzen[boundary] = new_typ
                revisions.append(BoundaryRevision(
                    changed_boundary=boundary,
                    old_typ=str(old),
                    new_typ=str(new_typ),
                    reason=verified_reason,
                    quelle=item.quelle,
                ))
            else:
                revisions.append(BoundaryRevision(
                    changed_boundary=boundary,
                    old_typ=str(old),
                    new_typ=str(old),  # KEINE Aufwertung
                    reason=(
                        f"Synthetische Front-Evidenz, unverifiziert ('{item.titel}') — "
                        f"Grenztyp NICHT aufgewertet (Kandidat für {new_typ} erst nach echter Verifikation)."
                    ),
                    quelle=item.quelle,
                ))

        for item in frontier_update.items:
            if "Solid-State" in item.titel or "Energie" in item.titel:
                _apply(item, "portable Energie für 5+ min bemannten Hover >80kg",
                       Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY,
                       "Verified Solid-State Battery results make it less breakthrough-dependent.")
                if getattr(item, "evidence_level", "synthetic") == "verified":
                    revised_fehlend = [f for f in revised_fehlend if "Energie-Dichte" not in f]  # remove from fehlend if addressed
            if "Redundant" in item.titel or "Control" in item.titel:
                _apply(item, "validierte Manned Single-Failure Recovery <0.1s", Grenztyp.KNOWN_POSSIBLE,
                       "Verified dissimilar redundant architecture provides path.")
            if "Parachute" in item.titel or "Recovery" in item.titel:
                _apply(item, "bemannter freier Flug über Menschenmenge ohne Failure-Risiko",
                       Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY,
                       "Verified ultra-light parachute system makes recovery path feasible.")

        upgrades = [r for r in revisions if r.new_typ != r.old_typ]

        # Add new step to ladder based on the frontier update (honest wording)
        revised_ladder.append(
            ExperimentleiterSchritt(
                beschreibung=(
                    "Frontier-Kandidaten prüfen (Solid-State + redundant FC + light recovery): "
                    + ("verifizierte Items in revised Grenze integrieren und nächste Stufe definieren."
                       if upgrades else
                       "alle Items synthetisch/unverifiziert — Grenztypen unverändert; erst echte Verifikation beschaffen, dann aufwerten.")
                ),
                quelle="breakthrough_watch Items + boundary_reviser",
            )
        )

        if upgrades:
            revised_heutige = current_front.heutige_grenze + " | REVISED: verifizierte Frontier-Items werten einzelne Grenztypen auf. See revisions."
        else:
            revised_heutige = current_front.heutige_grenze + " | REVIEWED: nur synthetische Front-Evidenz (unverifiziert) — Grenztypen unverändert, Kandidaten notiert."
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

    upgrades = [r for r in revisions if r.new_typ != r.old_typ]
    zusammenfassung = (
        f"{len(revisions)} boundary revision(s); {len(upgrades)} real upgrade(s) "
        f"(verified evidence only). Traum: {traum[:60]}…"
    )

    return RevisedFrontMap(
        source_traum=traum,
        revised_map=revised_map,
        revisions=revisions,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="boundary_reviser X3 + frontier_update + GENESIS_PLATFORM_PLAN.md §3.3",
    )


def revise_with_learning(
    current_front: "DevelopmentFrontMap",
    frontier_update: "FrontierUpdate",
    *,
    run_id: str | None = None,
) -> dict:
    """X3: full revise path + optional learning loop attachment.

    Returns revised map plus a learning-cycle delta when safety ladder is available.
    """
    from .safety_ladder import build_safety_ladder
    from .learning_integrator import apply_learning_cycle, apply_delta_to_front

    revised = revise_boundary(current_front, frontier_update, run_id=run_id)
    safety = build_safety_ladder(revised, run_id=run_id)
    delta = apply_learning_cycle(safety=safety, revised=revised, run_id=run_id)
    feed = apply_delta_to_front(revised, delta, run_id=run_id)
    return {
        "schema": "genesis-revise-with-learning-v1",
        "revised": revised,
        "delta": delta,
        "learning_feed": feed,
        "n_upgrades": sum(1 for r in revised.revisions if r.new_typ != r.old_typ),
        "quelle": "boundary_reviser.revise_with_learning",
    }
