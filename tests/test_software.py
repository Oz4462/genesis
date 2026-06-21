"""Tests für Software-/Firmware-Pipeline first stone (PLAN §4).

2 Tests:
- Jetpack path: concrete Embedded (Thrust + TetherSafety), API, OTA, testplan with fault injection. Naht to Elektriker/Techniker/Lern.
- Generic: honest gaps.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.software import map_to_software_spec, SoftwareSpec


def test_software_jetpack_produces_embedded_and_fault_tests():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="soft-jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="soft-jet-001")
    spec = map_to_software_spec(concept, ing, run_id="soft-jet-001")

    assert isinstance(spec, SoftwareSpec)
    assert spec.source_idea == idee
    assert len(spec.embedded_components) >= 1
    assert any("ThrustController" in e.name or "TetherSafety" in e.name for e in spec.embedded_components)
    assert any("overtemp" in str(e.fehler_zustaende) for e in spec.embedded_components)

    assert len(spec.apis) >= 1
    assert any("GroundTelemetry" in a.name for a in spec.apis)

    assert "rollback" in str(spec.update_pfad).lower() or "A/B" in str(spec.update_pfad)
    assert len(spec.testplan) >= 3
    assert any("fault injection" in t.lower() or "tether loss" in t.lower() for t in spec.testplan)

    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "Thrust" in spec.zusammenfassung


def test_software_generic_fallback_honest_gaps():
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="soft-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="soft-gen-001")
    spec = map_to_software_spec(concept, ing, run_id="soft-gen-001")

    assert len(spec.embedded_components) >= 1
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    assert len(spec.testplan) >= 1
    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")