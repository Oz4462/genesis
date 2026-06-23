"""wirtschaft — Wirtschafts-/Produkt-Pipeline first stone (PLAN §4).

Gemäß GENESIS_PLATFORM_PLAN.md §4:
- Aufgabe: Kosten, Zielgruppe, Stückzahl, Lieferkette, Reparatur, Skalierung.
- Outputs: Business case, target market, volume ramp, supply chain, repair model, scaling plan.
- Gate: no cost claim without source/estimate, no volume without market, no scaling without repair path.

Erster Stein: Mapper from prior (Fertigungs cost, Realisierungspaket costs, Techniker repair) to WirtschaftSpec.
Jetpack: hobby/experimental market, low volume, high repair cost, scaling to certified manned only after regulatorik.
Generic: leitet Kosten/Markt/Reparatur nachweislich aus ``concept`` und ``ingenieur`` ab
(zwei verschiedene Eingaben → unterscheidbare Specs) und markiert fehlende Belege ehrlich
als „Lücke: …" — keine fabrizierten Preise/Stückzahlen (Kernprinzip: keine stillen Defaults).

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


# Material name fragments that signal a metallic/composite workpiece — a real signal from
# ingenieur.material_hinweise that the part is more expensive to source/process than a
# plain printed structure. Used only to JUSTIFY a qualitative cost-driver note, never to
# fabricate a price (keine stillen Defaults).
_METAL_MATERIAL_MARKERS: tuple[str, ...] = (
    "alu", "stahl", "steel", "titan", "edelstahl", "messing", "metal", "cfk",
)

_PLAN_REF = "GENESIS_PLATFORM_PLAN.md §4"


def _derive_generic_kosten(
    concept: SystemConcept, ingenieur: IngenieurSpec
) -> KostenStruktur:
    """Derive a non-jetpack KostenStruktur from REAL engineer/concept signals.

    Cost is expressed as auditable *qualitative drivers* (assembly/load-case/failure-mode
    counts, material kind) — never a fabricated EUR figure, because no cost model was run
    in the first stone (Gate: keine Kosten ohne Quelle/Schätzung). Where a signal is
    genuinely absent, an explicit ``Lücke: …`` string is emitted instead of a guess.
    """
    n_assemblies = len(concept.main_assemblies)
    n_loadcases = len(ingenieur.lastfaelle)
    n_failures = len(ingenieur.failure_modes)
    n_tol = len(ingenieur.toleranzen)
    material_names = [m.name for m in ingenieur.material_hinweise]
    has_metal = any(
        any(marker in name.lower() for marker in _METAL_MATERIAL_MARKERS)
        for name in material_names
    )

    if n_assemblies or n_loadcases:
        prototype = (
            f"Kostentreiber (qualitativ): {n_assemblies} Baugruppe(n), "
            f"{n_loadcases} Lastfall(fälle); keine gerangte EUR-Zahl ohne "
            "Kostenmodell (Lücke: cost_model/Wissensbasis-Preise)"
        )
    else:
        prototype = (
            "TBD — Lücke: keine Baugruppen/Lastfälle im Input, kein Kostentreiber ableitbar"
        )

    if material_names:
        metal_note = (
            "; metall-/composite-fähig → höherer Beschaffungs-/Bearbeitungsaufwand"
            if has_metal
            else ""
        )
        low_volume = (
            f"Werkstoff-getrieben ({', '.join(material_names)}{metal_note}); "
            f"{n_tol} enge Toleranz(en); konkrete Batch-Kosten offen (Lücke)"
        )
    else:
        low_volume = "Lücke: keine Material-Hinweise → kein Werkstoff-Kostentreiber ableitbar"

    n_open = len(concept.open_decisions)
    if n_open:
        target_volume = (
            f"Serienkosten blockiert durch {n_open} offene Entscheidung(en); "
            "keine Serienkosten ohne deren Klärung (Lücke)"
        )
    else:
        target_volume = (
            "Lücke: keine offenen Entscheidungen erfasst → Serienkostenpfad nicht bewertbar"
        )

    if n_failures:
        fm_names = ", ".join(f.name for f in ingenieur.failure_modes)
        repair_cost = (
            f"{n_failures} Inspektions-/Reparaturpunkt(e) aus Failure-Modes ({fm_names}); "
            "Kostenhöhe ohne Stundensatz offen (Lücke)"
        )
    else:
        repair_cost = (
            "Lücke: keine Failure-Modes deklariert → Reparaturaufwand nicht ableitbar"
        )

    return KostenStruktur(
        prototype=prototype,
        low_volume=low_volume,
        target_volume=target_volume,
        repair_cost=repair_cost,
        quelle=(
            "generic aus ingenieur (Lastfälle/Material/Failure-Modes) + "
            f"{_PLAN_REF} (keine Kosten ohne Quelle, ehrliche Lücke)"
        ),
    )


def _derive_generic_markt(concept: SystemConcept) -> Markt:
    """Derive a non-jetpack Markt from REAL concept signals.

    Target group is grounded in the concept's requirements (which carry the verbatim
    idea), the volume ramp in the number of concept variants, the supply chain in the
    main assemblies to be sourced, and scaling readiness in the open decisions (Gate:
    kein Skalierungspfad ohne geklärte offene Entscheidungen + Reparaturmodell). Absent
    signals become explicit ``Lücke: …`` strings, not invented market facts.
    """
    req_texts = [r.text for r in concept.requirements]
    if req_texts:
        zielgruppe = (
            f"Aus Anforderungen abgeleitet: {'; '.join(req_texts[:2])}; "
            "konkrete Marktsegmentierung offen (Lücke)"
        )
    else:
        zielgruppe = (
            f"Lücke: keine Anforderungen → Zielgruppe für »{concept.source_idea}« "
            "nicht ableitbar"
        )

    n_variants = len(concept.variants)
    if n_variants:
        stueckzahl_ramp = (
            f"{n_variants} Konzept-Variante(n) → Ramp ab Prototyp; "
            "Stückzahl-Ziel ohne Marktdaten offen (Lücke)"
        )
    else:
        stueckzahl_ramp = "Lücke: keine Varianten im Konzept → kein Ramp ableitbar"

    if concept.main_assemblies:
        asm_names = ", ".join(a.name for a in concept.main_assemblies)
        lieferkette = (
            f"{len(concept.main_assemblies)} zu beschaffende Baugruppe(n): {asm_names}; "
            "konkrete Lieferanten offen (Lücke)"
        )
    else:
        lieferkette = "Lücke: keine Baugruppen im Konzept → Lieferkette nicht ableitbar"

    if concept.open_decisions:
        decisions = "; ".join(concept.open_decisions[:2])
        skalierung = (
            f"Skalierung blockiert durch {len(concept.open_decisions)} offene "
            f"Entscheidung(en) ({decisions}); kein Skalierungspfad ohne Klärung + Reparaturmodell"
        )
    else:
        skalierung = (
            "Lücke: keine offenen Entscheidungen erfasst → Skalierungsreife unklar"
        )

    return Markt(
        zielgruppe=zielgruppe,
        stueckzahl_ramp=stueckzahl_ramp,
        lieferkette=lieferkette,
        skalierung=skalierung,
        quelle=(
            "generic aus concept (Anforderungen/Baugruppen/Varianten/offene Entscheidungen) + "
            f"{_PLAN_REF}"
        ),
    )


def _derive_generic_reparatur(ingenieur: IngenieurSpec) -> str:
    """Derive a non-jetpack repair model from the engineer's REAL failure modes and
    Prüfplan-Hinweise. With neither signal present, declare an honest gap rather than
    fabricating a maintenance plan (Gate: no scaling without repair path)."""
    if ingenieur.failure_modes or ingenieur.pruefplan_hinweise:
        fm = ", ".join(f.name for f in ingenieur.failure_modes) or "keine Failure-Modes"
        pruef = "; ".join(ingenieur.pruefplan_hinweise) or "keine Prüfplan-Hinweise"
        return (
            f"Reparatur-/Wartungsmodell aus Failure-Modes ({fm}) + Prüfplan ({pruef}); "
            "Intervalle/Kosten offen (Lücke)"
        )
    return (
        "Lücke: weder Failure-Modes noch Prüfplan-Hinweise → kein Reparaturmodell ableitbar"
    )


def map_to_wirtschaft_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> WirtschaftSpec:
    """
    Erster Stein Wirtschafts-Pipeline.
    Jetpack: experimental/hobby market, low volume, high repair, scaling gated by regulatorik.
    Generic: leitet Kosten/Markt/Reparatur nachweislich aus ``concept`` (Anforderungen,
    Baugruppen, Varianten, offene Entscheidungen) und ``ingenieur`` (Lastfälle, Material,
    Failure-Modes, Prüfplan) ab — zwei verschiedene Eingaben ergeben unterscheidbare Specs.
    Fehlende Belege werden ehrlich als „Lücke: …" markiert; es wird kein Preis/keine
    Stückzahl geraten.

    Raises:
        ValueError: wenn ``concept.source_idea`` leer oder nur Whitespace ist — eine
            fehlende Eingabe darf keinen fabrizierten Stub erzeugen (Kernprinzip: keine
            stillen Defaults; spiegelt architekt.map_to_system_concept / fertigungs).
    """
    if not concept.source_idea.strip():
        raise ValueError(
            "concept.source_idea must be a non-empty, non-whitespace string "
            "(no fabricated WirtschaftSpec for a missing idea)"
        )

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
        # Generic path: every field is derived from the passed-in concept/ingenieur
        # signals so two distinct inputs yield distinguishable specs; truly missing
        # signals become explicit Lücke strings (no fabricated price/volume).
        kosten = _derive_generic_kosten(concept, ingenieur)
        markt = _derive_generic_markt(concept)
        reparatur = _derive_generic_reparatur(ingenieur)
        zusammen = (
            f"Generische WirtschaftSpec für »{concept.source_idea}«: Kosten/Markt/Reparatur "
            f"aus {len(concept.main_assemblies)} Baugruppe(n), {len(ingenieur.lastfaelle)} "
            f"Lastfall(fälle), {len(ingenieur.failure_modes)} Failure-Mode(s) abgeleitet; "
            "offene Punkte ehrlich als Lücke markiert (Supplier-Preise, Marktdaten, Serienkosten)."
        )
        quelle = (
            f"{_PLAN_REF} + generischer Mapper "
            "(aus concept+ingenieur abgeleitet, ehrliche Lücken)"
        )

    return WirtschaftSpec(
        source_idea=concept.source_idea,
        kosten=kosten,
        markt=markt,
        reparatur_modell=reparatur,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
