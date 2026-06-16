"""Tests für Elektriker-/Elektronik-Pipeline (PLAN §4.5 full depth).

Original 2 tests (high-level first-stone behavior) remain unchanged and must pass.
Additional tests cover the deep layer:
- Netlist present + compatible with gate_erc (no wiring defects).
- MNA simulation (via circuit.py) produces voltages/currents consistent with budget.
- CAD integration artifacts (placements + harness) for assembly co-design.
- Falsification experiments generated (δ⁺ / reality seam).
- electronic_bom items are domain=ELECTRONIC.
- schaltplan_text + provenance on rich fields.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.elektriker import map_to_elektriker_spec, ElektronikSpec

# For deep-layer assertions (netlist, erc, sim, bom domain)
try:
    from gen.core.state import BomDomain, Netlist
    from gen.verification.gates import gate_erc
    from gen.core.state import RunState, Question, Specification
except Exception:  # pragma: no cover
    BomDomain = Netlist = gate_erc = RunState = Question = Specification = None  # type: ignore


def test_elektriker_jetpack_produces_concrete_power_and_safety():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="elektro-jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="elektro-jet-001")
    spec = map_to_elektriker_spec(concept, ing, run_id="elektro-jet-001")

    assert isinstance(spec, ElektronikSpec)
    assert spec.source_idea == idee
    assert len(spec.stromkreise) >= 2
    # Concrete for Jetpack
    main = next((s for s in spec.stromkreise if "Main Drive" in s.name or "Drive" in s.name), None)
    assert main is not None
    assert main.spannung_v >= 24.0
    assert main.leistung_w > 500
    assert "cutoff" in main.schutz.lower() or "fuse" in main.schutz.lower()

    assert spec.leistungs_budget.gesamt_w > 1000
    assert spec.leistungs_budget.reserve_prozent >= 5

    assert len(spec.emv_checks) >= 1
    assert any("shield" in e.massnahme.lower() or "emi" in e.massnahme.lower() for e in spec.emv_checks)

    assert len(spec.sicherheits_anforderungen) >= 1
    assert any("emergency" in s.name.lower() or "cut" in s.massnahme.lower() for s in spec.sicherheits_anforderungen)

    assert len(spec.pcb_hinweise) >= 1
    assert len(spec.pruefplan) >= 2

    assert "§4.5" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "Thrust" in spec.zusammenfassung


def test_elektriker_generic_fallback_honest_gaps():
    idee = "Ein portables Messgerät für extreme Umgebungen."
    concept = map_to_system_concept(idee, run_id="elektro-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="elektro-gen-001")
    spec = map_to_elektriker_spec(concept, ing, run_id="elektro-gen-001")

    assert len(spec.stromkreise) >= 1
    # Generisch → ehrliche Lücken
    assert "Lücke" in spec.zusammenfassung or "Minimal" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    # Aber immer noch Struktur + Gate-Elemente
    assert spec.leistungs_budget.reserve_prozent > 0
    assert len(spec.sicherheits_anforderungen) >= 1
    assert "§4.5" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")


# --- deep layer tests (full §4.5) --------------------------------------------

def test_elektriker_jetpack_produces_rich_netlist_and_erc_compatible():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="elektro-jet-rich-001")
    ing = map_to_ingenieur_spec(concept, run_id="elektro-jet-rich-001")
    spec = map_to_elektriker_spec(concept, ing, run_id="elektro-jet-rich-001")

    # Netlist must be present and sound (gate_erc must pass)
    assert spec.netlist is not None
    assert isinstance(spec.netlist, Netlist) or hasattr(spec.netlist, "pins")
    # Build a minimal RunState wrapper exactly as gate_erc expects
    st = RunState(question=Question(raw="elektriker-erc", run_id="elektro-jet-rich-001"))
    st.specification = Specification(run_id="elektro-jet-rich-001", idea=idee, bom=spec.electronic_bom or [], netlist=spec.netlist)
    erc = gate_erc(st)
    assert erc.passed, [f"{f.code}: {f.detail}" for f in erc.failures]

    # electronic_bom items are ELECTRONIC domain
    if spec.electronic_bom:
        assert all(getattr(b, "domain", None) is BomDomain.ELECTRONIC for b in spec.electronic_bom)


def test_elektriker_jetpack_mna_simulation_matches_budget_and_produces_falsif():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="elektro-jet-sim-001")
    ing = map_to_ingenieur_spec(concept, run_id="elektro-jet-sim-001")
    spec = map_to_elektriker_spec(concept, ing, run_id="elektro-jet-sim-001")

    assert spec.simulation_result is not None
    sim = spec.simulation_result
    # At least one electrical DC case and one power budget case
    domains = {c.domain for c in sim.cases}
    assert "electrical_dc_op" in domains or "power_budget" in domains
    # Power delivered should be in the 1000+ W range for the Jetpack budget
    power_cases = [c for c in sim.cases if "power" in c.domain.lower() or "W" in c.predicted_unit]
    if power_cases:
        assert power_cases[0].predicted_value > 1000.0

    # Falsification experiments ready for reality.py
    assert len(spec.falsification_experiments) >= 1
    for exp in spec.falsification_experiments:
        assert "predicted_value" in exp and "predicted_unit" in exp
        assert "grounding" in exp or "quelle" in exp

    # provenance everywhere on rich artifacts
    assert "§4.5" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    if sim.provenance:
        assert "electronics" in sim.provenance.lower() or "mna" in sim.provenance.lower() or "circuit" in sim.provenance.lower()


def test_elektriker_jetpack_produces_cad_placements_and_harness():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="elektro-jet-cad-001")
    ing = map_to_ingenieur_spec(concept, run_id="elektro-jet-cad-001")
    spec = map_to_elektriker_spec(concept, ing, run_id="elektro-jet-cad-001")

    assert len(spec.placement_hints) >= 2  # at least battery + esc + dcdc etc.
    for p in spec.placement_hints:
        assert hasattr(p, "pos_mm") or "pos_mm" in p
        assert hasattr(p, "ref_des") or "ref_des" in p

    # Harness for distributed (tether) electronics
    if spec.harness is not None:
        segs = getattr(spec.harness, "segments", None)
        if segs is None and isinstance(spec.harness, dict):
            segs = spec.harness.get("segments", [])
        assert len(segs or []) >= 1

    # schaltplan_text and cad_integration present
    assert spec.schaltplan_text
    assert spec.cad_integration or (spec.placement_hints and spec.netlist)
