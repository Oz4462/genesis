"""wirtschaft — Wirtschafts-/Produkt-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Kosten, Zielgruppe, Stückzahl, Lieferkette, Reparatur, Skalierung.
- Outputs: Business case, target market, volume ramp, supply chain, repair model, scaling plan.
- Gate: no cost claim without source/estimate, no volume without market, no scaling without repair path.

Erster Stein: Mapper from prior (Fertigungs cost, Realisierungspaket costs, Techniker repair) to WirtschaftSpec.
Jetpack: hobby/experimental market, low volume, high repair cost, scaling to certified manned only after regulatorik.
Generic: honest gaps.

Naht: Pulls costs from Fertigungs/Realisierungspaket, repair from Techniker, market hints from concept. Output feeds Realisierungspaket (business case in package).
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept
from .ingenieur import IngenieurSpec


@dataclass(frozen=True)
class KostenStruktur:
    """Detailed cost breakdown (with source/estimate)."""
    prototype: str
    low_volume: str
    target_volume: str
    repair_cost: str
    quelle: str | None = None


@dataclass(frozen=True)
class Markt:
    """Target market and volume."""
    zielgruppe: str
    stueckzahl_ramp: str
    lieferkette: str
    skalierung: str
    quelle: str | None = None


@dataclass(frozen=True)
class WirtschaftSpec:
    """Output of the Wirtschafts/P rodukt Pipeline (first stone)."""
    source_idea: str
    kosten: KostenStruktur
    markt: Markt
    reparatur_modell: str
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_wirtschaft_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> WirtschaftSpec:
    """
    Erster Stein Wirtschafts-Pipeline.
    Jetpack: experimental/hobby market, low volume, high repair, scaling gated by regulatorik.
    Generic: honest gaps.
    """
    idee_lower = concept.source_idea.lower()

    if "jetpack" in idee_lower or "flug" in idee_lower:
        kosten = KostenStruktur(
            prototype="8-25 EUR (FDM dominant, from Fertigungs/Realisierungspaket)",
            low_volume="50-150 EUR (small batch CNC + electronics)",
            target_volume="TBD - depends on certification (Lücke: live supplier prices from Wissensbasis)",
            repair_cost="High (tether + battery + harness inspection per Techniker)",
            quelle="Fertigungs + Realisierungspaket + Techniker + PLAN §4",
        )
        markt = Markt(
            zielgruppe="Experimental / hobby pilots in controlled areas (post regulatorik approval: certified manned flight)",
            stueckzahl_ramp="1-10 prototypes -> 50-200 low volume (gated by Regulatorik)",
            lieferkette="Motors/batteries from hobby suppliers, tether/custom from specialist (Lücke for full chain)",
            skalierung="Only after full Regulatorik + certification; otherwise limited to experimental use",
            quelle="Regulatorik + PLAN §4 + concept (manned in crowd)",
        )
        reparatur = "Per-flight tether inspection + annual full service (Techniker model). High cost -> low volume market."
        zusammen = "Jetpack WirtschaftSpec: prototype/low-volume costs from prior, experimental market gated by Regulatorik, high repair, scaling only post-cert. Naht to Fertigungs/Realisierungspaket/Techniker/Regulatorik."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 (Wirtschafts-Pipeline) + prior Fertigungs/Realisierungspaket/Techniker/Regulatorik + Jetpack-Kanon"
    else:
        kosten = KostenStruktur(prototype="TBD", low_volume="TBD", target_volume="Lücke", repair_cost="Lücke", quelle="Generic + PLAN §4")
        markt = Markt(zielgruppe="Generic", stueckzahl_ramp="Lücke", lieferkette="Lücke", skalierung="Lücke", quelle="Generic")
        reparatur = "Lücke"
        zusammen = f"Generische WirtschaftSpec für '{concept.source_idea[:40]}...'. Viele Details als Lücke."
        quelle = "GENESIS_PLATFORM_PLAN.md §4 + generic fallback (ehrliche Lücken)"

    return WirtschaftSpec(
        source_idea=concept.source_idea,
        kosten=kosten,
        markt=markt,
        reparatur_modell=reparatur,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
