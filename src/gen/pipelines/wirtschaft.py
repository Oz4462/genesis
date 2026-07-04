"""wirtschaft — Wirtschafts-/Produkt-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Kosten, Zielgruppe, Stückzahl, Lieferkette, Reparatur, Skalierung.
- Outputs: Business case, target market, volume ramp, supply chain, repair model, scaling plan.
- Gate: no cost claim without source/estimate, no volume without market, no scaling without repair path.

Erster Stein: deterministischer Mapper von SystemConcept zu WirtschaftSpec (Kanon-Vorlage).
Jetpack: hobby/experimental market, low volume, high repair cost, scaling to certified manned only after regulatorik.
Generic: honest gaps.

HONESTY (Schritt-9-Review #9, S-1-Muster): der ``ingenieur``-Parameter wird akzeptiert
(API-Stabilität), aber derzeit NICHT konsumiert — keine Kosten stammen aus Fertigungs/
Realisierungspaket/cost_model, kein Reparaturmodell aus Techniker. Jeder Output ist eine
PLAN-§4-Kanon-Vorlage; die deklarierte Lücke ist die echte Prior-Auswertung (insbesondere
reale cost_model-Bänder statt der Kanon-Kostenannahmen). Geplante Naht (NOCH NICHT
verdrahtet): Kosten aus Fertigungs/Realisierungspaket, Reparatur aus Techniker, Output in
Realisierungspaket (business case).
"""

from __future__ import annotations

from dataclasses import dataclass

from ._triggers import is_flight_idea
from .architekt import SystemConcept
from .ingenieur import IngenieurSpec

#: Honest provenance label (S-1): a canon template, not a consumed prior.
_CANON_QUELLE = "PLAN §4 Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)"


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
    Erster Stein Wirtschafts-Pipeline: deterministische PLAN-§4-Kanon-Vorlage je Konzept.
    Jetpack: experimental/hobby market, low volume, high repair, scaling gated by regulatorik.
    Generic: honest gaps.

    ``ingenieur`` ist für die geplante Prior-Naht reserviert und wird derzeit NICHT
    konsumiert (#9, S-1-Muster) — die Kostenbänder sind Kanon-Annahmen, keine
    cost_model-/Fertigungs-Ableitungen, und sagen das explizit.
    """
    if is_flight_idea(concept.source_idea):
        kosten = KostenStruktur(
            prototype="8-25 EUR (FDM dominant — Kanon-Annahme, keine cost_model-/Fertigungs-Ableitung)",
            low_volume="50-150 EUR (small batch CNC + electronics — Kanon-Annahme)",
            target_volume="TBD - depends on certification (Lücke: live supplier prices from Wissensbasis)",
            repair_cost="High (tether + battery + harness inspection — Kanon-Annahme)",
            quelle=_CANON_QUELLE,
        )
        markt = Markt(
            zielgruppe="Experimental / hobby pilots in controlled areas (post regulatorik approval: certified manned flight)",
            stueckzahl_ramp="1-10 prototypes -> 50-200 low volume (gated by Regulatorik)",
            lieferkette="Motors/batteries from hobby suppliers, tether/custom from specialist (Lücke for full chain)",
            skalierung="Only after full Regulatorik + certification; otherwise limited to experimental use",
            quelle=_CANON_QUELLE,
        )
        reparatur = "Per-flight tether inspection + annual full service (Kanon-Annahme). High cost -> low volume market."
        zusammen = (
            "Jetpack WirtschaftSpec: Prototyp-/Kleinserien-Kosten als Kanon-Annahme, experimenteller "
            "Markt gated by Regulatorik, hohe Reparaturkosten, Skalierung nur post-cert. "
            "Kein Prior (Fertigungs/Realisierungspaket/Techniker) konsumiert — die geplante Naht "
            "ist noch nicht verdrahtet (Lücke: echte cost_model-Bänder)."
        )
        quelle = "GENESIS_PLATFORM_PLAN.md §4 (Wirtschafts-Pipeline) — Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)"
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
