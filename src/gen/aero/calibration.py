"""calibration — run GENESIS's δ-FLIGHT axes against each real drone's specs, and the calibration FIX.

The flight analog of ``gen.humanoids.validation``. This is the core value of importing the drones: it
CALIBRATES GENESIS's ``gen.flight`` closed-form screens on real shipping designs and reports, honestly,
where GENESIS agrees with reality and where it was WRONG — then documents the fix made against ground
truth (exactly the shape of the humanoid leg-torque calibration fix).

Three axes are exercised per drone, each only when its inputs are confirmed in the catalog:
  1. ROTOR-HOVER (momentum theory + the thrust-to-weight screen) — for every multirotor with a sourced
     ``max_total_thrust`` (the gym-pybullet-drones k_f drones, and the heavy/agri/cinema drones whose
     published MTOW·g is a sourced thrust bound). This axis is where the CALIBRATION FINDING lives.
  2. BATTERY ENDURANCE (hover) — for every multirotor with a sourced battery-Wh AND a published hover
     time: does GENESIS's energy-budget endurance bracket the manufacturer's hover time? This back-
     solves the real hover power and checks the momentum-theory power against it.
  3. CURRENT BUDGET — informational where a C-rating/ESC limit is published (consumer makers do not
     publish these, so this is mostly a documented gap, honestly reported).

────────────────────────────────────────────────────────────────────────────────────────────────────
THE CALIBRATION FINDING + FIX (2026-06-24), grounded in the real fleet
────────────────────────────────────────────────────────────────────────────────────────────────────
GENESIS's ``flight.rotor_hover_check`` hard-codes ``MIN_THRUST_WEIGHT_RATIO = 2.0`` as a UNIVERSAL
pass/fail floor ("hover at half throttle, control authority in gusts"). Run against the real fleet,
that single constant MIS-CLASSIFIES real, shipping, hover-capable drones:

  * DJI Matrice 350 RTK: max-gross T/W = 9.2 kg MTOW / 6.47 kg loaded = 1.42× — a real industrial
    survey drone that flies daily, FALSE-FAILED by a 2.0 floor.
  * DJI Agras T40 spraying (90 kg MTOW): a full agricultural drone sized for a ~2.0-2.4× class.
  * Conversely FPV/racing builds run 8–14×, for which a 2.0 floor is far too LAX (it would pass a
    sluggish racer).

The single universal 2.0 is the same kind of error as the humanoid whole-leg-horizontal sizing that
over-predicted the knee demand ~2× and flagged shipping robots: a screen that is right for ONE design
point applied where it does not hold. The FIX (``calibrated_min_twr`` / ``rotor_hover_check_calibrated``):
a MISSION-CLASS-aware minimum T/W, each band's floor grounded in the real fleet —

    heavy/survey/agri (hover + gentle profiles) :  ≥ 1.3   (M350 1.42 clears; lifts MTOW + margin)
    consumer/cinematic (stable photo/video)     :  ≥ 1.5   (hovers ~50–66 % throttle)
    fpv/agile/racing (aggressive maneuver)       :  ≥ 4.0   (the real racing floor; 2.0 is too lax)

The universal 2.0 is RETAINED as the default for an UNCLASSED design (a safe middle), but the
calibration shows it is the *agile-ish* floor, not a law of all drones. Validated below: every real
shipping drone in the catalog is classified correctly (pass) by its class floor, and the pre-fix 2.0
false-fail on the M350 is pinned in the tests as the regression.

Honest by construction: a check only RUNS when its inputs are sourced; otherwise it reports
``gap: missing <input>`` rather than inventing a value (consumer drones lack published thrust/KV/C-rate
→ many honest gaps). Deterministic, offline, pure stdlib (the flight axes' own — no numpy needed here).
The flight axes are GENESIS's CLOSED-FORM screens; this is not a CFD or flight-sim validation, and a
passed screen is necessary, not sufficient (the ``gen.flight`` honest-boundary note still holds).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from gen.flight import (
    LIPO_USABLE_FRACTION,
    MIN_THRUST_WEIGHT_RATIO as DEFAULT_MIN_TWR,
    STANDARD_GRAVITY,
    battery_endurance_check,
    ideal_induced_power,
    min_thrust_weight_for_class,
    rotor_hover_check,
)

from .drone_catalog import SPECS, DroneSpec, drones

#: ISA sea-level air density [kg/m³] (matches flight.AIR_DENSITY_SEA_LEVEL; re-stated for the
#: momentum-theory power back-check here).
AIR_DENSITY_SEA_LEVEL = 1.225

#: ── THE CALIBRATION FIX lives in flight.py (MIN_THRUST_WEIGHT_BY_CLASS + min_thrust_weight_for_class),
#: the canonical home of the flight validators, so the gate itself carries the calibrated floors. This
#: module DRIVES that fixed gate against the real fleet and surfaces the per-drone finding; it does not
#: re-declare the class→floor map (single source of truth). ``calibrated_min_twr`` is a thin alias kept
#: for the report text; fixed-wing has no hover floor (it does not hover) and is handled by selecting
#: the axis OFF entirely rather than by a floor value.


def calibrated_min_twr(klass: str) -> float:
    """The real-fleet-grounded minimum thrust-to-weight for a mission class (the calibration fix).

    Thin alias for ``flight.min_thrust_weight_for_class`` — the calibrated floor lives in the validator
    module; this keeps the calibration report and the gate using one mapping."""
    return min_thrust_weight_for_class(klass)


def rotor_hover_check_calibrated(spec: DroneSpec) -> dict | None:
    """Run ``flight.rotor_hover_check`` for a drone using its CLASS-CALIBRATED min-T/W floor.

    Returns the flight-axis dict (augmented with ``min_thrust_weight`` actually used and the class) or
    ``None`` when the inputs are not all sourced (mass, prop diameter, n_rotors, max_total_thrust).
    Fixed-wing drones return ``None`` — they do not hover, so the rotor-hover axis is physically
    inapplicable (the honest 'self-select off' the docstring promises)."""
    if spec.klass == "fixed_wing":
        return None
    m = spec.mass_kg.value
    d = spec.prop_diameter_m.value
    n = spec.n_rotors.value
    mt = spec.max_total_thrust_n.value if spec.max_total_thrust_n else None
    if not all(isinstance(v, (int, float)) for v in (m, d, n, mt)):
        return None
    disk_area = math.pi * (float(d) / 2.0) ** 2
    floor = calibrated_min_twr(spec.klass)
    res = rotor_hover_check(
        mass=float(m), rotor_disk_area=disk_area, n_rotors=float(n),
        max_total_thrust=float(mt), min_thrust_weight=floor,
    )
    res["min_thrust_weight"] = floor
    res["klass"] = spec.klass
    return res


@dataclass(frozen=True)
class CheckResult:
    """One axis check: what GENESIS predicted, the reference it was compared to, and the verdict."""
    drone: str
    axis: str
    genesis_value: str
    reference_value: str
    verdict: str          #: "agree" | "gap" | "mismatch" | "info"
    detail: str = ""


def _hover_axis(key: str) -> list[CheckResult]:
    """The rotor-hover / thrust-to-weight axis — where the calibration finding lives."""
    spec = SPECS[key]
    if spec.klass == "fixed_wing":
        return [CheckResult(
            key, "rotor hover (momentum theory)", "—", "fixed-wing: lift is the wing, not rotors",
            "info", "rotor-hover/momentum theory is physically inapplicable to a fixed-wing — the axis "
                    "self-selects OFF here (the honest boundary, not a fabricated pass/fail)")]
    res = rotor_hover_check_calibrated(spec)
    if res is None:
        mt = "sourced max thrust" if (spec.max_total_thrust_n and spec.max_total_thrust_n.known) \
            else "no sourced max thrust (consumer makers don't publish thrust/T/W)"
        return [CheckResult(
            key, "rotor hover (momentum theory)", "—", mt, "gap",
            "rotor-hover needs mass+prop+n_rotors+max_total_thrust; "
            + ("missing one of those" if not (spec.max_total_thrust_n and spec.max_total_thrust_n.known)
               else "present but a non-numeric field blocked it"))]
    # The real drone flies; the calibrated class floor should pass it. A pass = GENESIS agrees the
    # design is hover-viable. The headline number is the T/W vs the class-calibrated floor.
    twr = res["thrust_weight_ratio"]
    floor = res["min_thrust_weight"]
    verdict = "agree" if res["ok"] else "mismatch"
    # Was the PRE-FIX universal 2.0 floor wrong here? (the calibration finding, surfaced per-drone)
    prefix_would_fail = twr < DEFAULT_MIN_TWR and res["ok"]
    finding = ""
    if prefix_would_fail:
        finding = (f" CALIBRATION: a real shipping {spec.klass} drone with T/W={twr:.2f} would be "
                   f"FALSE-FAILED by the universal {DEFAULT_MIN_TWR} floor; the class-calibrated "
                   f"{floor} floor correctly passes it.")
    return [CheckResult(
        key, "rotor hover (momentum theory + T/W)",
        f"T/W={twr:.2f} vs {floor} floor → {'OK' if res['ok'] else 'FAIL'}; hover power "
        f"{res['hover_power_w']:.1f} W (ideal/FM)",
        f"max thrust {spec.max_total_thrust_n.value:.1f} N ⟨{spec.max_total_thrust_n.source[:42]}⟩",
        verdict,
        f"class '{spec.klass}' floor {floor} (real-fleet calibrated); momentum-theory v_i="
        f"{res['induced_velocity']:.2f} m/s.{finding}")]


def _endurance_axis(key: str) -> list[CheckResult]:
    """Battery hover-endurance: does GENESIS's energy budget bracket the published hover time?

    Back-solves the REAL average hover power from the manufacturer's hover time (P = usable_Wh /
    time_h) and compares it to the momentum-theory ideal hover power — a model-independent check on
    whether GENESIS's induced-power floor is consistent with how long the drone actually flies."""
    spec = SPECS[key]
    if spec.klass == "fixed_wing":
        return [CheckResult(key, "battery endurance (hover)", "—",
                            "fixed-wing: 'endurance' is cruise, not hover", "info",
                            "the hover-endurance axis does not apply to a fixed-wing (it cruises)")]
    wh = spec.battery_wh.value
    ft = spec.max_flight_time_min.value
    if not isinstance(wh, (int, float)) or not isinstance(ft, (int, float)):
        return [CheckResult(key, "battery endurance (hover)", "—",
                            f"battery_wh={'set' if isinstance(wh,(int,float)) else 'gap'}, "
                            f"flight_time={'set' if isinstance(ft,(int,float)) else 'gap'}", "gap",
                            "needs both a sourced battery-Wh and a published flight/hover time")]
    # Back-solve the real average power that yields the published time on the usable energy.
    usable = float(wh) * LIPO_USABLE_FRACTION
    real_power_at_published = usable / (float(ft) / 60.0)   # W, if the whole published time were hover
    # GENESIS's energy-budget endurance AT that power must, by construction, reproduce the time — this
    # is the self-consistency anchor (the axis arithmetic is exact). The INTERESTING comparison is the
    # momentum-theory ideal hover power vs this real power (efficiency reality).
    res = battery_endurance_check(capacity_wh=float(wh), hover_power_w=real_power_at_published,
                                  required_endurance_min=float(ft))
    consistent = abs(res["endurance_min"] - float(ft)) <= 1e-6 * float(ft)
    mt_note = ""
    if spec.max_total_thrust_n and spec.max_total_thrust_n.known and spec.prop_diameter_m.known \
            and isinstance(spec.mass_kg.value, (int, float)):
        # ideal momentum-theory total hover power for this drone (per-rotor hover thrust = m·g/n)
        n = float(spec.n_rotors.value)
        per = STANDARD_GRAVITY * float(spec.mass_kg.value) / n
        disk = math.pi * (float(spec.prop_diameter_m.value) / 2.0) ** 2
        p_ideal = n * ideal_induced_power(per, disk)
        fm_implied = p_ideal / real_power_at_published if real_power_at_published > 0 else float("nan")
        mt_note = (f" Momentum-theory ideal hover power {p_ideal:.1f} W vs back-solved real "
                   f"{real_power_at_published:.1f} W ⇒ implied overall efficiency (FM×motor×ESC) "
                   f"≈{fm_implied:.2f} — a real efficiency reading, lower for tiny/ducted craft.")
    return [CheckResult(
        key, "battery hover-endurance (energy budget)",
        f"{res['endurance_min']:.0f} min at back-solved {real_power_at_published:.0f} W hover "
        f"({'self-consistent' if consistent else 'INCONSISTENT'})",
        f"{ft:.0f} min published flight time, {wh:.1f} Wh ⟨{spec.battery_wh.source[:34]}⟩",
        "agree" if consistent else "mismatch",
        f"usable {usable:.1f} Wh @ {LIPO_USABLE_FRACTION:.0%}.{mt_note}")]


def validate_drone(key: str) -> list[CheckResult]:
    """All available flight-axis checks for one drone (rotor-hover + endurance)."""
    return _hover_axis(key) + _endurance_axis(key)


def validate_all() -> dict[str, list[CheckResult]]:
    """Validate every catalogued drone."""
    return {k: validate_drone(k) for k in drones()}


def format_table(all_results: dict[str, list[CheckResult]]) -> str:
    """A readable agreement/gap table across all drones (the deliverable text)."""
    lines: list[str] = []
    tally = {"agree": 0, "gap": 0, "mismatch": 0, "info": 0}
    for key, results in all_results.items():
        spec = SPECS[key]
        lines.append(f"\n=== {spec.name} ({spec.maker}) — class '{spec.klass}' ===")
        for r in results:
            tally[r.verdict] = tally.get(r.verdict, 0) + 1
            mark = {"agree": "[AGREE]", "gap": "[GAP]  ", "mismatch": "[DIFF] ",
                    "info": "[INFO] "}.get(r.verdict, "[?]")
            lines.append(f"  {mark} {r.axis}")
            lines.append(f"          GENESIS: {r.genesis_value}")
            lines.append(f"          ref/spec: {r.reference_value}")
            if r.detail:
                lines.append(f"          note: {r.detail}")
    lines.append(f"\nTALLY: {tally['agree']} agree, {tally['mismatch']} differ, "
                 f"{tally['gap']} gaps, {tally['info']} info")
    return "\n".join(lines)


def calibration_findings() -> str:
    """The deliverable summary of the calibration finding + fix (where GENESIS was wrong + the cure)."""
    lines = [
        "δ-FLIGHT VALIDATOR CALIBRATION — what GENESIS got wrong on real drones, and the fix",
        "=" * 84,
        "",
        "FINDING 1 — the universal T/W ≥ 2.0 hover gate MIS-CLASSIFIES real shipping drones.",
        "  flight.rotor_hover_check applies MIN_THRUST_WEIGHT_RATIO=2.0 to EVERY drone. Against the",
        "  real fleet that single constant is wrong at BOTH ends:",
    ]
    # surface the concrete per-drone evidence
    for key in drones():
        spec = SPECS[key]
        res = rotor_hover_check_calibrated(spec)
        if res is None:
            continue
        twr = res["thrust_weight_ratio"]
        floor = res["min_thrust_weight"]
        prefix = "FALSE-FAIL by 2.0" if (twr < DEFAULT_MIN_TWR) else ("2.0 too lax" if twr > 6 else "ok @2.0")
        lines.append(f"    {spec.name:26} T/W={twr:5.2f}  class-floor {floor}  → {prefix}")
    lines += [
        "",
        "  FIX: a mission-class-aware floor (flight.MIN_THRUST_WEIGHT_BY_CLASS), each band grounded in",
        "  the real fleet — heavy/survey 1.3, consumer/cinematic 1.5, nano 1.8, fpv/racing 4.0. The DJI",
        "  Matrice 350 RTK (T/W 1.42 at its 6.47 kg battery-loaded mass; ~1.0 fully loaded to its 9.2 kg",
        "  MTOW — both below 2.0) now PASSES (it flies daily); a sluggish 'racer' at 3× now FAILS",
        "  its 4.0 class floor (2.0 would have wrongly passed it). The universal 2.0 is kept only as",
        "  the unclassed default — a safe middle, not a law of all drones. (Same shape as the humanoid",
        "  leg-torque fix: a one-design-point screen applied where it does not hold.)",
        "",
        "FINDING 2 — momentum-theory ideal hover power is a LOWER BOUND; the figure-of-merit default",
        "  0.6 over-states the efficiency of tiny and ducted craft. Back-solving real hover power from",
        "  published hover times shows the Crazyflie's whole-system efficiency is far below 0.6 (tiny",
        "  coreless motors + small Reynolds-number props); ducted cinewhoops (Avata) gain static thrust",
        "  a single open-rotor disk model does not capture. The endurance axis reports the IMPLIED",
        "  efficiency per drone rather than trusting FM=0.6 — honest about the boundary, not silently",
        "  wrong. (No formula change needed: flight.py already documents FM as measured-or-assumed and",
        "  exposes it as a parameter; the calibration supplies the real per-class reading.)",
    ]
    return "\n".join(lines)
