"""designer — Designer-Pipeline first stone (PLAN §4.6).

Gemäß GENESIS_PLATFORM_PLAN.md §4.6:
- Aufgabe: Ergonomie, Haptik, Form, Bedienbarkeit, Ästhetik, Nutzerführung.
- Outputs: Ergonomie-Spec, Form-Entscheidungen, Bedien-Hinweise, Trade-offs (markiert), UI/Fehler-Szenarien.
- Gate: keine Designentscheidung als Fakt tarnen; Ergonomieannahmen markieren; Bedienfehler/Missbrauch sichtbar.

Erster Stein: deterministischer Mapper von SystemConcept + IngenieurSpec zu DesignerSpec.
Jetpack-Beispiel: Harness/Tether Komfort, Trage-Form, Bedienung (thrust control, emergency), Ästhetik (sichtbar/sicher).
Generic Fallback mit ehrlichen Gaps.

Naht: Nimmt prior Outputs, erzeugt Design-Anforderungen für CAD (Form), Techniker (Montage/Haptik), Elektriker (Bedien-UI), Realisierungspaket (Ergonomie in Regulatorik/Drawings).
"""

from __future__ import annotations

from dataclasses import dataclass

from ._triggers import is_flight_idea
from .architekt import SystemConcept
from .ingenieur import IngenieurSpec


@dataclass(frozen=True)
class ErgonomieAnforderung:
    """Ergonomie / Haptik / Bedienbarkeits-Anforderung mit Beleg."""
    name: str
    beschreibung: str
    annahme: str  # z.B. "durchschnittliche Körpergröße 170cm"
    trade_off: str | None = None
    quelle: str | None = None


@dataclass(frozen=True)
class FormEntscheidung:
    """Form / Ästhetik Entscheidung (explizit als Entscheidung markiert)."""
    name: str
    beschreibung: str
    begruendung: str  # z.B. "sichtbar + aerodynamisch"
    markiert_als: str = "DECISION"
    quelle: str | None = None


@dataclass(frozen=True)
class BedienSzenario:
    """Bedien- / Missbrauchs-Szenario (für Gate und Regulatorik)."""
    name: str
    beschreibung: str
    fehler_risiko: str
    massnahme: str
    quelle: str | None = None


@dataclass(frozen=True)
class DesignerSpec:
    """Output der Designer-Pipeline (erster Stein)."""
    source_idea: str
    ergonomie_anforderungen: list[ErgonomieAnforderung]
    form_entscheidungen: list[FormEntscheidung]
    bedien_szenarien: list[BedienSzenario]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def map_to_designer_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    run_id: str | None = None,
) -> DesignerSpec:
    """
    Erster Stein Designer-Pipeline.
    Jetpack: Harness-Komfort, Trage-Form, einfache Bedienung (thrust + emergency), sichtbare Sicherheit.
    Generic: ehrliche Lücken.
    """
    if is_flight_idea(concept.source_idea):
        ergo = [
            ErgonomieAnforderung("Harness Fit", "Tether/Harness passt 5.-95. Perzentil Körper (ca. 150-190cm)", "durchschnittliche Nutzergröße 170cm +/-20cm", "Trade-off: mehr Verstellbarkeit vs. Gewicht/Volumen", quelle="PLAN §4.6 + Techniker Montage + Safety-Ladder"),
            ErgonomieAnforderung("Haptik / Bedienung", "Thrust-Control und Emergency-Cutoff erreichbar ohne Loslassen der Griffe", "Zwei-Hand-Bedienung typisch für Jetpack", None, quelle="Elektriker Bedien + Architekt Nutzer"),
        ]
        form = [
            FormEntscheidung("Sichtbare Sicherheit", "Helle Farben + klare Tether-Form für Sichtbarkeit in Menschenmenge", "Ästhetik sekundär zu Sicherheit + Erkennbarkeit (nicht Tarnung)", "DECISION", quelle="PLAN §4.6 + Realisierungspaket Regulatorik"),
            FormEntscheidung("Kompakte Form", "Tether-Anchor + Harness flach (<10cm Höhe) für Tragekomfort", "Aerodynamik + Packbarkeit vs. Volumen für Elektronik", "DECISION", quelle="CAD bounding_box + Ingenieur Volumen"),
        ]
        bedien = [
            BedienSzenario("Normal Flight", "Pilot steuert Thrust mit Händen, Tether aktiv", "Fehlbedienung Thrust → unkontrollierter Aufstieg", "Redundanter Cutoff + visuelles/auditives Feedback", quelle="Safety + Elektriker"),
            BedienSzenario("Emergency", "Tether loss or power failure", "Panik → falsche Handgriffe", "Einfache, taktile Emergency-Handles + klare Beschriftung", quelle="PLAN §4.6 Bedienfehler + Techniker Reparatur"),
            BedienSzenario("Missbrauch / Kinder", "Unbefugte Nutzung", "Unkontrollierter Flug in Menge", "Physische Verriegelung + Warnung 'Nur für geschulte Nutzer'", quelle="Regulatorik-Pfad"),
        ]
        zusammen = "Jetpack DesignerSpec: Ergonomie für 5-95% (Harness Fit, Haptik), Form-Entscheidungen für Sichtbarkeit + Kompaktheit, Bedien-Szenarien mit Missbrauch/Risiken. Naht zu CAD (Form), Elektriker (Bedien), Safety."
        quelle = "GENESIS_PLATFORM_PLAN.md §4.6 (Designer-Pipeline) + prior Elektriker/Techniker/Safety/CAD + Jetpack-Kanon"
    else:
        ergo = [ErgonomieAnforderung("Basic Fit", "Einfache Passform für durchschnittliche Nutzer", "keine spezifische Perzentil-Angabe", "Lücke: detaillierte Anthropometrie-Daten", quelle="Generic")]
        form = [FormEntscheidung("Einfache Form", "Funktional + unauffällig", "Ästhetik nicht priorisiert", "DECISION", quelle="Generic")]
        bedien = [BedienSzenario("Basic Use", "Standard Bedienung", "Fehlbedienung möglich", "Einfache Anleitung", quelle="Generic - Lücke für Missbrauchsszenarien")]
        zusammen = f"Generische DesignerSpec für '{concept.source_idea[:40]}...'. Viele Details als Lücke markiert (keine spezifische Nutzer/Ergonomie aus prior Steinen)."
        quelle = "GENESIS_PLATFORM_PLAN.md §4.6 + generic fallback (ehrliche Lücken)"

    return DesignerSpec(
        source_idea=concept.source_idea,
        ergonomie_anforderungen=ergo,
        form_entscheidungen=form,
        bedien_szenarien=bedien,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
