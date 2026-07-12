"""breakthrough_watch — neunter Grenzverschiebungs-Modul (nächster aktiver Stein nach bench_test_runner).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: beobachtet neue Tools, Papers, Materialien, Komponenten und Verfahren.
- Output: `FrontierUpdate`.

Dieses Modul nimmt eine `DevelopmentFrontMap` und produziert eine strukturierte
Beobachtung der Technologie-Front (neue Papers, Tools, Materialien, die die realen
Roadmap-Gaps der KARTE adressieren könnten), mit Relevanz-Bewertung und Verknüpfung
zu den tatsächlich offenen Punkten.

Kernregel (L1/„keine stillen Defaults"): Jedes emittierte `FrontierItem` referenziert
**einen realen, offenen Gap der Eingabe-Map** (`front_map.fehlende_faehigkeiten` oder ein
offener Schlüssel in `front_map.grenzen`). Hat die Map keinen offenen Gap, ist die ehrliche
Antwort ein **leerer/abstinenter** `FrontierUpdate` — kein fabrizierter Konserven-Treffer.

Der reichhaltige Jetpack-Katalog (Energie/Control/Recovery) bleibt als
regressions-geschützter Spezialfall: seine Items erscheinen aber nur, wenn die Map
einen passenden offenen Gap trägt, und ihre `relevanz_fuer_gap` ist der echte Gap-Text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .development_front import Grenztyp

if TYPE_CHECKING:
    from .development_front import DevelopmentFrontMap


@dataclass(frozen=True)
class FrontierItem:
    """Ein einzelnes beobachtetes Item (Paper, Tool, Material, Verfahren, Watch-Target).

    ``evidence_level`` (Review F6): "synthetic" = deterministisch fabriziertes
    Plan-Beispiel (Default — breakthrough_watch has no live scan yet); "verified"
    only when an independent, checked source backs the item. boundary_reviser
    upgrades Grenztypen ONLY for verified items.
    """

    titel: str
    typ: str                           # "Paper", "Tool", "Material", "Verfahren", "Watch"
    beschreibung: str
    relevanz_fuer_gap: str             # MUSS ein realer offener Gap der Eingabe-Map sein
    moeglicher_impact: str
    quelle: str | None = None
    evidence_level: str = "synthetic"  # "synthetic" | "verified"


@dataclass(frozen=True)
class FrontierUpdate:
    """Der strukturierte Frontier-Update (Output des Moduls)."""

    source_traum: str
    items: list[FrontierItem]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


@dataclass(frozen=True)
class _BreakthroughEntry:
    """Kuratierter, domänenspezifischer Durchbruch + die Stichwörter, die einen Gap matchen.

    Die Stichwörter sind bewusst zwei-/mehrsprachig (en/de), weil die Gaps einer
    DevelopmentFrontMap je nach Quelle englisch (fehlende_faehigkeiten) oder deutsch
    (grenzen-Schlüssel) formuliert sind.
    """

    titel: str
    typ: str
    beschreibung: str
    moeglicher_impact: str
    quelle: str
    keywords: tuple[str, ...]

    def fuer_gap(self, gap: str) -> "FrontierItem":
        """Erzeugt das FrontierItem für einen konkreten, realen Gap-Text der Map."""
        return FrontierItem(
            titel=self.titel,
            typ=self.typ,
            beschreibung=self.beschreibung,
            relevanz_fuer_gap=gap,
            moeglicher_impact=self.moeglicher_impact,
            quelle=self.quelle,
            evidence_level="synthetic",
        )


# Kuratierter Jetpack-Domänen-Katalog (Energie / Control / Recovery).
# Regressions-geschützter Spezialfall: erscheint NUR für Maps der bemannten-Flug-Domäne
# und NUR an realen offenen Gaps, deren Text die Stichwörter trägt — nie als Konserve.
_JETPACK_CATALOG: tuple[_BreakthroughEntry, ...] = (
    _BreakthroughEntry(
        titel="Solid-State Battery Breakthrough (2026 Lab Results)",
        typ="Material",
        beschreibung=(
            "Neue Sulfid-basierte Solid-State Zellen mit >350 Wh/kg bei Pack-Level in "
            "Lab-Scale, 300+ Zyklen, verbessertes Abuse-Verhalten."
        ),
        moeglicher_impact=(
            "Könnte den Prototyp auf >320 Wh/kg bringen und das Zyklenziel erleichtern."
        ),
        quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_builder P1 + bench_test T1 (Stand 2026)",
        keywords=("energy", "energie", "battery", "batterie", "wh/kg", "energie-dichte"),
    ),
    _BreakthroughEntry(
        titel="Dissimilar Redundant FC Architecture for Urban Air Mobility (Paper 2026)",
        typ="Verfahren",
        beschreibung=(
            "Paper zu dissimilar redundant Flight-Controller-Architekturen für eVTOL, "
            "mit <50ms Switch und <1kg Gewicht für 100kg+ Klasse."
        ),
        moeglicher_impact="Könnte die redundante Flugkontrolle leichter und schneller machen als geplant.",
        quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_builder P2 + teststand T1",
        keywords=("flight control", "flugkontrolle", "flight controller", "redundant flight"),
    ),
    _BreakthroughEntry(
        titel="Ultra-Light Ballistic Parachute with Rocket Assist (Commercial 2026)",
        typ="Tool",
        beschreibung=(
            "Neues kommerzielles System für <80kg bemannte Systeme, Gesamtgewicht <2.5kg, "
            "Auslösezeit <1.5s, zertifiziert für bemannte Anwendung."
        ),
        moeglicher_impact="Könnte den Recovery-Pfad vereinfachen und das Gewichtsziel erreichen.",
        quelle="GENESIS_PLATFORM_PLAN.md §3.3 + technology_roadmapper Recovery Gap",
        keywords=("recovery", "parachute", "fallschirm", "emergency recovery", "single-failure recovery"),
    ),
)


def _is_jetpack_domain(traum: str) -> bool:
    """Klassifiziert die Map als bemannte-Flug-Domäne (Jetpack-Katalog anwendbar)."""
    low = traum.lower()
    return "jetpack" in low or ("mensch" in low and "fliegen" in low)


def _open_gaps(front_map: "DevelopmentFrontMap") -> list[str]:
    """Sammelt die realen, offenen Gaps der Map in deterministischer Reihenfolge.

    Offen = alle `fehlende_faehigkeiten` (per Definition offen) plus jeder
    `grenzen`-Schlüssel, dessen Grenztyp NICHT `KNOWN_POSSIBLE` ist
    (`known_possible` ist heute schon machbar und damit kein offener Watch-Gap).
    Duplikate werden ordnungserhaltend entfernt, damit dasselbe Gap nicht doppelt
    Items erzeugt.
    """
    gaps: list[str] = []
    for gap in front_map.fehlende_faehigkeiten:
        if gap and gap not in gaps:
            gaps.append(gap)
    for key, typ in front_map.grenzen.items():
        # Nur offene Grenzen sind ein Watch-Ziel; bereits Machbares nicht.
        if typ is Grenztyp.KNOWN_POSSIBLE:
            continue
        if key and key not in gaps:
            gaps.append(key)
    return gaps


def _honest_watch_item(gap: str) -> FrontierItem:
    """Ehrliches Abstinenz-Item für einen offenen Gap ohne bekannten Durchbruch.

    Prinzip 4 (`„Ich weiß es nicht" ist ein gültiger Output`): statt einen Treffer zu
    fabrizieren, wird der Gap als aktiver Beobachtungspunkt ausgewiesen.
    """
    return FrontierItem(
        titel="Offener Watch-Target (noch kein bekannter Durchbruch)",
        typ="Watch",
        beschreibung=(
            "Für diese offene Fähigkeit/Grenze ist GENESIS aktuell kein konkreter "
            "Durchbruch (Paper/Tool/Material/Verfahren) bekannt — ehrlicher aktiver "
            "Beobachtungspunkt statt fabriziertem Treffer."
        ),
        relevanz_fuer_gap=gap,
        moeglicher_impact="Unbekannt bis ein realer Durchbruch beobachtet wird (Abstention).",
        quelle="breakthrough_watch (ehrlicher Per-Gap-Watch) + GENESIS_PLATFORM_PLAN.md §3.3",
    )


def watch_frontier(
    front_map: "DevelopmentFrontMap",
    *,
    run_id: str | None = None,
) -> FrontierUpdate:
    """Beobachtet die Technologie-Front gegen die REALEN offenen Gaps der Eingabe-Map.

    Für jeden offenen Gap (`fehlende_faehigkeiten` + offene `grenzen`-Schlüssel) wird
    geprüft, ob der kuratierte Jetpack-Domänen-Katalog (nur bei bemannter-Flug-Domäne)
    einen passenden Durchbruch trägt. Jedes emittierte `FrontierItem` referenziert in
    `relevanz_fuer_gap` exakt diesen realen Gap-Text. Findet sich kein Durchbruch, wird
    ein ehrliches Abstinenz-Watch-Item für den Gap emittiert. Hat die Map gar keinen
    offenen Gap, ist das Ergebnis ein leerer, abstinenter `FrontierUpdate`.

    Determinismus: gleiche Map → identischer FrontierUpdate (geordnete Iteration über
    Gaps und Katalog). `run_id` wird durchgereicht.

    Args:
        front_map: Die zu beobachtende Entwicklungs-Front-Karte. Quelle der realen Gaps.
        run_id: Optionale Lauf-ID für Provenance/Reproduzierbarkeit (durchgereicht).

    Returns:
        FrontierUpdate mit Items, die ausschließlich reale offene Gaps der Map adressieren.

    Raises:
        TypeError: wenn `front_map` `None` ist (fail-loud statt geratener Default).
    """
    if front_map is None:
        raise TypeError("watch_frontier benötigt eine DevelopmentFrontMap, nicht None.")

    traum = front_map.traum
    is_jetpack = _is_jetpack_domain(traum)
    gaps = _open_gaps(front_map)

    if not gaps:
        # Ehrliche Abstention: keine offenen Gaps → nichts zu beobachten.
        return FrontierUpdate(
            source_traum=traum,
            items=[],
            zusammenfassung=(
                "Keine offenen Roadmap-Gaps in dieser DevelopmentFrontMap — kein "
                "Frontier-Item zu melden (ehrliche Abstention statt fabriziertem Treffer)."
            ),
            run_id=run_id,
            quelle="breakthrough_watch (gap-gebunden) + GENESIS_PLATFORM_PLAN.md §3.3",
        )

    items: list[FrontierItem] = []
    for gap in gaps:
        gap_low = gap.lower()
        matched = [
            entry.fuer_gap(gap)
            for entry in _JETPACK_CATALOG
            if is_jetpack and any(kw in gap_low for kw in entry.keywords)
        ]
        # Jeder offene Gap erhält mindestens eine ehrliche Antwort: passende
        # Durchbrüche oder — wenn keiner bekannt ist — ein Abstinenz-Watch-Item.
        items.extend(matched if matched else [_honest_watch_item(gap)])

    konkrete = sum(1 for it in items if it.typ != "Watch")
    watches = len(items) - konkrete
    zusammenfassung = (
        f"{len(items)} Frontier-Item(s) für {len(gaps)} offene Roadmap-Gap(s) dieser Karte: "
        f"{konkrete} konkrete Durchbruch-Hinweise, {watches} ehrliche Watch-Targets ohne "
        f"bekannten Durchbruch. Jedes Item ist an einen realen Gap der Eingabe-Map gebunden."
    )

    return FrontierUpdate(
        source_traum=traum,
        items=items,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="breakthrough_watch (gap-gebunden) + GENESIS_PLATFORM_PLAN.md §3.3",
    )
