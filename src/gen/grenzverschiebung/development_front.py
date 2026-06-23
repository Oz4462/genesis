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

from dataclasses import dataclass, field
from enum import Enum

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


# --- Heuristische Typisierung bekannter Grenzen ---

# Stichwort → Grenztyp. Bewusst rule-based, aber der Typ wird AUS dem Text der
# Grenze abgeleitet (kein konstanter Default) — so spiegelt die Map die reale
# Eingabe wider. Reihenfolge = Priorität (erste passende Gruppe gewinnt).
_GRENZ_STICHWORTE: list[tuple[Grenztyp, tuple[str, ...]]] = [
    (Grenztyp.CONTRADICTS_CURRENT_MODEL,
     ("widerspricht", "verbietet", "unmöglich", "perpetuum", "thermodynamik", "kausalität")),
    (Grenztyp.NEEDS_BREAKTHROUGH,
     ("durchbruch", "breakthrough", "neue technologie", "energiedichte", "energie-dichte",
      "supraleiter", "quanten")),
    (Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY,
     ("unsicher", "gefahr", "gefährlich", "risiko", "sicher", "safety", "mensch")),
    (Grenztyp.MISSING_MODEL,
     ("modell", "model", "theorie", "simulation", "regelung", "vorhersage")),
    (Grenztyp.MISSING_COMPONENT,
     ("bauteil", "material", "komponente", "akku", "batterie", "motor", "werkstoff")),
    (Grenztyp.MISSING_TOOLING,
     ("fertigung", "werkzeug", "prüfstand", "tooling", "messgerät", "prüfung",
      "regulator", "zulassung")),
    (Grenztyp.MISSING_MEASUREMENT,
     ("messung", "messen", "messwert", "sensor", "daten", "kalibrier")),
]


def _klassifiziere_grenze(grenze: str) -> Grenztyp:
    """Leitet den Grenztyp aus dem Text einer bekannten Grenze ab.

    Was/Warum: Der Typ MUSS aus dem Inhalt folgen (L1/„keine stillen Defaults"),
    damit die Map die echte Eingabe konsumiert statt eines konstanten Werts.
    Trägt der Text kein erkennbares Signal, wird die Grenze ehrlich als
    MISSING_MEASUREMENT typisiert (eine reale Messung fehlt noch) — das ist die
    schwächste, am wenigsten anmaßende Aussage, kein optimistisches Raten.
    """
    text = grenze.lower()
    for typ, stichworte in _GRENZ_STICHWORTE:
        if any(s in text for s in stichworte):
            return typ
    return Grenztyp.MISSING_MEASUREMENT


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

    Args:
        idee: Der menschliche „Traum"/das Problem. Darf nicht leer/whitespace sein.
        bekannte_grenzen: Optional vorab bekannte Grenzen. Jede wird typisiert,
            in `fehlende_faehigkeiten` referenziert und bekommt einen eigenen
            Experimentleiter-Schritt (generischer Pfad).
        run_id: Provenance/Reproduzierbarkeit (A5).

    Raises:
        ValueError: Wenn `idee` leer oder nur Whitespace ist (keine stille leere
            Map — eine Grenze ohne Traum ist nicht kartierbar).
    """
    idee = idee.strip()
    if not idee:
        raise ValueError(
            "idee darf nicht leer/whitespace sein — ohne Traum gibt es keine "
            "Grenze zu kartieren (keine stille leere Map)."
        )
    bekannte_grenzen = [g.strip() for g in (bekannte_grenzen or []) if g and g.strip()]

    # Deterministische Analyse für das kanonische Jetpack-Beispiel (PLAN §3.2/3.3)
    # Später: Ersetzbar durch Wissensbasis + capability_gap_analyzer.
    if "jetpack" in idee.lower() or ("mensch" in idee.lower() and "fliegen" in idee.lower()):
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
        # Generischer Pfad: echte Ableitung aus (idee + bekannte_grenzen).
        # Jede bekannte Grenze wird typisiert, in fehlende_faehigkeiten referenziert
        # und bekommt einen eigenen Experimentleiter-Schritt. Trägt die Eingabe kein
        # Signal (keine bekannten Grenzen), bleibt die Map ehrlich abstinent statt
        # eine kanonische Pseudo-Grenze zu erfinden (keine stillen Defaults).
        traum = idee

        # heutige_grenze spiegelt die konkrete Idee → zwei Ideen ergeben zwei Maps.
        kurz = idee if len(idee) <= 120 else idee[:117] + "..."
        if bekannte_grenzen:
            heutige_grenze = (
                f"Für „{kurz}“ liegen {len(bekannte_grenzen)} bekannte Grenze(n) vor, "
                "die unten typisiert und je in einen kleinsten sicheren Test überführt "
                "werden. Eine vollständige quellenbasierte Kartierung erfordert zusätzlich "
                "Wissensbasis + capability_gap_analyzer (zukünftiger Stein)."
            )
        else:
            heutige_grenze = (
                f"Für „{kurz}“ sind noch KEINE konkreten Grenzen benannt — die Map ist "
                "daher ehrlich abstinent (keine erfundenen Grenzen). Nächster Schritt: "
                "bekannte_grenzen liefern oder capability_gap_analyzer ausführen, um reale "
                "Grenzen mit Quellen zu erzeugen."
            )

        # grenzen: jede bekannte Grenze AUS DEM TEXT typisiert (kein flacher Default).
        grenzen = {g: _klassifiziere_grenze(g) for g in bekannte_grenzen}

        # fehlende_faehigkeiten referenzieren jede bekannte Grenze explizit.
        fehlende_faehigkeiten = [
            f"Schließen von „{g}“ (typisiert als {grenzen[g].value}) durch realen Test/Quelle"
            for g in bekannte_grenzen
        ]
        # Ohne benannte Grenzen bleibt eine ehrliche Meta-Lücke (kein leeres Versprechen).
        if not fehlende_faehigkeiten:
            fehlende_faehigkeiten = [
                "Vollständige Grenz-Kartierung mit realen Quellen/Tests und Domänen-Wissen "
                "(noch keine konkreten Grenzen benannt)",
            ]

        # Experimentleiter: feste Eröffnung + ein Schritt pro bekannter Grenze.
        experimentleiter = [
            ExperimentleiterSchritt(
                beschreibung=f"Traum aufnehmen: „{kurz}“ — emotionalen/technischen Kern extrahieren.",
                quelle="GENESIS_PLATFORM_PLAN.md §3.2 (Moonshot-Pipeline)",
            ),
            ExperimentleiterSchritt(
                beschreibung=(
                    "Heutige Grenze grob typisieren (known_possible vs. needs_breakthrough etc.). "
                    "Hypothese bis durch realen Test/Quelle bestätigt."
                ),
                hypothese=True,
            ),
        ]
        for g in bekannte_grenzen:
            typ = grenzen[g]
            experimentleiter.append(
                ExperimentleiterSchritt(
                    beschreibung=(
                        f"Grenze „{g}“ ({typ.value}): kleinsten sicheren Test entwerfen, der "
                        "diese Grenze gezielt prüft und einen Messwert → Entscheidung erzeugt."
                    ),
                    grenzt_typ=typ,
                )
            )
        if not bekannte_grenzen:
            experimentleiter.append(
                ExperimentleiterSchritt(
                    beschreibung="Kleinsten sicheren Test definieren, der echtes Wissen erzeugt.",
                    quelle="GENESIS_PLATFORM_PLAN.md §3.3 (Experimentleiter)",
                )
            )

        # Abbruchkriterien: für Grenzen, die einen Durchbruch/Widerspruch erfordern,
        # ehrlich ein hartes Stopp-Kriterium ergänzen (aus den Typen abgeleitet).
        abbruchkriterien = [
            "Keine sichere Stufe definierbar ohne neue Technologie (needs_breakthrough)",
        ]
        for g in bekannte_grenzen:
            if grenzen[g] in (Grenztyp.NEEDS_BREAKTHROUGH, Grenztyp.CONTRADICTS_CURRENT_MODEL):
                abbruchkriterien.append(
                    f"„{g}“ verlangt {grenzen[g].value} → Abbruch und Technology-Roadmap "
                    "statt unsicherem Direkt-Bau."
                )
        naechste_stufe = "capability_gap_analyzer + milestone_builder (nächste Grenzverschiebungs-Module)"

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
