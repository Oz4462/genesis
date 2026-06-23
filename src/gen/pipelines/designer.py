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


def _generic_designer_spec(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
) -> tuple[
    list[ErgonomieAnforderung],
    list[FormEntscheidung],
    list[BedienSzenario],
    str,
    str,
]:
    """
    Generischer (Nicht-Jetpack) Designer-Pfad — input-getrieben statt konstant.

    Leitet Ergonomie, Form und Bedien-Szenarien aus den *tatsächlichen* prior
    Outputs ab: jede Baugruppe (`concept.main_assemblies`) und jeder Failure-Mode
    (`ingenieur.failure_modes`) erzeugt eigene Einträge. Dadurch ergeben
    unterschiedliche Concepts/Specs unterschiedliche DesignerSpecs (kein
    Facade-Stub mehr). Wo prior Steine keine konkreten Nutzer-/Missbrauchsdaten
    liefern, bleiben ehrliche „Lücke"-Marker stehen statt fabrizierter Sicherheit.

    Fehlerfall: Sind sowohl Baugruppen als auch Failure-Modes leer, gibt es keinen
    actionable Input — dann wird explizit abstiniert (alle Einträge als Lücke
    markiert), nicht geraten.
    """
    assemblies = concept.main_assemblies
    failure_modes = ingenieur.failure_modes

    if not assemblies and not failure_modes:
        # No actionable signal at all -> abstain honestly instead of fabricating
        # ergonomics/operation certainty (Kernprinzip: keine stillen Defaults).
        ergo = [ErgonomieAnforderung(
            "Lücke: keine Ergonomie-Basis",
            "Weder Baugruppen noch Failure-Modes aus prior Steinen vorhanden",
            "Lücke: keine Anthropometrie-/Nutzerdaten ableitbar",
            "Lücke: Architekt + Ingenieur müssen erst Baugruppen/Failure-Modes liefern",
            quelle="Generic (ehrliche Lücke — kein actionable Input)",
        )]
        form = [FormEntscheidung(
            "Lücke: keine Form-Basis",
            "Keine Baugruppen → keine Form-Entscheidung ableitbar",
            "Lücke: Form folgt aus Baugruppen-Struktur, die noch fehlt",
            "LÜCKE",
            quelle="Generic (ehrliche Lücke)",
        )]
        bedien = [BedienSzenario(
            "Lücke: keine Bedien-Szenarien",
            "Keine Failure-Modes und keine Baugruppen → keine Bedienung/Missbrauch ableitbar",
            "Lücke: Risiken unbekannt, solange prior Steine leer sind",
            "Lücke: Erst Architekt-/Ingenieur-Lauf nötig",
            quelle="Generic (ehrliche Lücke — kein actionable Input)",
        )]
        zusammen = (
            "Generische DesignerSpec ohne actionable Input: weder Baugruppen noch "
            "Failure-Modes vorhanden. Alles als Lücke markiert (keine fabrizierte Sicherheit)."
        )
        quelle = "GENESIS_PLATFORM_PLAN.md §4.6 + generic fallback (ehrliche Lücken, leerer Input)"
        return ergo, form, bedien, zusammen, quelle

    # Ergonomics: one requirement per assembly the user may interact with;
    # anthropometry stays an explicit Lücke (prior stones carry no percentile data).
    ergo = [
        ErgonomieAnforderung(
            f"Bedienbarkeit: {a.name}",
            f"Ergonomie/Haptik der Baugruppe '{a.name}' ({a.purpose}); "
            f"Schnittstellen: {', '.join(a.interfaces) or 'keine deklariert'}",
            "Lücke: keine konkreten Anthropometrie-/Perzentil-Daten aus prior Steinen",
            "Trade-off: Bedienkomfort vs. Bauraum/Gewicht der Baugruppe",
            quelle=a.quelle or "abgeleitet aus concept.main_assemblies",
        )
        for a in assemblies
    ]
    if not ergo:
        # Only failure modes present: ergonomics can only be hinted, not specified.
        ergo = [ErgonomieAnforderung(
            "Bedienbarkeit (nur aus Failure-Modes ableitbar)",
            "Keine Baugruppen vorhanden; Ergonomie nur aus Failure-Mode-Handling ableitbar",
            "Lücke: keine Anthropometrie-Daten",
            "Lücke: Baugruppen-Struktur fehlt für vollständige Ergonomie",
            quelle="abgeleitet aus ingenieur.failure_modes",
        )]

    # Form decisions: shape follows each assembly's purpose + interfaces.
    form = [
        FormEntscheidung(
            f"Form: {a.name}",
            f"Form folgt Funktion '{a.purpose}' und Schnittstellen "
            f"{', '.join(a.interfaces) or '(keine deklariert)'}",
            "Form aus Baugruppen-Zweck abgeleitet; Ästhetik-Feinheiten offen (Lücke)",
            "DECISION",
            quelle=a.quelle or "abgeleitet aus concept.main_assemblies",
        )
        for a in assemblies
    ]
    if not form:
        form = [FormEntscheidung(
            "Form: Lücke (keine Baugruppen)",
            "Keine Baugruppen → Form nur grob aus Failure-Mode-Kontext",
            "Lücke: Form-Entscheidung braucht Baugruppen-Struktur",
            "LÜCKE",
            quelle="abgeleitet aus ingenieur.failure_modes",
        )]

    # Operation/misuse scenarios are the core seam to Safety/Regulatorik: one per
    # failure mode (error handling, with its real detection/measure) plus one per
    # assembly (normal operation). Concrete misuse analysis stays a Lücke until
    # Elektriker/Safety provide the Bedien-UI + protective measures.
    bedien = [
        BedienSzenario(
            f"Fehlerfall: {fm.name}",
            f"{fm.beschreibung} (Baugruppe: {fm.aus_baugruppe})",
            f"Fehlbedienung/Ausfall: {fm.beschreibung}",
            fm.detection or "Lücke: keine Detection/Massnahme deklariert",
            quelle=fm.quelle or "abgeleitet aus ingenieur.failure_modes",
        )
        for fm in failure_modes
    ] + [
        BedienSzenario(
            f"Bedienung: {a.name}",
            f"Normale Nutzung der Baugruppe '{a.name}' ({a.purpose})",
            "Lücke: konkrete Missbrauchs-/Fehlbedienungs-Szenarien noch nicht analysiert",
            "Lücke: Bedien-UI + Schutzmassnahmen aus Elektriker/Safety nötig",
            quelle=a.quelle or "abgeleitet aus concept.main_assemblies",
        )
        for a in assemblies
    ]

    zusammen = (
        f"Generische DesignerSpec aus {len(assemblies)} Baugruppe(n) + "
        f"{len(failure_modes)} Failure-Mode(s) abgeleitet (input-getrieben). "
        "Offene Punkte als Lücke markiert (Anthropometrie, Missbrauchs-Szenarien)."
    )
    quelle = (
        "GENESIS_PLATFORM_PLAN.md §4.6 + generic fallback (abgeleitet aus "
        "Architekt-Baugruppen + Ingenieur-Failure-Modes, ehrliche Lücken)"
    )
    return ergo, form, bedien, zusammen, quelle


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
    idee_lower = concept.source_idea.lower()

    if "jetpack" in idee_lower or "flug" in idee_lower:
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
        ergo, form, bedien, zusammen, quelle = _generic_designer_spec(concept, ingenieur)

    return DesignerSpec(
        source_idea=concept.source_idea,
        ergonomie_anforderungen=ergo,
        form_entscheidungen=form,
        bedien_szenarien=bedien,
        zusammenfassung=zusammen,
        run_id=run_id,
        quelle=quelle,
    )
