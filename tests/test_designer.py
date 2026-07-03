"""Tests für Designer-Pipeline first stone (PLAN §4.6).

2 Tests:
- Jetpack path: concrete Ergonomie, Form-Entscheidungen (markiert), Bedien-Szenarien mit Missbrauch (Naht zu prior Steinen).
- Generic: ehrliche Lücken.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.designer import map_to_designer_spec, DesignerSpec


def test_designer_jetpack_produces_ergonomie_and_marked_decisions():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="designer-jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="designer-jet-001")
    spec = map_to_designer_spec(concept, ing, run_id="designer-jet-001")

    assert isinstance(spec, DesignerSpec)
    assert spec.source_idea == idee
    assert len(spec.ergonomie_anforderungen) >= 1
    assert any("Harness" in e.name or "Haptik" in e.name for e in spec.ergonomie_anforderungen)
    assert any(e.trade_off for e in spec.ergonomie_anforderungen)

    assert len(spec.form_entscheidungen) >= 1
    assert any(f.markiert_als == "DECISION" for f in spec.form_entscheidungen)
    assert any("Sichtbare" in f.name or "Kompakte" in f.name for f in spec.form_entscheidungen)

    assert len(spec.bedien_szenarien) >= 2
    assert any("Emergency" in b.name or "Missbrauch" in b.name for b in spec.bedien_szenarien)

    assert "§4.6" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "Harness" in spec.zusammenfassung


def test_designer_generic_fallback_honest_gaps():
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="designer-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="designer-gen-001")
    spec = map_to_designer_spec(concept, ing, run_id="designer-gen-001")

    assert len(spec.ergonomie_anforderungen) >= 1
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    assert len(spec.form_entscheidungen) >= 1
    assert len(spec.bedien_szenarien) >= 1
    assert "§4.6" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")