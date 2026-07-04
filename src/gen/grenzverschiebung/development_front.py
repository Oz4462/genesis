"""development_front_mapper (erste Umsetzung eines Grenzverschiebungs-Moduls)

Gemäß GENESIS_PLATFORM_PLAN.md §3.3 "Die Grenzverschiebungs-Module".

Ziel (PLATFORM_PLAN):
- Kartiert die Grenze von heute: was geht, was fehlt, was ist unklar.
- Produziert `DevelopmentFrontMap`.
- Typisiert Grenzen (known_possible, possible_but_unsafe_directly, missing_measurement, missing_model, missing_component, missing_tooling, needs_breakthrough, contradicts_current_model).
- Wichtigster Output: Experimentleiter (Traum → heutige Grenze → fehlende Fähigkeit → kleinster sicherer Test → Messwert → Entscheidung → nächste Stufe → neue Grenze).

Dies ist der erste kleine, aber echte Stein unter dem Ultra-Workflow (4 Linsen + autonome Skill-Aktivierung + Selbstkontrolle).

Design-Regeln aus dem Projekt:
- Framework-frei, gegen core/interfaces und core/state wo sinnvoll.
- Quellenzwang / Provenance wo Fakten (L1).
- Deterministisch wo möglich.
- Explizite Lücken statt geratener Werte.
- Testbar inkl. Negativpfad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# --- Gemeinsamer Jetpack-Trigger (Review F5, Muster wie pipelines/_triggers) ---

#: Wortgrenzen-genaue Marker: der frühere Substring-Check ("mensch" in x and
#: "fliegen" in x) feuerte auch in "unmenschlich" + "Fliegengitter".
_JETPACK_WORD = re.compile(r"\bjetpacks?\b")
_MENSCH_WORD = re.compile(r"\bmensch(?:en)?\b")
_FLIEGEN_WORD = re.compile(r"\bfliegen\b")


def is_jetpack_traum(text: str) -> bool:
    """True gdw. der Traum den kanonischen Jetpack-Fall (PLAN §3.2/3.3) benennt.

    Wortgrenzen statt Substrings: "jetpack(s)" ODER ("mensch(en)" UND "fliegen"
    jeweils als ganzes Wort). Case-insensitiv (lowercased hier — Aufrufer brauchen
    kein eigenes ``.lower()``). Fehlerfälle: keine; ``""`` → False. Gemeinsamer
    Helfer für alle Grenzverschiebungs-Steine (eine Quelle statt 12 Kopien).
    """
    t = text.lower()
    return bool(_JETPACK_WORD.search(t)) or (
        bool(_MENSCH_WORD.search(t)) and bool(_FLIEGEN_WORD.search(t))
    )


# --- Grenztypen (exakt aus PLATFORM_PLAN.md §3.3) ---

class Grenztyp(str, Enum):
    KNOWN_POSSIBLE = "known_possible"                    # heute mit bekannten Mitteln gezeigt oder berechenbar
    POSSIBLE_BUT_UNSAFE_DIRECTLY = "possible_but_unsafe_directly"
    MISSING_MEASUREMENT = "missing_measurement"          # es fehlt eine reale Messung
    MISSING_MODEL = "missing_model"                      # es fehlt ein tragfähiges Modul
    MISSING_COMPONENT = "missing_component"              # es fehlt ein Bauteil, Material oder Prozess
    MISSING_TOOLING = "missing_tooling"                  # es fehlt Fertigung, Prüfstand oder Messgerät
    NEEDS_BREAKTHROUGH = "needs_breakthrough"            # braucht neue Technologie oder starke Verbesserung
    CONTRADICTS_CURRENT_MODEL = "contradicts_current_model"


# --- Kern-Datenstrukturen (Experimentleiter + Map) ---

@dataclass(frozen=True)
class ExperimentleiterSchritt:
    """Ein Schritt der Experimentleiter."""
    beschreibung: str
    grenzt_typ: Grenztyp | None = None
    quelle: str | None = None           # Provenance (L1)
    hypothese: bool = False


@dataclass(frozen=True)
class DevelopmentFrontMap:
    """Output von development_front_mapper (PLATFORM_PLAN §3.3)."""

    traum: str
    heutige_grenze: str
    fehlende_faehigkeiten: list[str] = field(default_factory=list)
    experimentleiter: list[ExperimentleiterSchritt] = field(default_factory=list)
    grenzen: dict[str, Grenztyp] = field(default_factory=dict)  # key -> Grenztyp
    abbruchkriterien: list[str] = field(default_factory=list)
    naechste_stufe: str | None = None

    # Metadaten für Provenance & Reproduzierbarkeit
    run_id: str | None = None
    quelle: str | None = None           # z.B. "PLATFORM_PLAN.md §3.3 + human_idee"


def map_development_front(
    idee: str,
    *,
    bekannte_grenzen: list[str] | None = None,
    run_id: str | None = None,
) -> DevelopmentFrontMap:
    """
    Funktionale erste Implementierung des development_front_mapper.

    Gemäß GENESIS_PLATFORM_PLAN.md §3.3: Kartiert einen "Traum" (Mensch-Idee)
    zu einer ehrlichen DevelopmentFrontMap mit typisierten Grenzen und
    der Experimentleiter (Traum → heutige Grenze → fehlende Fähigkeit →
    kleinster sicherer Test → Messwert → Entscheidung → nächste Stufe → neue Grenze).

    Keine Optimismus, keine unmarkierten Fakten (L1). Alle Grenzen explizit
    typisiert. Für das Jetpack-Beispiel aus dem PLAN produziert sie ein
    konkretes, reichhaltiges Map (deterministisch, erweiterbar für echte
    Wissensbasis später).

    Erfüllt die Verantwortung aus dem PLAN:
    - Produziert DevelopmentFrontMap
    - Typisiert Grenzen (nicht nur "unmöglich")
    - Startet die Experimentleiter mit sicheren Stufen
    - Markiert Lücken und Abbruchkriterien ehrlich
    """
    idee = idee.strip()
    bekannte_grenzen = bekannte_grenzen or []

    # Deterministische Analyse für das kanonische Jetpack-Beispiel (PLAN §3.2/3.3)
    # Später: Ersetzbar durch Wissensbasis + capability_gap_analyzer.
    if is_jetpack_traum(idee):
        traum = idee
        heutige_grenze = (
            "Wir haben deterministische Physik-Modelle und Validatoren für unbemannte "
            "Flugsysteme (δ+ Physics Gate: Rotor-Schwebe, Impulstheorie, Akku-Flugzeit, "
            "Strom-Budget, PD-Regelung). Keine validierte Manned-Payload-Safety, "
            "keine Redundanz für Single-Point-Failure über Menschenmengen, "
            "keine portable Energie-Dichte für >80kg Nutzlast + Pilot bei vernünftiger "
            "Flugdauer. Regulatorik für bemannten experimentellen VTOL in populated areas "
            "existiert nicht für diese Klasse."
        )
        fehlende_faehigkeiten = [
            "Manned safety validation & failure-mode coverage for public overflight (SafetyStagePlan + Falsifikations-Experiment)",
            "Portable high-density energy storage for sustained hover with >80kg total payload (missing_model + needs_breakthrough)",
            "Redundant flight control + emergency recovery (parachute/ducted fan) that guarantees <0.1s response under single failure",
            "Regulatory + human-acceptance path for experimental manned personal flight in urban environments",
        ]
        experimentleiter = [
            ExperimentleiterSchritt(
                beschreibung="Traum aufnehmen: Freier bemannter Flug als Symbol für persönliche Freiheit und Technologie-Demonstration.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.2 (Moonshot emotionaler Kern)",
            ),
            ExperimentleiterSchritt(
                beschreibung="Heutige Grenze typisieren: Unbemannte Systeme sind known_possible (bestehende δ+ Modelle + CAD/Printability). Bemannter freier Flug über Menschen ist possible_but_unsafe_directly.",
                grenzt_typ=Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY,
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (Grenztyp-Tabelle)",
            ),
            ExperimentleiterSchritt(
                beschreibung="Fehlende Fähigkeit isolieren: Keine tragfähige Manned-Safety + Energie-Dichte. → Kleinster sicherer Test = stark getetherter oder wasserbasierter Demonstrator (kein Risiko für Dritte).",
                grenzt_typ=Grenztyp.MISSING_MODEL,
            ),
            ExperimentleiterSchritt(
                beschreibung="Sicherer Test entwerfen: 1:5 Scale-Modell mit Dummy-Payload + redundanter Abschaltung + Wasser-Landung. Messen: Flugzeit, Stabilität unter Last, Failure-Response-Zeit.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (Experimentleiter + safety_ladder)",
            ),
            ExperimentleiterSchritt(
                beschreibung="Messwert → Entscheidung: Bei erfolgreicher tethered Demo (z.B. 3min stable hover >20kg Payload, <0.5s safe abort) → nächste Stufe = tethered public demo mit SafetyStagePlan. Bei Nichterreichen: boundary_reviser oder technology_roadmapper für neue Batterie-Technologie.",
            ),
        ]
        grenzen = {
            "unbemannter stabiler Hover (bestehende Physik)": Grenztyp.KNOWN_POSSIBLE,
            "bemannter freier Flug über Menschenmenge ohne Failure-Risiko": Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY,
            "portable Energie für 5+ min bemannten Hover >80kg": Grenztyp.NEEDS_BREAKTHROUGH,
            "regulatorischer Pfad für bemannten personal flight in populated area": Grenztyp.MISSING_TOOLING,
            "validierte Manned Single-Failure Recovery <0.1s": Grenztyp.MISSING_MODEL,
        }
        abbruchkriterien = [
            "Jede Failure-Mode, die Nutzlast auf Menschen fallen lässt ohne garantierte <0.1s sichere Landung/Parachute-Äquivalent.",
            "Energie-Dichte < aktuelle LiPo/Li-Ion Limits ohne neue Chemie → Abbruch und Technology-Roadmap.",
        ]
        naechste_stufe = "safety_ladder + experiment_designer für tethered public Demo + capability_gap_analyzer für Energie"
    else:
        # Ehrlicher Fallback für beliebige Ideen (noch nicht reichhaltig analysiert)
        traum = idee
        # Review F9: capability_gap_analyzer/milestone_builder sind GEBAUT — der
        # frühere Text "zukünftiger Stein" war Kommentar-Drift. Ehrlich ist: die
        # Steine existieren, ihre Verdrahtung in diesen generischen Fallback fehlt.
        heutige_grenze = "Noch nicht detailliert kartiert für diese Idee — siehe Experimentleiter und offene Lücken. Volle Analyse erfordert Wissensbasis + capability_gap_analyzer (Stein gebaut, in diesen Fallback noch nicht verdrahtet — Lücke)."
        fehlende_faehigkeiten = [
            "Vollständige Grenz-Kartierung mit realen Quellen/Tests und Domänen-Wissen (Steine gebaut, Verdrahtung in diesen Fallback fehlt — Lücke)",
            "Sichere Demo-Varianten + SafetyStagePlan",
        ]
        experimentleiter = [
            ExperimentleiterSchritt(
                beschreibung="Idee / Traum aufnehmen und emotionalen/technischen Kern extrahieren.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.2 (Moonshot-Pipeline)",
            ),
            ExperimentleiterSchritt(
                beschreibung="Heutige Grenze grob typisieren (was ist known_possible vs. needs_breakthrough etc.).",
                hypothese=True,
            ),
            ExperimentleiterSchritt(
                beschreibung="Kleinster sicherer Test definieren, der echtes Wissen erzeugt.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.3 (Experimentleiter)",
            ),
        ]
        grenzen = {g: Grenztyp.MISSING_MEASUREMENT for g in bekannte_grenzen} or {
            "generische Machbarkeit der Idee": Grenztyp.MISSING_MEASUREMENT
        }
        abbruchkriterien = [
            "Keine sichere Stufe definierbar ohne neue Technologie (needs_breakthrough)",
        ]
        naechste_stufe = "capability_gap_analyzer + milestone_builder (gebaute Grenzverschiebungs-Steine — nächster Schritt in der Kette)"

    front_map = DevelopmentFrontMap(
        traum=traum,
        heutige_grenze=heutige_grenze,
        fehlende_faehigkeiten=fehlende_faehigkeiten,
        experimentleiter=experimentleiter,
        grenzen=grenzen,
        abbruchkriterien=abbruchkriterien,
        naechste_stufe=naechste_stufe,
        run_id=run_id,
        quelle="development_front_mapper (funktionaler Stein, Ultra-Workflow 2026-06-15) + GENESIS_PLATFORM_PLAN.md §3.3",
    )
    return front_map
