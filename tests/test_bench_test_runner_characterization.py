"""Characterization + depth-audit tests für bench_test_runner (achter Grenzverschiebungs-Stein).

Siehe GENESIS_PLATFORM_PLAN.md §3.3 und docs/audit/DEPTH_AUDIT_bench_test_runner.md.

Diese Tests pinnen das ehrliche Verhalten fest und FALLEN auf der alten Facade durch:
- die Facade ignorierte `prototype_plan.prototypes` (hartkodiertes 1-/2-Item-Ergebnis per
  Substring auf `source_traum`) → hier wird bewiesen, dass die Ergebnisse je Prototyp und
  aus dessen realen `anforderungen`/`risiken` abgeleitet sind;
- die Facade ließ `ergebnis_bewertung` immer `None` → hier wird bewiesen, dass jede
  Bewertung explizit und ehrlich gesetzt ist (nie `None`).
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, strategies as st

from gen.grenzverschiebung.technology_builder import (
    TechnologyPrototypePlan,
    TechnologyPrototypeSpec,
    build_technology_prototype,
)
from gen.grenzverschiebung.technology_roadmapper import build_technology_roadmap
from gen.grenzverschiebung.teststand_architect import build_test_stand
from gen.grenzverschiebung.milestone_builder import build_milestone_ladder
from gen.grenzverschiebung.capability_gap_analyzer import analyze_capability_gaps
from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.bench_test_runner import (
    BenchTestPlan,
    STATUS_GEPLANT_NICHT_AUSGEFUEHRT,
    STATUS_GEPLANT_UNVOLLSTAENDIG,
    run_bench_test,
)


def _spec(
    name: str = "PX — Test-Prototyp",
    *,
    anforderungen: list[str] | None = None,
    risiken: list[str] | None = None,
    ziel: str = "Zieltechnologie X",
) -> TechnologyPrototypeSpec:
    """Minimaler, voll kontrollierter Prototyp zum Treiben der Ableitungs-Logik."""
    return TechnologyPrototypeSpec(
        name=name,
        beschreibung=f"Beschreibung von {name}",
        ziel_technologie=ziel,
        anforderungen=anforderungen if anforderungen is not None else ["Anf-A ≥ 1", "Anf-B < 2"],
        test_stand_tie_in="T0 — Test-Stand",
        risiken=risiken if risiken is not None else ["Risiko-R"],
        grober_zeitplan="2 Wochen",
        quelle="unit-test",
    )


def _plan(*specs: TechnologyPrototypeSpec, traum: str = "irgendeine Idee ohne Jetpack") -> TechnologyPrototypePlan:
    return TechnologyPrototypePlan(
        source_traum=traum,
        prototypes=list(specs),
        zusammenfassung="test-plan",
        run_id="bench-char-001",
        quelle="unit-test",
    )


# ---------------------------------------------------------------------------
# 1. Anti-Facade: ein Ergebnis pro Prototyp (die Facade lieferte fix 1 oder 2)
# ---------------------------------------------------------------------------


def test_one_result_per_prototype_proves_prototypes_are_consumed():
    """Drei Prototypen → drei Ergebnisse. Die alte Facade ignorierte die Liste und lieferte fix 2."""
    plan = _plan(_spec("P-eins"), _spec("P-zwei"), _spec("P-drei"))
    bench = run_bench_test(plan)

    assert len(bench.results) == 3
    assert [r.prototype_name for r in bench.results] == ["P-eins", "P-zwei", "P-drei"]


def test_result_count_tracks_input_count():
    """Output-Kardinalität folgt der Eingabe — beweist, dass `.prototypes` wirklich konsumiert wird."""
    for n in (1, 2, 4, 7):
        specs = [_spec(f"P{i}") for i in range(n)]
        bench = run_bench_test(_plan(*specs))
        assert len(bench.results) == n


# ---------------------------------------------------------------------------
# 2. Anti-Facade: Kriterien sind aus anforderungen/risiken ABGELEITET
# ---------------------------------------------------------------------------


def test_messdaten_and_erfolg_derived_from_anforderungen():
    """Messdaten-Anforderungen und Erfolgskriterien enthalten den realen Anforderungs-Text."""
    spec = _spec(anforderungen=["Energiedichte ≥ 300 Wh/kg", "Gewicht < 8 kg"], risiken=[])
    bench = run_bench_test(_plan(spec))
    r = bench.results[0]

    # je Anforderung genau ein Messdaten- und ein Erfolgs-Eintrag, der den Text trägt
    assert len(r.messdaten_anforderungen) == 2
    assert any("Energiedichte ≥ 300 Wh/kg" in m for m in r.messdaten_anforderungen)
    assert any("Gewicht < 8 kg" in m for m in r.messdaten_anforderungen)
    assert len(r.erfolgskriterien) == 2
    assert any("Energiedichte ≥ 300 Wh/kg" in e for e in r.erfolgskriterien)


def test_abbruchkriterien_derived_from_risiken_plus_universal_stop():
    """Jedes Risiko wird zu einem Abbruchkriterium; zusätzlich gibt es ein universelles Sicherheits-Stopp."""
    spec = _spec(risiken=["Thermal Runaway", "Cross-Talk"])
    bench = run_bench_test(_plan(spec))
    r = bench.results[0]

    assert any("Thermal Runaway" in a for a in r.abbruchkriterien)
    assert any("Cross-Talk" in a for a in r.abbruchkriterien)
    # universelles Stopp ist immer dabei → auch ein risiko-armer Prototyp hat einen Stopp
    assert len(r.abbruchkriterien) == 3


def test_changing_an_input_anforderung_changes_the_output():
    """Verändert man NUR eine Anforderung, ändert sich der abgeleitete Messplan — kein Konstant-Stub."""
    base = _spec(anforderungen=["A-original"])
    mutated = replace(base, anforderungen=["A-anders"])

    r_base = run_bench_test(_plan(base)).results[0]
    r_mut = run_bench_test(_plan(mutated)).results[0]

    assert r_base.messdaten_anforderungen != r_mut.messdaten_anforderungen
    assert any("A-original" in m for m in r_base.messdaten_anforderungen)
    assert any("A-anders" in m for m in r_mut.messdaten_anforderungen)


# ---------------------------------------------------------------------------
# 3. Anti-Facade: ergebnis_bewertung ist NIE None (die Facade ließ es immer None)
# ---------------------------------------------------------------------------


def test_every_result_has_non_none_honest_bewertung():
    """Jede BenchTestResult trägt eine explizite, ehrliche Bewertung — niemals None."""
    plan = _plan(_spec("P-a"), _spec("P-b", anforderungen=[]))
    bench = run_bench_test(plan)

    for r in bench.results:
        assert r.ergebnis_bewertung is not None
        assert r.ergebnis_bewertung != ""
        assert r.bewertung_begruendung  # ehrliche Begründung vorhanden


def test_prototype_with_anforderungen_is_geplant_not_executed():
    """Prototyp mit Anforderungen → vollständig planbar, Status 'geplant_nicht_ausgefuehrt'."""
    bench = run_bench_test(_plan(_spec(anforderungen=["A1"])))
    assert bench.results[0].ergebnis_bewertung == STATUS_GEPLANT_NICHT_AUSGEFUEHRT


def test_prototype_without_anforderungen_is_flagged_incomplete():
    """Prototyp ohne Anforderungen → kein Erfolgskriterium ableitbar → ehrlich 'unvollstaendig'."""
    bench = run_bench_test(_plan(_spec(anforderungen=[])))
    r = bench.results[0]
    assert r.ergebnis_bewertung == STATUS_GEPLANT_UNVOLLSTAENDIG
    assert r.erfolgskriterien == []  # nichts erfunden
    # selbst hier bleibt das universelle Sicherheits-Stopp erhalten
    assert any("Sicherheitsrisiko" in a for a in r.abbruchkriterien)


# ---------------------------------------------------------------------------
# 4. Ehrliche Abstention bei leerer Eingabe (Facade fabrizierte einen P0-Default)
# ---------------------------------------------------------------------------


def test_empty_plan_abstains_instead_of_fabricating():
    """Kein Prototyp → leere Ergebnisliste + ehrliche Begründung, KEIN erfundener P0-Default."""
    bench = run_bench_test(_plan(traum="leere idee"))
    assert isinstance(bench, BenchTestPlan)
    assert bench.results == []
    assert "kein messlauf" in bench.zusammenfassung.lower()


# ---------------------------------------------------------------------------
# 5. Jetpack-Regression: die reiche Signal-Quelle bleibt erhalten — jetzt input-derived
# ---------------------------------------------------------------------------


def test_jetpack_rich_content_is_preserved_and_input_derived():
    """Über die echte Pipeline trägt der Jetpack-Plan reiche Prototypen → reiche, ABGELEITETE Pläne."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="bench-jp-001")
    gaps = analyze_capability_gaps(front, run_id="bench-jp-001")
    ladder = build_milestone_ladder(front, gaps, run_id="bench-jp-001")
    stand = build_test_stand(ladder, run_id="bench-jp-001")
    roadmap = build_technology_roadmap(stand, run_id="bench-jp-001")
    proto_plan = build_technology_prototype(roadmap, run_id="bench-jp-001")
    bench = run_bench_test(proto_plan, run_id="bench-jp-001")

    # eine BenchTestResult pro echtem Jetpack-Prototyp
    assert len(bench.results) == len(proto_plan.prototypes)
    assert len(bench.results) >= 1

    # die reichen Energiedichte-Anforderungen erscheinen — aber abgeleitet aus dem Input,
    # nicht hartkodiert: jede Anforderung des Prototyps steckt im Messplan.
    for spec, result in zip(proto_plan.prototypes, bench.results):
        assert result.prototype_name == spec.name
        for anf in spec.anforderungen:
            assert any(anf in m for m in result.messdaten_anforderungen)
        assert result.ergebnis_bewertung is not None


# ---------------------------------------------------------------------------
# 6. Property-based: Invarianten über beliebige Prototyp-Listen
# ---------------------------------------------------------------------------

_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=20)


@given(
    names=st.lists(_text, min_size=1, max_size=6, unique=True),
    anforderungen=st.lists(_text, min_size=0, max_size=4),
    risiken=st.lists(_text, min_size=0, max_size=4),
)
def test_property_one_result_per_proto_and_never_none_bewertung(names, anforderungen, risiken):
    """Invariante: |results| == |prototypes|, Reihenfolge erhalten, Bewertung nie None,
    und je Anforderung genau ein Messdaten-/Erfolgs-Eintrag (Ableitung ist total)."""
    specs = [_spec(n, anforderungen=list(anforderungen), risiken=list(risiken)) for n in names]
    bench = run_bench_test(_plan(*specs))

    assert len(bench.results) == len(specs)
    assert [r.prototype_name for r in bench.results] == names
    for r in bench.results:
        assert r.ergebnis_bewertung is not None
        assert len(r.messdaten_anforderungen) == len(anforderungen)
        assert len(r.erfolgskriterien) == len(anforderungen)
        # Abbruch = je Risiko ein Eintrag + 1 universelles Stopp
        assert len(r.abbruchkriterien) == len(risiken) + 1


@given(n=st.integers(min_value=0, max_value=8))
def test_property_empty_plan_always_abstains(n):
    """Mit n Prototypen kommen n Ergebnisse; bei n==0 ehrliche leere Abstention."""
    specs = [_spec(f"P{i}") for i in range(n)]
    bench = run_bench_test(_plan(*specs))
    assert len(bench.results) == n
    if n == 0:
        assert bench.results == []
