"""Teilprojekt 2 (Struktur-Härtung): zyklische Lasten am Humanoiden.

Die vier existierenden Validatoren (fatigue/Goodman, notch_fatigue, buckling,
resonance) feuern jetzt über Measurand-Tagging auf beide Humanoiden — der
Oberschenkel als wechselnd gebogener Träger (Gang, R = -1), das Hüftlager-Loch
als Kerbe, der Unterschenkel als Druckstab und die Struktur-Eigenmode gegen die
2. Gang-Harmonische. Keine neuen Validatoren, keine neuen Recipe-Einträge.
"""

import math
from dataclasses import replace

from gen.competitive_humanoid import FLAGSHIP, PRINTED, build_humanoid
from gen.physics_selection import select_physics_checks
from gen.physics_validation import run_physics_checks
from gen.pipeline import assess_specification
from gen.seams import domains_present, required_seam_pairs

#: Die vier TP2-Checks, wie die existierenden Recipes sie benennen.
STRUCTURE_CHECK_NAMES = {"fatigue (Goodman)", "notch fatigue", "column buckling", "resonance"}


def _quantity(spec, qid):
    m = {q.id: q for q in spec.quantities}
    assert qid in m, f"{qid} fehlt in Spec {spec.run_id}"
    return m[qid]


def _run_named_check(spec, name):
    """Select-and-run exactly one named check; asserts it was selected (no gap)."""
    checks, gaps = select_physics_checks(spec)
    assert not any(name.split(" (")[0] in gap for gap in gaps), gaps
    matches = [c for c in checks if c.name == name]
    assert len(matches) == 1, f"{name!r} nicht (genau einmal) selektiert: {sorted(c.name for c in checks)}"
    return run_physics_checks(matches)[0]


# --- 1. Alle 4 Checks erscheinen in physics_checks BEIDER Humanoiden und bestehen ---

def test_structure_checks_fire_and_pass_for_both_humanoids():
    for cfg in (PRINTED, FLAGSHIP):
        a = assess_specification(build_humanoid(cfg))
        names = {c.name for c in a.physics_checks}
        assert STRUCTURE_CHECK_NAMES <= names, names
        assert a.overall == "physics_verified", (cfg.run_id, a.overall, a.physics_gate.failures)
        # und jeder der vier läuft einzeln mit ok=True
        spec = build_humanoid(cfg)
        for name in STRUCTURE_CHECK_NAMES:
            r = _run_named_check(spec, name)
            assert r["status"] == "ran" and r["ok"] is True, (cfg.run_id, name, r)


# --- 2. Negativ Fatigue: dünner Oberschenkel => sigma_nom hoch => Goodman fällt durch ---

def test_thin_thigh_fails_fatigue():
    thin = replace(PRINTED, run_id="printed_thin_thigh", thigh_thick_mm=8.0)
    spec = build_humanoid(thin)
    r = _run_named_check(spec, "fatigue (Goodman)")
    assert r["status"] == "ran" and r["ok"] is False, r
    assert r["result"]["safety_factor"] < 1.0
    a = assess_specification(spec)
    assert a.overall != "physics_verified"


# --- 3. Negativ Knickung: langer dünner Unterschenkel => Euler fällt durch ---

def test_slender_shank_fails_buckling():
    slender = replace(PRINTED, run_id="printed_slender_shank",
                      shank_len_mm=400.0, shank_thick_mm=4.0)
    spec = build_humanoid(slender)
    r = _run_named_check(spec, "column buckling")
    assert r["status"] == "ran" and r["ok"] is False, r
    assert r["result"]["governs"] == "buckling"
    assert r["result"]["safety_factor"] < 1.0
    a = assess_specification(spec)
    assert a.overall != "physics_verified"


# --- 4. Negativ Resonanz: Schrittfrequenz nahe der Eigenfrequenz => resonance fällt durch ---

def test_step_frequency_near_first_mode_fails_resonance():
    spec_ok = build_humanoid(PRINTED)
    f1 = _quantity(spec_ok, "q_f1").value
    # Anregung (2. Harmonische) direkt auf die Eigenmode legen: step_f = f1 / 2
    resonant = replace(PRINTED, run_id="printed_resonant_gait", step_frequency_hz=f1 / 2.0)
    spec = build_humanoid(resonant)
    r = _run_named_check(spec, "resonance")
    assert r["status"] == "ran" and r["ok"] is False, r
    assert r["result"]["ratio"] < r["result"]["min_separation_factor"]
    a = assess_specification(spec)
    assert a.overall != "physics_verified"


# --- 5. Formel-Konsistenz: I/A/f1-DERIVED-Werte gegen unabhängige Handrechnung ---

def test_derived_section_and_frequency_values_match_hand_calculation():
    for cfg in (PRINTED, FLAGSHIP):
        spec = build_humanoid(cfg)
        # Unterschenkel-Querschnitt (Knick-Stab): I = b*h^3/12, A = b*h (mm-Einheiten)
        b_s, h_s = cfg.shank_width_mm, cfg.shank_thick_mm
        assert math.isclose(_quantity(spec, "q_I_shank").value, b_s * h_s**3 / 12.0, rel_tol=1e-12)
        assert math.isclose(_quantity(spec, "q_A_shank").value, b_s * h_s, rel_tol=1e-12)
        # Oberschenkel-Querschnitt (Eigenmode-Träger)
        b_t, h_t = cfg.thigh_width_mm, cfg.thigh_thick_mm
        assert math.isclose(_quantity(spec, "q_I_thigh").value, b_t * h_t**3 / 12.0, rel_tol=1e-12)
        assert math.isclose(_quantity(spec, "q_A_thigh").value, b_t * h_t, rel_tol=1e-12)
        # f1 unabhängig in SI nachgerechnet: (1.875^2/2pi)*sqrt(E*I/(rho*A*L^4))
        e_pa = cfg.e_modulus_mpa * 1e6
        i_m4 = (b_t / 1e3) * (h_t / 1e3) ** 3 / 12.0
        a_m2 = (b_t / 1e3) * (h_t / 1e3)
        rho = 1240.0                       # q_density 0.00124 g/mm^3 == 1240 kg/m^3
        length = 0.180                     # q_thigh_x 180 mm
        f1_si = (1.875**2 / (2.0 * math.pi)) * math.sqrt(e_pa * i_m4 / (rho * a_m2 * length**4))
        assert math.isclose(_quantity(spec, "q_f1").value, f1_si, rel_tol=1e-9), cfg.run_id
        # Anregung = 2. Gang-Harmonische
        assert math.isclose(_quantity(spec, "q_excitation").value, 2.0 * cfg.step_frequency_hz,
                            rel_tol=1e-12)
        # Dauerfestigkeits-Basis (DECISION 0.30 * UTS) konsistent
        assert math.isclose(_quantity(spec, "q_endurance_limit").value,
                            cfg.endurance_limit_basis * cfg.material_strength_mpa, rel_tol=1e-12)


# --- 6. Gap-Freiheit + keine neuen Domains / Pflicht-Seam-Paare (Repro-Baseline) ---

def test_no_new_gaps_domains_or_required_seam_pairs():
    for cfg in (PRINTED, FLAGSHIP):
        spec = build_humanoid(cfg)
        checks, gaps = select_physics_checks(spec)
        assert gaps == [], f"Gaps: {gaps}"
        assert STRUCTURE_CHECK_NAMES <= {c.name for c in checks}
        # Repro-Baseline vor TP2 (2026-07-04): genau diese 4 Domains, genau diese 2 Paare.
        assert {d.value for d in domains_present(spec)} == {
            "mechanical", "thermal", "electrical", "cost"}
        pairs = {tuple(sorted((a.value, b.value))) for a, b in required_seam_pairs(spec)}
        assert pairs == {("electrical", "thermal"), ("mechanical", "thermal")}
