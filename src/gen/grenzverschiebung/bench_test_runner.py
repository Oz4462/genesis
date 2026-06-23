"""bench_test_runner — achter Grenzverschiebungs-Modul (nächster aktiver Stein nach technology_builder).

Gemäß GENESIS_PLATFORM_PLAN.md §3.3:
- Aufgabe: plant UND bewertet den Messlauf für diesen Prototyp.
- Output: `BenchTestPlan` (eine `BenchTestResult` pro Prototyp).

Dieses Modul nimmt die `TechnologyPrototypePlan` aus dem technology_builder und
produziert pro Prototyp einen konkreten Messplan: Messdaten-Anforderungen,
Erfolgskriterien und Abbruchkriterien werden **aus den realen `anforderungen`/`risiken`
des jeweiligen Prototyps abgeleitet** (nicht hartkodiert), und jede `BenchTestResult`
trägt eine explizite, ehrliche `ergebnis_bewertung` — niemals ein stilles `None`.

Ehrlichkeits-Prinzip (CLAUDE.md Kernprinzip 1 + 4): Es existiert in dieser Stufe noch
kein realer Messlauf. Deshalb ist die Bewertung honest `geplant_nicht_ausgefuehrt`
(mit Begründung), statt ein Pass/Fail zu erfinden, das keine Messung deckt. Trägt ein
Prototyp keine Anforderungen, lässt sich kein Erfolgskriterium ableiten — das wird als
`geplant_unvollstaendig_keine_kriterien` ausgewiesen, nicht überspielt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .technology_builder import TechnologyPrototypePlan, TechnologyPrototypeSpec


# Ehrliche Bewertungs-Stati. Single source of truth, damit Tests und Downstream
# (breakthrough_watch, safety_ladder) gegen Konstanten und nicht gegen Stringliterale prüfen.
STATUS_GEPLANT_NICHT_AUSGEFUEHRT = "geplant_nicht_ausgefuehrt"
STATUS_GEPLANT_UNVOLLSTAENDIG = "geplant_unvollstaendig_keine_kriterien"


@dataclass(frozen=True)
class BenchTestResult:
    """Ein einzelnes Messergebnis für einen Prototyp (Output des Moduls).

    `ergebnis_bewertung` ist nie `None`: solange kein realer Messlauf existiert, steht
    hier ein ehrlicher Plan-Status (`STATUS_GEPLANT_*`), begründet in
    `bewertung_begruendung`. Nach einem echten Lauf würde hier ein gemessenes Verdikt
    (z.B. "bestanden"/"nicht erreicht") gesetzt.
    """

    prototype_name: str
    test_name: str
    beschreibung: str
    messdaten_anforderungen: list[str]
    erfolgskriterien: list[str]
    abbruchkriterien: list[str]
    geplante_dauer: str
    ergebnis_bewertung: str = STATUS_GEPLANT_NICHT_AUSGEFUEHRT
    bewertung_begruendung: str | None = None
    quelle: str | None = None


@dataclass(frozen=True)
class BenchTestPlan:
    """Der vollständige Messplan und Ergebnis-Bewertung (Output des Moduls)."""

    source_traum: str
    results: list[BenchTestResult]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


# Universelles Sicherheits-Abbruchkriterium: gilt unabhängig vom konkreten Prototyp,
# damit auch ein risiko-armer Prototyp nie ohne Stopp-Bedingung gefahren wird.
_UNIVERSAL_ABBRUCH = "Sicherheitsrisiko für Mensch/Material oder Verlassen des freigegebenen Test-Stand-Fensters"


def _messdaten_anforderungen(spec: "TechnologyPrototypeSpec") -> list[str]:
    """Jede Bau-Anforderung wird zur Messgröße: gemessen wird, ob sie erfüllt ist.

    Leitet direkt aus `spec.anforderungen` ab — kein Hardcode. Trägt der Prototyp die
    reichen Jetpack-Anforderungen, erscheint deren Inhalt hier; trägt er nichts, bleibt
    die Liste leer (ehrlich), statt einen Default zu erfinden.
    """
    return [f"Messung: {a}" for a in spec.anforderungen]


def _erfolgskriterien(spec: "TechnologyPrototypeSpec") -> list[str]:
    """Erfolgskriterium = die jeweilige Anforderung muss im Messlauf erfüllt sein."""
    return [f"Erfüllt im Messlauf: {a}" for a in spec.anforderungen]


def _abbruchkriterien(spec: "TechnologyPrototypeSpec") -> list[str]:
    """Abbruchkriterien aus den realen Risiken plus universelles Sicherheits-Stopp.

    Jedes deklarierte Risiko, das sich materialisiert, ist ein Abbruchgrund — so wird
    der Messplan an die echten Risiken des Prototyps gekoppelt statt an eine Konstante.
    """
    aus_risiken = [f"Abbruch bei Eintreten von: {r}" for r in spec.risiken]
    # Reihenfolge: prototyp-spezifisch zuerst, dann das universelle Stopp-Kriterium.
    return [*aus_risiken, _UNIVERSAL_ABBRUCH]


def _bench_result_for(spec: "TechnologyPrototypeSpec") -> BenchTestResult:
    """Baut genau eine `BenchTestResult` aus einer Prototyp-Spec — vollständig abgeleitet.

    Setzt eine ehrliche `ergebnis_bewertung`:
    - hat der Prototyp Anforderungen → vollständiger Plan, Status
      `geplant_nicht_ausgefuehrt` (noch kein realer Messlauf);
    - hat er keine → kein Erfolgskriterium ableitbar, Status
      `geplant_unvollstaendig_keine_kriterien` (Lücke ehrlich ausgewiesen).
    """
    messdaten = _messdaten_anforderungen(spec)
    erfolg = _erfolgskriterien(spec)
    abbruch = _abbruchkriterien(spec)

    if spec.anforderungen:
        bewertung = STATUS_GEPLANT_NICHT_AUSGEFUEHRT
        begruendung = (
            "Messplan vollständig aus den Prototyp-Anforderungen und -Risiken abgeleitet. "
            "Es liegt noch kein realer Messlauf vor, daher (ehrlich) kein Pass/Fail-Verdikt."
        )
    else:
        bewertung = STATUS_GEPLANT_UNVOLLSTAENDIG
        begruendung = (
            "Prototyp trägt keine Anforderungen — es lässt sich kein Erfolgskriterium "
            "ableiten; der Messlauf ist nicht bewertbar (keine stillen Defaults)."
        )

    return BenchTestResult(
        prototype_name=spec.name,
        test_name=f"Bench-Validierung: {spec.ziel_technologie}",
        beschreibung=(
            f"Messlauf auf {spec.test_stand_tie_in} zur Validierung des Prototyps "
            f"'{spec.name}'. {spec.beschreibung}"
        ),
        messdaten_anforderungen=messdaten,
        erfolgskriterien=erfolg,
        abbruchkriterien=abbruch,
        geplante_dauer=f"Messlauf-Fenster orientiert am Prototyp-Zeitplan: {spec.grober_zeitplan}",
        ergebnis_bewertung=bewertung,
        bewertung_begruendung=begruendung,
        quelle=(
            f"bench_test_runner (abgeleitet aus Prototyp-Spec) + "
            f"{spec.quelle or 'technology_builder'} + GENESIS_PLATFORM_PLAN.md §3.3"
        ),
    )


def run_bench_test(
    prototype_plan: "TechnologyPrototypePlan",
    *,
    run_id: str | None = None,
) -> BenchTestPlan:
    """Plant und bewertet den Messlauf — eine `BenchTestResult` pro Prototyp.

    Was/Warum: Für jeden `TechnologyPrototypeSpec` in `prototype_plan.prototypes` wird ein
    Messplan abgeleitet, dessen Messdaten-Anforderungen/Erfolgs-/Abbruchkriterien aus den
    realen `anforderungen`/`risiken` des Prototyps stammen. Jede Bewertung ist explizit und
    ehrlich (nie `None`): solange kein realer Messlauf existiert, `geplant_nicht_ausgefuehrt`.

    Fehlerfälle / ehrliche Abstention:
    - Enthält der Plan **keine** Prototypen, wird KEIN Default-Prototyp erfunden, sondern
      eine leere Ergebnisliste mit ehrlicher Begründung zurückgegeben.
    - Trägt ein Prototyp keine Anforderungen, wird dessen Bewertung als
      `geplant_unvollstaendig_keine_kriterien` ausgewiesen (statt fabrizierter Kriterien).
    """
    traum = prototype_plan.source_traum

    if not prototype_plan.prototypes:
        # Ehrliche Abstention statt fabriziertem P0-Default: ohne Prototyp kein Messlauf.
        return BenchTestPlan(
            source_traum=traum,
            results=[],
            zusammenfassung=(
                "Kein Prototyp im Plan — es ist kein Messlauf planbar oder bewertbar. "
                "Ehrliche Abstention (keine stillen Defaults)."
            ),
            run_id=run_id,
            quelle="bench_test_runner (leere Abstention) + GENESIS_PLATFORM_PLAN.md §3.3",
        )

    results = [_bench_result_for(spec) for spec in prototype_plan.prototypes]

    bewertbar = sum(1 for r in results if r.ergebnis_bewertung == STATUS_GEPLANT_NICHT_AUSGEFUEHRT)
    zusammenfassung = (
        f"{len(results)} BenchTestResult(s) aus den Prototyp-Specs abgeleitet "
        f"(Messpläne + Erfolgs-/Abbruchkriterien direkt aus deren Anforderungen/Risiken). "
        f"{bewertbar}/{len(results)} vollständig planbar; alle Bewertungen sind ehrlich gesetzt "
        f"(noch kein realer Messlauf ausgeführt)."
    )

    return BenchTestPlan(
        source_traum=traum,
        results=results,
        zusammenfassung=zusammenfassung,
        run_id=run_id,
        quelle="bench_test_runner (input-abgeleitet) + technology_prototype_plan + GENESIS_PLATFORM_PLAN.md §3.3",
    )
