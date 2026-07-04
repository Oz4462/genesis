"""Tests für den gemeinsamen Wortgrenzen-Flug-Trigger der Fach-Pipelines (Schritt 9, #3–#6, #11).

Befund: ``"flug" in idee_lower`` matchte "Ausflug"/"Flughafen" und feuerte den vollen
Jetpack-Kanon — bei der Regulatorik-Pipeline inklusive EASA-Zuordnung und Haftungstexten
(rechts-/sicherheitsrelevant). Fix: EIN gemeinsamer Helfer ``pipelines._triggers.is_flight_idea``
(Wortgrenzen-Regex, exakt das S-2-Muster aus software.py) in allen 6 Stellen; architekt härtet
"fliegen" separat mit ``has_fliegen_word``.
"""

from gen.pipelines._triggers import is_flight_idea, has_fliegen_word
from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.designer import map_to_designer_spec
from gen.pipelines.elektriker import map_to_elektriker_spec
from gen.pipelines.fertigungs import map_to_fertigungs_spec
from gen.pipelines.regulatorik import map_to_regulatorik_spec
from gen.pipelines.wirtschaft import map_to_wirtschaft_spec


def _concept_and_ingenieur(idee: str, run_id: str):
    concept = map_to_system_concept(idee, run_id=run_id)
    return concept, map_to_ingenieur_spec(concept, run_id=run_id)


# --- Helfer selbst: Wortgrenzen, keine Substrings -----------------------------------


def test_is_flight_idea_matches_flight_terms_on_word_boundaries():
    for text in (
        "Ich will ein Jetpack bauen.",
        "Ein Gerät für den sicheren Flug über Wasser.",
        "Ein Fluggerät für eine Person.",
        "Ein FLUGZEUG im Kleinformat.",
        "fluggeraet ohne Umlaut",
    ):
        assert is_flight_idea(text), text


def test_is_flight_idea_rejects_ausflug_and_flughafen_substrings():
    for text in (
        "Ein Planer für den Ausflug ins Grüne.",
        "Ein Gepäckband für den Flughafen.",
        "Ein Ausflugsboot für Familien.",
        "",
    ):
        assert not is_flight_idea(text), text


def test_has_fliegen_word_boundary():
    assert has_fliegen_word("Menschen sollen sicher fliegen können.")
    assert not has_fliegen_word("Menschen, die überfliegende Vögel beobachten.")
    assert not has_fliegen_word("")


# --- #3 Regulatorik: „Ausflug" darf KEINE EASA-/Haftungs-Kanon-Antwort auslösen ------


def test_regulatorik_ausflug_does_not_trigger_easa_canon():
    concept, ing = _concept_and_ingenieur("Ein Planer für den Ausflug ins Grüne.", "trig-reg-001")
    spec = map_to_regulatorik_spec(concept, ing, run_id="trig-reg-001")
    assert not any("EASA" in n.name for n in spec.normen)
    assert not any("tether" in r.name.lower() for r in spec.risiken)
    assert "Generic" in spec.zusammenfassung or "Lücke" in spec.zusammenfassung


# --- #4 Designer -------------------------------------------------------------------


def test_designer_flughafen_does_not_trigger_jetpack_canon():
    concept, ing = _concept_and_ingenieur("Ein Gepäckband für den Flughafen.", "trig-des-001")
    spec = map_to_designer_spec(concept, ing, run_id="trig-des-001")
    assert not any("Harness" in e.name for e in spec.ergonomie_anforderungen)
    assert "Generic" in spec.zusammenfassung or "Lücke" in spec.zusammenfassung


# --- #5 Elektriker -----------------------------------------------------------------


def test_elektriker_ausflug_does_not_trigger_48v_jetpack_canon():
    concept, ing = _concept_and_ingenieur("Ein Planer für den Ausflug ins Grüne.", "trig-ele-001")
    spec = map_to_elektriker_spec(concept, ing, run_id="trig-ele-001")
    assert not any(s.name == "Main Drive" and s.spannung_v == 48.0 for s in spec.stromkreise)
    assert spec.leistungs_budget.gesamt_w < 1300.0


# --- #6 Wirtschaft -----------------------------------------------------------------


def test_wirtschaft_flughafen_does_not_trigger_jetpack_canon():
    concept, ing = _concept_and_ingenieur("Ein Gepäckband für den Flughafen.", "trig-wir-001")
    spec = map_to_wirtschaft_spec(concept, ing, run_id="trig-wir-001")
    assert "experimental" not in spec.markt.zielgruppe.lower()
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung


# --- fertigungs.py:125 (gleicher Bug) ------------------------------------------------


def test_fertigungs_ausflug_does_not_trigger_jetpack_canon():
    concept, ing = _concept_and_ingenieur("Ein Planer für den Ausflug ins Grüne.", "trig-fer-001")
    spec = map_to_fertigungs_spec(concept, ing, run_id="trig-fer-001")
    assert "Jetpack" not in spec.zusammenfassung
    assert "Generisch" in spec.zusammenfassung or "Lücke" in spec.zusammenfassung


# --- Positivpfad bleibt: echtes Fluggerät feuert den Kanon weiterhin -----------------


def test_real_flight_device_still_triggers_canon_in_all_five():
    idee = "Ein Fluggerät für eine Person."
    concept, ing = _concept_and_ingenieur(idee, "trig-pos-001")
    reg = map_to_regulatorik_spec(concept, ing, run_id="trig-pos-001")
    assert any("EASA" in n.name for n in reg.normen)
    des = map_to_designer_spec(concept, ing, run_id="trig-pos-001")
    assert any("Harness" in e.name for e in des.ergonomie_anforderungen)
    ele = map_to_elektriker_spec(concept, ing, run_id="trig-pos-001")
    assert any(s.name == "Main Drive" for s in ele.stromkreise)
    wir = map_to_wirtschaft_spec(concept, ing, run_id="trig-pos-001")
    assert "experimental" in wir.markt.zielgruppe.lower()
    fer = map_to_fertigungs_spec(concept, ing, run_id="trig-pos-001")
    assert "Jetpack" in fer.zusammenfassung


# --- #11 Architekt: „fliegen" nur als ganzes Wort ------------------------------------


def test_architekt_ueberfliegende_substring_does_not_trigger_jetpack_concept():
    # alt: "mensch" in idee und "fliegen" in idee (Substring in "überfliegende") → Jetpack-Kanon
    concept = map_to_system_concept(
        "Ein Boot für Menschen, die überfliegende Vögel beobachten.", run_id="trig-arc-001"
    )
    assert "minimal" in concept.zusammenfassung.lower()


def test_architekt_mensch_plus_fliegen_word_still_triggers():
    concept = map_to_system_concept(
        "Ich will, dass Menschen sicher fliegen.", run_id="trig-arc-002"
    )
    assert len(concept.main_assemblies) >= 4
