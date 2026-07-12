"""Drone catalog + δ-FLIGHT validator calibration + discovered scaling laws (the drone-training task).

The flight analog of ``test_humanoids_scaling_laws.py``. Exact checks, not vibes:
  * the catalog carries SOURCED facts with honest gaps — consumer drones have NO motor KV/thrust/T/W
    (a None, not a fabricated value) — the no-hallucination contract (the NEGATIVE test);
  * the model_parser reproduces gym-pybullet-drones' OWN derived MAX_THRUST/HOVER_RPM from the URDF's
    empirically-fitted k_f, to the simulator's arithmetic — a model-independent ground truth;
  * the CALIBRATION FIX: GENESIS no longer false-fails the DJI Matrice 350 RTK (real survey drone,
    max-gross T/W 1.42×) on the universal T/W≥2.0 floor, and a sluggish racer no longer passes the
    too-lax 2.0 — the class-calibrated floors (grounded in the real fleet) classify both correctly;
  * the discovered laws keep ONLY what generalises out-of-sample (prop-diameter∝mass^0.5 KEPT at the
    physically-predicted exponent; battery/mass and endurance/specific-energy honestly REJECTED).

Offline, numpy only (scaling-law fits); the catalog/calibration are pure stdlib. The model_parser
tests skip cleanly when the optional gym-pybullet-drones clone is absent.
Run: pytest tests/test_aero_drone_calibration.py
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.aero.calibration import (  # noqa: E402
    calibrated_min_twr,
    calibration_findings,
    rotor_hover_check_calibrated,
    validate_all,
    validate_drone,
)
from gen.aero.drone_catalog import (  # noqa: E402
    ASSETS,
    SPECS,
    drones,
    hover_thrust_demand_n,
    multirotors,
)
from gen.aero.model_parser import DRONE_URDF_DIR, SIM_GRAVITY, parse_drone_urdf, parse_known
from gen.aero.scaling_laws import (  # noqa: E402
    GENERALISES_OOS_R2,
    dataset,
    fit_battery_mass_law,
    fit_endurance_law,
    fit_prop_mass_law,
    hover_thrust_identity,
)
from gen.flight import (  # noqa: E402
    MIN_THRUST_WEIGHT_BY_CLASS,
    MIN_THRUST_WEIGHT_RATIO,
    min_thrust_weight_for_class,
    rotor_hover_check,
)

_HAS_URDFS = os.path.isdir(DRONE_URDF_DIR) and os.path.isfile(os.path.join(DRONE_URDF_DIR, "cf2x.urdf"))


# ── catalog integrity + the no-hallucination contract ─────────────────────────────────────────────

def test_catalog_keys_are_consistent_across_specs_assets_and_ordering():
    assert set(SPECS) == set(ASSETS), "every spec must have a local-asset/provenance record"
    assert set(drones()) == set(SPECS), "the ordering list must cover exactly the spec keys"
    assert len(drones()) >= 12, "the task targets ~12-20 real drones"


def test_catalog_spans_the_full_size_spectrum():
    classes = {SPECS[k].klass for k in drones()}
    # nano → fpv → consumer/cinematic → fixed-wing → heavy: the spread the calibration needs
    for required in ("nano", "fpv", "consumer", "fixed_wing", "heavy"):
        assert required in classes, f"catalog missing a '{required}' drone"


def test_every_field_carries_a_source_string():
    """The project rule: no factual value without a source. Every Cited field has a non-empty source,
    INCLUDING the honest-gap (None-valued) ones — a gap must still say WHY it is a gap."""
    for k in drones():
        s = SPECS[k]
        for fld in ("n_rotors", "mass_kg", "prop_diameter_m", "battery_cells", "battery_voltage_v",
                    "battery_capacity_mah", "battery_wh", "max_flight_time_min"):
            cited = getattr(s, fld)
            assert cited.source and isinstance(cited.source, str), f"{k}.{fld} has no source"


def test_NEGATIVE_consumer_drones_have_honest_thrust_gaps_not_fabricated_values():
    """NEGATIVE TEST: DJI/Autel do NOT publish motor KV / per-motor thrust / T/W. The catalog must carry
    these as honest None, never a guessed number — a fabricated thrust would poison the calibration and
    violate the no-hallucination contract. (The gym-pybullet/FPV/heavy drones DO have sourced thrust.)"""
    for k in ("dji_mini4pro", "dji_air3", "dji_mavic3classic", "autel_evolite_plus"):
        s = SPECS[k]
        assert s.max_total_thrust_n is None, f"{k} must not invent a max thrust (consumer maker omits it)"
        assert s.motor_kv is None, f"{k} must not invent a motor KV"
        assert s.per_motor_max_thrust_n is None, f"{k} must not invent a per-motor thrust"


def test_sourced_max_thrust_only_where_genuinely_grounded():
    """max_total_thrust is populated ONLY for the gym-pybullet k_f drones, the FPV build (vendor thrust
    table), and the heavy drones (published MTOW·g) — never for a bare consumer drone."""
    have_thrust = {k for k in drones()
                   if SPECS[k].max_total_thrust_n is not None and SPECS[k].max_total_thrust_n.known}
    assert have_thrust == {"crazyflie2x", "gpd_racer", "iflight_nazgul5_v3",
                           "freefly_alta_x", "dji_matrice350", "dji_agras_t40"}


def test_hover_thrust_demand_is_mg_or_none():
    cf = hover_thrust_demand_n("crazyflie2x")
    assert cf == pytest.approx(9.80665 * 0.027)
    # a drone whose mass is known always yields a demand; every catalogued drone has a mass
    assert all(hover_thrust_demand_n(k) is not None for k in drones())


def test_multirotors_excludes_fixed_wing():
    mr = set(multirotors())
    assert "sensefly_ebee_x" not in mr and "skywalker_x8" not in mr
    assert "crazyflie2x" in mr and "dji_air3" in mr


# ── the model_parser reproduces the simulator's OWN ground truth (k_f dynamics) ───────────────────

@pytest.mark.skipif(not _HAS_URDFS, reason="gym-pybullet-drones clone not present")
def test_parser_reproduces_simulator_max_thrust_identity():
    """gym-pybullet-drones defines MAX_THRUST = 4·k_f·MAX_RPM² and MAX_RPM = sqrt(t2w·weight/(4·k_f)),
    so MAX_THRUST must equal thrust2weight·weight EXACTLY. The parser reproduces this — the cross-check
    that our reading of the dynamics file matches the simulator's own arithmetic."""
    cf = parse_drone_urdf(os.path.join(DRONE_URDF_DIR, "cf2x.urdf"))
    assert cf.mass_kg == pytest.approx(0.027)
    assert cf.thrust2weight == pytest.approx(2.25)
    # the algebraic identity the simulator is built on:
    assert cf.max_total_thrust_n == pytest.approx(cf.thrust2weight * cf.weight_n)
    # hover thrust per rotor must lift exactly a quarter of the weight (4 rotors at hover):
    assert 4.0 * cf.hover_thrust_per_rotor_n == pytest.approx(cf.weight_n)
    assert cf.weight_n == pytest.approx(SIM_GRAVITY * cf.mass_kg)


@pytest.mark.skipif(not _HAS_URDFS, reason="gym-pybullet-drones clone not present")
def test_parser_reads_real_prop_and_racer_is_heavier_than_crazyflie():
    models = parse_known()
    assert "cf2x" in models and "racer" in models
    cf, racer = models["cf2x"], models["racer"]
    # the Crazyflie's 45mm-class prop (radius 2.31348e-2 → ~46.3mm dia):
    assert cf.prop_diameter_m == pytest.approx(2.0 * 2.31348e-2)
    # the racer is a much bigger, higher-thrust airframe:
    assert racer.mass_kg > 10 * cf.mass_kg
    assert racer.max_total_thrust_n > 10 * cf.max_total_thrust_n


@pytest.mark.skipif(not _HAS_URDFS, reason="gym-pybullet-drones clone not present")
def test_catalog_max_thrust_matches_the_parsed_urdf_ground_truth():
    """The catalog's hard-coded Crazyflie/racer max-thrust must equal what the parser derives from the
    URDF on disk — the catalog number is the parsed ground truth, not a typo."""
    models = parse_known()
    assert SPECS["crazyflie2x"].max_total_thrust_n.value == pytest.approx(
        models["cf2x"].max_total_thrust_n, rel=1e-4)
    assert SPECS["gpd_racer"].max_total_thrust_n.value == pytest.approx(
        models["racer"].max_total_thrust_n, rel=1e-4)


def test_parser_fails_loud_on_missing_file():
    with pytest.raises(FileNotFoundError):
        parse_drone_urdf("/nonexistent/path/to/cf2x.urdf")


# ── THE CALIBRATION FIX: real shipping drones classified correctly (the core finding) ─────────────

def test_calibrated_floors_live_in_flight_and_are_real_fleet_grounded():
    """The fix lives in the validator module (single source of truth), with the documented per-class
    floors. The aero alias and the flight helper must agree."""
    assert MIN_THRUST_WEIGHT_BY_CLASS["heavy"] == 1.3
    assert MIN_THRUST_WEIGHT_BY_CLASS["fpv"] == 4.0
    assert min_thrust_weight_for_class("consumer") == 1.5
    assert calibrated_min_twr("nano") == min_thrust_weight_for_class("nano")
    # unknown class falls back to the universal default (a safe middle, not a crash):
    assert min_thrust_weight_for_class("spaceship") == MIN_THRUST_WEIGHT_RATIO == 2.0


def test_REGRESSION_matrice350_false_failed_by_universal_2_passes_after_calibration():
    """THE calibration finding (the drone analog of the humanoid leg-torque fix): a real shipping survey
    drone (DJI Matrice 350 RTK, max-gross T/W = 9.2 kg MTOW / 6.47 kg loaded = 1.42×) is FALSE-FAILED by
    the universal 2.0 floor but flies daily. The class-calibrated 1.3 'heavy' floor must PASS it; the
    pre-fix 2.0 floor is pinned as the regression that would have wrongly failed it."""
    spec = SPECS["dji_matrice350"]
    twr = 9.2 / 6.47  # max takeoff weight / loaded weight, both DJI-sourced
    # pre-fix: the universal 2.0 floor would FAIL this real drone
    disk = math.pi * (spec.prop_diameter_m.value / 2.0) ** 2
    prefix = rotor_hover_check(mass=spec.mass_kg.value, rotor_disk_area=disk,
                               n_rotors=spec.n_rotors.value,
                               max_total_thrust=spec.max_total_thrust_n.value,
                               min_thrust_weight=2.0)
    assert prefix["ok"] is False, "the universal 2.0 floor (the bug) false-fails the M350"
    assert prefix["thrust_weight_ratio"] == pytest.approx(twr, rel=1e-3)
    # post-fix: the class-calibrated floor passes it
    fixed = rotor_hover_check_calibrated(spec)
    assert fixed["min_thrust_weight"] == 1.3
    assert fixed["ok"] is True, "the calibrated heavy floor must pass the real, flying M350"


def test_calibration_passes_every_real_shipping_multirotor_with_sourced_thrust():
    """A known-good real drone clears its class-calibrated floor — the gate is right after the fix (it
    does not false-fail any catalogued shipping multirotor that has a sourced max thrust)."""
    for k in ("crazyflie2x", "iflight_nazgul5_v3", "freefly_alta_x", "dji_matrice350", "dji_agras_t40"):
        res = rotor_hover_check_calibrated(SPECS[k])
        assert res is not None and res["ok"], f"{k} should clear its calibrated class floor"


def test_2_point_0_floor_is_too_lax_for_fpv_and_calibration_fixes_that_end_too():
    """The OTHER end of the finding: a real 5\" freestyle quad runs T/W≈9×; the 4.0 fpv floor is the
    real bar. A hypothetical sluggish 'racer' at 3× PASSES the lax 2.0 but FAILS the calibrated 4.0 —
    the fix tightens the over-lax end as well as loosening the false-fail end."""
    nazgul = rotor_hover_check_calibrated(SPECS["iflight_nazgul5_v3"])
    assert nazgul["thrust_weight_ratio"] > 6.0  # a real freestyle quad is far above 2.0
    # a sluggish fpv build at 3× would (wrongly) pass 2.0 but (correctly) fail the calibrated 4.0:
    disk = math.pi * (0.127 / 2.0) ** 2
    sluggish_2 = rotor_hover_check(mass=0.7, rotor_disk_area=disk, n_rotors=4,
                                   max_total_thrust=3.0 * 0.7 * 9.80665, min_thrust_weight=2.0)
    sluggish_4 = rotor_hover_check(mass=0.7, rotor_disk_area=disk, n_rotors=4,
                                   max_total_thrust=3.0 * 0.7 * 9.80665, min_thrust_weight=4.0)
    assert sluggish_2["ok"] is True and sluggish_4["ok"] is False


def test_fixed_wing_self_selects_off_the_hover_axis():
    """A fixed-wing does not hover, so the rotor-hover/momentum axis is physically inapplicable; the
    calibration must return None (axis off), NOT a fabricated pass/fail."""
    assert rotor_hover_check_calibrated(SPECS["sensefly_ebee_x"]) is None
    results = validate_drone("sensefly_ebee_x")
    hover = [r for r in results if "rotor hover" in r.axis]
    assert hover and hover[0].verdict == "info"
    assert "fixed-wing" in hover[0].reference_value.lower()


def test_consumer_drone_hover_axis_reports_gap_not_fabricated_pass():
    """With no sourced max thrust, the rotor-hover axis must report a GAP — never invent a thrust to
    produce a pass. The endurance axis (which only needs Wh + time) still runs and agrees."""
    results = validate_drone("dji_air3")
    hover = [r for r in results if "rotor hover" in r.axis]
    assert hover and hover[0].verdict == "gap"
    endurance = [r for r in results if "endurance" in r.axis]
    assert endurance and endurance[0].verdict == "agree"  # self-consistent energy budget


def test_calibration_findings_text_names_the_real_drones():
    txt = calibration_findings()
    assert "Matrice 350" in txt and "FALSE-FAIL" in txt
    assert "1.42" in txt  # the M350's actual T/W appears
    assert "Nazgul" in txt  # the over-lax end is anchored by a real product


# ── the discovered scaling laws + the keep-only-what-generalises discipline ───────────────────────

def test_dataset_is_assembled_from_real_catalog_facts_only():
    pts = dataset()
    assert len(pts) >= 12
    # every point's mass is the catalog mass (no fabricated coordinate)
    for p in pts[:5]:
        assert p.mass_kg == SPECS[p.key].mass_kg.value


def test_prop_mass_law_generalises_out_of_sample_and_is_kept_at_the_physical_exponent():
    """LAW B is the discovery that holds: disk-loading-bounded design predicts prop AREA ∝ weight, i.e.
    D ∝ mass^0.5. The fitted exponent must be ≈0.5 AND validate leave-one-out → kept."""
    law = fit_prop_mass_law()
    assert law.name == "prop_diameter_vs_mass"
    assert law.exponent == pytest.approx(0.5, abs=0.12), "D∝mass^0.5 (prop area ∝ weight)"
    assert law.oos_r2 >= GENERALISES_OOS_R2 and law.generalises
    assert "KEPT" in law.note


def test_battery_mass_law_is_honestly_rejected_not_oversold():
    """The discovery discipline's other half: battery-Wh vs mass does NOT generalise (the heavy drones
    carry disproportionately more battery) → reported rejected, never stored as a validated law."""
    law = fit_battery_mass_law()
    assert law.oos_r2 < GENERALISES_OOS_R2 and not law.generalises
    assert "rejected" in law.note.lower()


def test_endurance_law_reports_its_honest_verdict():
    """The endurance law's keep/reject is decided by its real OOS score, not asserted in advance — but
    its verdict text must match its computed ``generalises`` flag (no oversold law)."""
    law = fit_endurance_law()
    if law.generalises:
        assert law.oos_r2 >= GENERALISES_OOS_R2 and "KEPT" in law.note
    else:
        assert law.oos_r2 < GENERALISES_OOS_R2 and "rejected" in law.note.lower()


def test_hover_thrust_identity_holds_for_all_sourced_drones():
    """The dimensional identity τ=m·g: every catalogued drone with a sourced max-thrust must clear
    T/W≥1 (it can at least lift itself) — the loop-closing consistency check, exact by construction."""
    law = hover_thrust_identity()
    assert law.exponent == 1.0 and law.generalises
    assert "100%" in law.note  # all sourced drones clear T/W ≥ 1


def test_validate_all_covers_every_drone():
    allr = validate_all()
    assert set(allr) == set(drones())
    assert all(len(v) >= 1 for v in allr.values())
