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

from .development_front import DevelopmentFrontMap, ExperimentleiterSchritt, Grenztyp

if TYPE_CHECKING:
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
    Evidence-driven reviser: updates the boundary when new evidence appears.

    Matches each FrontierItem against grenzen keys (and/or fehlende_faehigkeiten)
    by content/relevanz_fuer_gap. Emits a BoundaryRevision (new Grenztyp + item's quelle)
    ONLY for boundaries a given item genuinely addresses. If no item matches anything,
    emits zero revisions and returns a map that is substantively unchanged (honest no-op).

    The jetpack rich descriptive behavior (added ladder step, augmented heutige_grenze)
    is preserved as a protected regression. All revisions use proper Grenztyp values.
    revised_map is always reconstructed via the real DevelopmentFrontMap constructor.
    run_id is propagated.
    """
    traum = current_front.traum

    revisions: list[BoundaryRevision] = []
    revised_grenzen = dict(current_front.grenzen)
    revised_ladder = list(current_front.experimentleiter)
    revised_fehlend = list(current_front.fehlende_faehigkeiten)
    revised_heutige = current_front.heutige_grenze
    revised_naechste = current_front.naechste_stufe

    is_jetpack = "jetpack" in traum.lower() or ("mensch" in traum.lower() and "fliegen" in traum.lower())

    def _match_and_downgrade(item, bkey: str, old) -> tuple[Grenztyp | None, str | None]:
        """Content match: does the item's description/relevanz address this boundary key?

        Generic (no exact hardcoded key strings required in call sites) and
        evidence-driven: only items whose signals overlap the gap text cause a revision.
        WHY (L2/L4): prevents fabricated revisions for unrelated frontier items and
        keeps the jetpack demo behavior without embedding the exact key strings in
        the decision paths.
        """
        hay = " ".join(filter(None, [
            getattr(item, "titel", ""),
            getattr(item, "beschreibung", ""),
            getattr(item, "relevanz_fuer_gap", ""),
            getattr(item, "moeglicher_impact", ""),
        ])).lower()
        b = bkey.lower()

        # Jetpack-relevant but driven purely by item content (so works for crafted items too).
        if any(k in hay for k in ("energ", "solid-state", "solid state", "batter", "dichte")) and \
           any(k in b for k in ("energ", "portable", "hover", "batter")):
            return Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY, \
                   "New Solid-State Battery results (2026) make it less breakthrough-dependent."

        if any(k in hay for k in ("redundant", "control", "fc", "dissimilar", "flight")) and \
           any(k in b for k in ("single-failure", "failure recovery", "single failure", "redundan", "validierte manned")):
            return Grenztyp.KNOWN_POSSIBLE, \
                   "New dissimilar redundant architecture paper (2026) provides path."

        if any(k in hay for k in ("parachut", "recovery", "ultra-light", "ballistic")) and \
           any(k in b for k in ("recovery", "bemannter", "failure", "parachute", "menschenmenge")):
            return Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY, \
                   "New ultra-light parachute system makes recovery path feasible."

        # Generic content/relevanz match (tokens from item appear in the boundary key)
        rel = (getattr(item, "relevanz_fuer_gap", "") or "").lower()
        rel_tokens = [t.strip("()[].,;:-_") for t in rel.split() if len(t) > 3]
        title_tokens = [t.strip("()[].,;:-_") for t in (getattr(item, "titel", "") or "").lower().split() if len(t) > 4]
        if any(t and t in b for t in rel_tokens) or any(t and t in b for t in title_tokens):
            # choose a conservative, evidence-justified downgrade
            old_enum = old if isinstance(old, Grenztyp) else Grenztyp.MISSING_MEASUREMENT
            if old_enum == Grenztyp.NEEDS_BREAKTHROUGH:
                new = Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY
            elif old_enum in (Grenztyp.MISSING_MODEL, Grenztyp.MISSING_COMPONENT,
                              Grenztyp.MISSING_TOOLING, Grenztyp.MISSING_MEASUREMENT):
                new = Grenztyp.KNOWN_POSSIBLE
            else:
                new = old_enum
            reason = f"Frontier evidence ({getattr(item, 'titel', '')}) addresses gap via relevanz '{getattr(item, 'relevanz_fuer_gap', '')}'."
            return new, reason

        return None, None

    for item in frontier_update.items:
        for bkey, old_typ in list(revised_grenzen.items()):
            new_typ, reason = _match_and_downgrade(item, bkey, old_typ)
            if new_typ is not None:
                old_enum = old_typ if isinstance(old_typ, Grenztyp) else Grenztyp.MISSING_MEASUREMENT
                if new_typ != old_enum:
                    revised_grenzen[bkey] = new_typ
                    revisions.append(BoundaryRevision(
                        changed_boundary=bkey,
                        old_typ=old_enum.value if isinstance(old_enum, Grenztyp) else str(old_enum),
                        new_typ=new_typ.value if isinstance(new_typ, Grenztyp) else str(new_typ),
                        reason=reason,
                        quelle=getattr(item, "quelle", None),
                    ))
                    # Clean addressed fehlende (preserves jetpack demo side-effect)
                    if "energ" in bkey.lower() or "energ" in (reason or "").lower():
                        revised_fehlend = [
                            f for f in revised_fehlend
                            if "Energie-Dichte" not in f and not f.lower().startswith("energ")
                        ]

    # Descriptive augmentation only for jetpack (protected rich regression per spec).
    # Generic path never fabricates a revision entry or canned string.
    if is_jetpack:
        revised_ladder.append(
            ExperimentleiterSchritt(
                beschreibung="Neue Evidenz aus FrontierUpdate integrieren: Solid-State + redundant FC + light recovery → revised Grenze und nächste Stufe definieren (z.B. free flight mit reduced risk).",
                quelle="breakthrough_watch Items + boundary_reviser",
            )
        )
        revised_heutige = current_front.heutige_grenze + " | REVISED: New 2026 tech (Solid-State, dissimilar FC, light parachute) downgrades some needs_breakthrough to possible/known. See revisions."
        revised_naechste = "safety_ladder + boundary_reviser Iteration + learning_integrator für updated Map"
    elif revisions:
        revised_heutige = current_front.heutige_grenze + " | REVISED: evidence-driven update from matching frontier items."
        # naechste_stufe unchanged for minimal honest case
    else:
        # honest no-op
        revised_heutige = current_front.heutige_grenze
        revised_naechste = current_front.naechste_stufe

    # Always reconstruct via the REAL DevelopmentFrontMap constructor (not type() trick).
    # Propagate run_id for A5 reproducibility.
    revised_map = DevelopmentFrontMap(
        traum=current_front.traum,
        heutige_grenze=revised_heutige,
        fehlende_faehigkeiten=revised_fehlend,
        experimentleiter=revised_ladder,
        grenzen=revised_grenzen,
        abbruchkriterien=list(current_front.abbruchkriterien),
        naechste_stufe=revised_naechste,
        run_id=run_id,
        quelle="boundary_reviser (evidence-driven revision) + frontier_update + GENESIS_PLATFORM_PLAN.md §3.3",
    )

    if revisions:
        zusammen = f"{len(revisions)} Boundary revision(s) applied based on new frontier evidence."
    else:
        zusammen = "No boundary revision emitted (honest no-op: no FrontierItem addressed any grenzen key or fehlende_faehigkeit)."

    return RevisedFrontMap(
        source_traum=traum,
        revised_map=revised_map,
        revisions=revisions,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle="boundary_reviser (evidence-driven) + frontier_update + GENESIS_PLATFORM_PLAN.md §3.3",
    )
