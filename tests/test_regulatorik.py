"""Tests für Regulatorik-Pipeline first stone (PLAN §4).

2 Tests:
- Jetpack path: EASA-like norms, high risks with human freigabe, full haftung. Naht to Elektriker/Techniker/Lern/DFM.
- Generic: honest gaps.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.regulatorik import map_to_regulatorik_spec, RegulatorikSpec


def test_regulatorik_jetpack_produces_norms_and_human_freigabe():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="reg-jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="reg-jet-001")
    spec = map_to_regulatorik_spec(concept, ing, run_id="reg-jet-001")

    assert isinstance(spec, RegulatorikSpec)
    assert spec.source_idea == idee
    assert len(spec.normen) >= 1
    assert any("EASA" in n.name or "ISO" in n.name for n in spec.normen)

    assert len(spec.risiken) >= 1
    assert any("tether" in r.name.lower() or "battery" in r.name.lower() for r in spec.risiken)
    assert any("human" in r.freigabe.lower() or "sign-off" in r.freigabe.lower() for r in spec.risiken)

    assert len(spec.warnhinweise) >= 1
    assert "WARNING" in " ".join(spec.warnhinweise).upper()
    assert "human" in spec.freigabe_prozess.lower() or "pilot" in spec.freigabe_prozess.lower()
    assert "liability" in spec.haftungsgrenzen.lower() or "operator" in spec.haftungsgrenzen.lower()

    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "tether" in spec.zusammenfassung.lower()


def test_regulatorik_generic_fallback_honest_gaps():
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="reg-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="reg-gen-001")
    spec = map_to_regulatorik_spec(concept, ing, run_id="reg-gen-001")

    assert len(spec.normen) >= 1
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")