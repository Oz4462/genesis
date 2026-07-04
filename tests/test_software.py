"""Tests für Software-/Firmware-Pipeline first stone (PLAN §4).

2 Tests:
- Jetpack path: concrete Embedded (Thrust + TetherSafety), API, OTA, testplan with fault injection. Naht to Elektriker/Techniker/Lern.
- Generic: honest gaps.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.software import map_to_software_spec, SoftwareSpec, UpdatePfad


def _spec_for(idee: str, run_id: str) -> SoftwareSpec:
    concept = map_to_system_concept(idee, run_id=run_id)
    ing = map_to_ingenieur_spec(concept, run_id=run_id)
    return map_to_software_spec(concept, ing, run_id=run_id)


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


# --- S-1: no fabricated provenance — no prior is consumed, and nothing claims it ---


def test_no_fabricated_prior_attribution_in_sources():
    """The `ingenieur` parameter is never read; quelle strings must not claim
    'Elektriker/Techniker/DFM/Lern' provenance. The honest label is: PLAN §4 canon
    template, no prior consumed (declared gap)."""
    spec = _spec_for("Ich will ein Jetpack bauen.", "soft-honest-001")
    all_quellen = [spec.quelle or ""] + \
        [e.quelle or "" for e in spec.embedded_components] + \
        [a.quelle or "" for a in spec.apis] + [spec.update_pfad.quelle or ""]
    for fach in ("Elektriker", "Techniker", "DFM", "Lern"):
        assert not any(fach in q for q in all_quellen), f"fabrizierte Herkunft: {fach}"
    assert "kein Prior konsumiert" in (spec.quelle or "")


def test_update_pfad_is_a_dataclass_not_a_tuple():
    """Latent bug: a trailing comma made the jetpack update path a 1-tuple."""
    spec = _spec_for("Ich will ein Jetpack bauen.", "soft-tuple-001")
    assert isinstance(spec.update_pfad, UpdatePfad)


# --- S-2: word-boundary trigger — 'Ausflug'/'Flughafen' are not flight devices -----


def test_ausflug_and_flughafen_do_not_trigger_the_jetpack_canon():
    for idee, rid in (("Ein Planer für den Ausflug ins Grüne.", "soft-trig-001"),
                      ("Ein Gepäckband für den Flughafen.", "soft-trig-002")):
        spec = _spec_for(idee, rid)
        assert not any("ThrustController" in e.name for e in spec.embedded_components), idee
        assert "Generic" in spec.zusammenfassung or "Lücke" in spec.zusammenfassung


def test_standalone_flug_and_fluggeraet_still_trigger():
    for idee, rid in (("Ein Gerät für den sicheren Flug über Wasser.", "soft-trig-003"),
                      ("Ein Fluggerät für eine Person.", "soft-trig-004")):
        spec = _spec_for(idee, rid)
        assert any("ThrustController" in e.name for e in spec.embedded_components), idee


# --- S-3: the jetpack canon declares its gap — no prior-derived detail --------------


def test_jetpack_path_declares_canon_assumption_gap():
    spec = _spec_for("Ich will ein Jetpack bauen.", "soft-gap-001")
    assert "Kanon-Annahme" in spec.zusammenfassung
    assert "aus keinem Prior abgeleitet" in spec.zusammenfassung