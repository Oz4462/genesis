"""GATE δ-physics — runs the engineering validators and aggregates one verdict.

The δ-layer validators (torsion, buckling, fatigue, contact, pressure_vessel, creep,
thermal over-temperature, thermal-expansion mismatch, resonance, … ; 40 total in VALIDATORS)
each answer a single failure mode in isolation. This module is the GATE that ties them into the
pipeline: given a list of declared ``PhysicsCheck``s — each naming a validator and the
resolved numeric inputs for it — it runs every one and returns a single
``GateResult`` that passes ONLY if every check actually ran and reported ``ok``.

Registry + recipes (42 in physics_selection.RECIPES) make checks auto-selectable from
spec measurands (see physics_selection.select_physics_checks + pipeline.assess_specification).

It carries GENESIS's anti-hallucination discipline into the physics layer:

  • A check naming an UNKNOWN validator is a hard failure (``PHYSICS_UNKNOWN_VALIDATOR``)
    — the gate never certifies a check it has no code to evaluate.
  • A validator that RAISES on its inputs (a bad/contradictory geometry or material) is
    a hard failure (``PHYSICS_CHECK_ERROR``), never a silent pass — an un-evaluatable
    check is surfaced, not swallowed.
  • A validator that runs and reports ``ok=False`` is a hard failure
    (``PHYSICS_CHECK_FAILED``) with the computed safety factor as evidence.

So the verdict is honest by construction: the gate passes a design only when each
declared physics check was genuinely computed and cleared its own margin. An empty
check list passes vacuously (nothing was declared, so nothing can fail) — the analogue
of the spec gates passing an empty specification.

The PhysicsCheck carries RESOLVED numeric inputs, exactly as the spec gates operate on
declared Quantities: in the full pipeline an agent emits the checks from the
specification (mapping quantity_ids to values, the way derivations are resolved); this
gate is the deterministic, LLM-free backstop that re-runs them. Offline, pure functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .dimensional_guard import scale_invariance_report
from .bolted_joint import bolted_joint_check
from .buckling import buckling_check
from .contact import contact_check
from .core.interfaces import GateFailure, GateResult
from .creep import creep_life_check
from .fatigue import goodman_check
from .fracture import fracture_check
from .modal import resonance_check
from .flight import (
    attitude_pd_check,
    battery_endurance_check,
    current_budget_check,
    rotor_hover_check,
)
from .notch_fatigue import notch_fatigue_check
from .plate_bending import plate_bending_check
from .pressure_vessel import pressure_vessel_check
from .security import (
    birthday_bound_check,
    gcm_invocation_budget_check,
    key_security_check,
)
from .printability import (
    bridge_span_check,
    emboss_detail_check,
    fdm_fit_clearance_check,
    layer_adhesion_check,
    pin_diameter_check,
    thread_size_check,
    unsupported_wall_check,
)
from .thermal import overtemperature_check
from .thermal_stress import thermal_mismatch_check
from .torsion import shaft_torsion_check
from .kinematics import reach_check, zmp_balance_check
from .actuation import (
    electric_actuator_check,
    hydraulic_cylinder_check,
    hydraulic_flow_check,
)
from .compute import (
    compute_budget_check,
    inference_latency_check,
    inference_power_check,
)
from .digital_bus import bus_bandwidth_check, bus_latency_check
from .dynamics import (
    joint_swing_torque_check,
    swing_resonance_check,
    zmp_dynamic_check,
)
from .montecarlo import montecarlo_uncertainty


def montecarlo_uncertainty_check(
    formula: str,
    values: dict,
    uncertainties: dict,
    *,
    n_samples: int = 200,
    seed: int = 0,
    coverage: float = 0.95,
    max_rel_std: float | None = None,
) -> dict:
    """GATE-compatible Monte Carlo uncertainty screen (JCGM 101 style).

    Wraps ``montecarlo.montecarlo_uncertainty`` and adds an ``ok`` verdict:
    finite mean/std, and optionally relative std ≤ ``max_rel_std`` when set.
    """
    rep = montecarlo_uncertainty(
        formula,
        values,
        uncertainties,
        n_samples=n_samples,
        seed=seed,
        coverage=coverage,
    )
    mean = float(rep["mean"])
    std = float(rep["std"])
    ok = math.isfinite(mean) and math.isfinite(std) and std >= 0.0
    if ok and max_rel_std is not None and mean != 0.0:
        ok = (std / abs(mean)) <= float(max_rel_std)
    out = dict(rep)
    out["ok"] = ok
    # Dimensionless relative uncertainty as a pseudo safety_factor when mean ≠ 0
    out["safety_factor"] = (abs(mean) / std) if (ok and std > 0.0) else (1.0 if ok else 0.0)
    return out


def montecarlo_product_check(
    a: float,
    u_a: float,
    b: float,
    u_b: float,
    *,
    n_samples: int = 200,
    seed: int = 0,
    coverage: float = 0.95,
    max_rel_std: float | None = 0.25,
) -> dict:
    """Auto-selectable MC screen for the product y = a·b (self-improve gap close).

    Full arbitrary-formula MC stays callable via :func:`montecarlo_uncertainty_check`.
    This flat-arg form matches CheckRecipe float inputs for δ auto-select.
    """
    return montecarlo_uncertainty_check(
        "a*b",
        {"a": float(a), "b": float(b)},
        {"a": float(u_a), "b": float(u_b)},
        n_samples=n_samples,
        seed=seed,
        coverage=coverage,
        max_rel_std=max_rel_std,
    )


def vacuum_radiation_balance_check(
    absorbed_solar_w: float,
    epsilon: float,
    area_m2: float,
    t_k: float,
    *,
    tol: float = 0.1,
    radiation_dose_sv: float = 0.0,
    designed_as_sink_or_source: bool = False,
    dose_limit_sv: float = 1e12,
) -> dict:
    """Minimal vacuum radiation balance (Stefan-Boltzmann, honest for space).

    Net heat = absorbed - epsilon * sigma * A * T^4.
    For space hardware (no convection). Conservative; real includes albedo, view factors, transients.

    Supports designed sink/source: when designed_as_sink_or_source=True, imbalance is accepted.
    radiation_dose_sv always participates: dose_ok = dose <= dose_limit_sv.
    """
    for v in (absorbed_solar_w, epsilon, area_m2, t_k, tol, radiation_dose_sv, dose_limit_sv):
        if not math.isfinite(v):
            return {"ok": False, "error": "non_finite_input"}
    if absorbed_solar_w < 0 or epsilon <= 0 or epsilon > 1 or area_m2 <= 0 or t_k <= 0:
        return {"ok": False, "error": "invalid_inputs"}
    if radiation_dose_sv < 0 or dose_limit_sv < 0:
        return {"ok": False, "error": "invalid_inputs"}
    sigma = 5.670374419e-8  # W m^-2 K^-4 (exact CODATA)
    radiated = epsilon * sigma * area_m2 * (t_k ** 4)
    net = absorbed_solar_w - radiated
    balanced = abs(net) <= tol * max(abs(absorbed_solar_w), 1.0)
    designed_ok = bool(designed_as_sink_or_source)
    dose_ok = radiation_dose_sv <= dose_limit_sv
    ok = (balanced or designed_ok) and dose_ok
    result = {
        "ok": ok,
        "net_heat_w": net,
        "radiated_w": radiated,
        "safety_factor": ((absorbed_solar_w / (radiated + 1e-9)) if absorbed_solar_w > 0 else None) if ok else 0.0,
        "quelle": "Stefan-Boltzmann (vacuum, no convection) + user params",
        "radiation_dose_sv": radiation_dose_sv,
        "dose_ok": dose_ok,
    }
    if not dose_ok:
        result["dose_note"] = f"dose {radiation_dose_sv} exceeds configured limit {dose_limit_sv}"
    if designed_as_sink_or_source:
        result["designed_note"] = "designed sink/source (imbalance accepted per spec)"
    return result


def isru_electrolysis_o2_check(
    water_kg: float, efficiency: float = 0.80, *, o2_target_kg: float = 0.0
) -> dict:
    """Minimal closed-form ISRU O2 yield via water electrolysis stoichiometry.

    2 H2O -> O2 + 2 H2. Molar proxy 36 g water -> 32 g O2. Efficiency accounts for real losses.
    """
    for v in (water_kg, efficiency, o2_target_kg):
        if not math.isfinite(v):
            return {"ok": False, "error": "non_finite_input"}
    if water_kg <= 0 or not (0 < efficiency <= 1.0):
        return {"ok": False, "error": "invalid_inputs"}
    stoich_o2 = (32.0 / 36.0) * water_kg * efficiency
    ok = (o2_target_kg <= 0.0) or (stoich_o2 >= o2_target_kg * 0.95)
    return {
        "ok": ok,
        "o2_produced_kg": stoich_o2,
        "water_consumed_kg": water_kg,
        "efficiency": efficiency,
        "quelle": "stoichiometry 2H2O -> O2 + 2H2 (molar 36->32 proxy) * efficiency",
        "safety_factor": (stoich_o2 / max(o2_target_kg, 1e-9)) if o2_target_kg > 0 else None,
    }


def life_support_o2_balance_check(
    crew: float,
    o2_consumption_kg_per_day: float = 0.84,
    closure_rate: float = 0.0,
    *,
    target_closure: float = 0.0,
) -> dict:
    """Minimal closed-form LIFE_SUPPORT O2 balance for habitats (ECLSS)."""
    for v in (crew, o2_consumption_kg_per_day, closure_rate, target_closure):
        if not math.isfinite(v):
            return {"ok": False, "error": "non_finite_input"}
    if crew <= 0 or not (0 <= closure_rate <= 1) or o2_consumption_kg_per_day <= 0:
        return {"ok": False, "error": "invalid_inputs"}
    consumed = crew * o2_consumption_kg_per_day
    produced = consumed * closure_rate
    ok = (target_closure <= 0) or (closure_rate >= target_closure * 0.95)
    return {
        "ok": ok,
        "o2_consumed_kg_day": consumed,
        "o2_produced_kg_day": produced,
        "closure_rate": closure_rate,
        "quelle": "crew O2 consumption proxy (0.84 kg/day/person) * closure_rate",
        "safety_factor": (closure_rate / max(target_closure, 1e-9)) if target_closure > 0 else None,
    }


# Registry of validators the gate can run. Each is a *_check function returning a dict
# that contains at least an "ok" bool (and usually a "safety_factor"). The key is the
# stable name a PhysicsCheck declares.
VALIDATORS = {
    "torsion": shaft_torsion_check,
    "buckling": buckling_check,
    "fatigue": goodman_check,
    "contact": contact_check,
    "pressure_vessel": pressure_vessel_check,
    "creep": creep_life_check,
    "overtemperature": overtemperature_check,
    "thermal_mismatch": thermal_mismatch_check,
    "resonance": resonance_check,
    "notch_fatigue": notch_fatigue_check,
    "fracture": fracture_check,
    "plate_bending": plate_bending_check,
    "bolted_joint": bolted_joint_check,
    # printability — the design errors that only show up on the print bed
    "bridge_span": bridge_span_check,
    "fdm_fit_clearance": fdm_fit_clearance_check,
    "pin_diameter": pin_diameter_check,
    "thread_size": thread_size_check,
    "unsupported_wall": unsupported_wall_check,
    "emboss_detail": emboss_detail_check,
    "layer_adhesion": layer_adhesion_check,
    # flight — the closed-form axes a multirotor lives or dies by
    "rotor_hover": rotor_hover_check,
    "battery_endurance": battery_endurance_check,
    "current_budget": current_budget_check,
    "attitude_pd": attitude_pd_check,
    # security — closed-form cryptographic sizing (NIST-anchored)
    "birthday_bound": birthday_bound_check,
    "key_security": key_security_check,
    "gcm_invocation_budget": gcm_invocation_budget_check,
    # robot — humanoid kinematics / actuation / onboard-compute sizing screens
    "reach": reach_check,
    "zmp_balance": zmp_balance_check,
    "electric_actuator": electric_actuator_check,
    "hydraulic_cylinder": hydraulic_cylinder_check,
    "hydraulic_flow": hydraulic_flow_check,
    "compute_budget": compute_budget_check,
    "inference_power": inference_power_check,
    "inference_latency": inference_latency_check,
    "bus_bandwidth": bus_bandwidth_check,
    "bus_latency": bus_latency_check,
    # space — multi-planetary vacuum radiation (no convection)
    "vacuum_radiation_balance": vacuum_radiation_balance_check,
    # ISRU / LIFE_SUPPORT closed-form proxies (mass balance, not full plant models)
    "isru_electrolysis_o2": isru_electrolysis_o2_check,
    "life_support_o2_balance": life_support_o2_balance_check,
    # robot dynamics — motion over a gait cycle (dynamic balance + swing inverse dynamics)
    "swing_resonance": swing_resonance_check,
    "zmp_dynamic": zmp_dynamic_check,
    "joint_swing_torque": joint_swing_torque_check,
    # uncertainty — Monte Carlo propagation (JCGM 101 style screen)
    "montecarlo_uncertainty": montecarlo_uncertainty_check,
    # flat-arg product form for CheckRecipe auto-select (gap close 2026-07-14)
    "montecarlo_product": montecarlo_product_check,
}


# Validators PROVEN input-homogeneous: their dimensionless safety_factor stays invariant under a
# coherent unit rescaling (see tests/test_dimensional_invariance.py). ONLY these are auto-checked by
# the dimensional guard at gate time. A validator that bakes in a DIMENSIONAL constant it does not
# take as an argument (e.g. a hard-coded g) is NOT input-homogeneous and would false-alarm — so it
# is excluded BY CONSTRUCTION (dimensional_guard.py "HONEST SCOPE"). The guard can only ever fire on
# a genuine dimensional formula bug in one of these, never cry wolf on a correct one. Extending this
# set requires adding a scale-invariance proof to that test, never a guess.
SCALE_INVARIANT_VALIDATORS: frozenset[str] = frozenset({
    "electric_actuator",
    "hydraulic_cylinder",
    "hydraulic_flow",
    "birthday_bound",
    "gcm_invocation_budget",
})


def _dimensional_ok(validator: str, inputs: dict, input_units: dict, result: dict) -> bool | None:
    """Run the dimensional guard on an input-homogeneous validator: its dimensionless
    ``safety_factor`` must be INVARIANT under a coherent unit rescaling (dimensional_guard).

    Returns True/False, or None when the check is not eligible — the validator is not in the
    proven-homogeneous set, no per-input units were declared, or the result has no numeric
    safety_factor. A returned False is a real dimensional formula bug in the validator, NOT a
    physics-margin failure. Non-unit ``extra`` kwargs (dimensionless config like an end-condition)
    are passed through fixed, only the unit-carrying inputs are rescaled.
    """
    if validator not in SCALE_INVARIANT_VALIDATORS:
        return None
    sf = result.get("safety_factor")
    if not isinstance(sf, (int, float)) or isinstance(sf, bool):
        return None
    # Non-finite dimensionless verdict is never scale-invariant "ok" — NaN would
    # also poison IEEE comparisons downstream (REWORK 2026-07-11).
    if not math.isfinite(sf):
        return False
    units = {arg: u for arg, u in input_units.items() if arg in inputs}
    if not units:
        return None
    fn = VALIDATORS[validator]
    extra = {k: v for k, v in inputs.items() if k not in units}
    guard_inputs = {arg: (inputs[arg], u) for arg, u in units.items()}

    def _fn(**kw):
        return fn(**kw, **extra)

    try:
        rep = scale_invariance_report(_fn, guard_inputs)
    except (TypeError, ValueError, KeyError, ZeroDivisionError, ArithmeticError):
        return None  # the guard could not run (opaque unit, bad args) — not a dimensional verdict
    except Exception:
        # Unexpected failure: still abstain (None), never invent invariant=True.
        return None
    # Re-check the measured report: non-finite base/rescaled is not a green pass.
    if not math.isfinite(rep.get("base", float("nan"))) or not math.isfinite(
        rep.get("rescaled", float("nan"))
    ):
        return False
    return bool(rep["invariant"])


@dataclass(frozen=True)
class PhysicsCheck:
    """One declared engineering check: run validator `validator` with `inputs`.

    `name`        human label for the location/check (e.g. "drive shaft torsion").
    `validator`   a key in ``VALIDATORS``.
    `inputs`      keyword arguments for that validator (resolved numeric values).
    `input_units` arg -> unit string (from the recipe), enabling the dimensional guard for the
                  proven-homogeneous validators. Optional/empty = no dimensional check (backward
                  compatible — a check built without units behaves exactly as before).
    """

    name: str
    validator: str
    inputs: dict = field(default_factory=dict)
    input_units: dict = field(default_factory=dict)


def run_physics_checks(checks: list[PhysicsCheck]) -> list[dict]:
    """Run every check and return per-check evidence (no pass/fail decision here).

    Each result dict carries ``{"name", "validator", "status", "ok", "detail",
    "result", "dimensional_ok"}``: status is "ran" | "unknown" | "error"; ok is the
    validator's verdict (False for unknown/error); result is the validator's full output
    dict (or None); detail is a short human reason for unknown/error; dimensional_ok is the
    scale-invariance verdict (True/False) for a proven-homogeneous validator with declared
    units, else None (not checked). Deterministic; runs each validator in a try/except so one
    bad check cannot abort the batch.
    """
    out: list[dict] = []
    for check in checks:
        fn = VALIDATORS.get(check.validator)
        if fn is None:
            out.append({
                "name": check.name, "validator": check.validator, "status": "unknown",
                "ok": False, "detail": f"no validator named {check.validator!r}",
                "result": None, "dimensional_ok": None,
            })
            continue
        # Screen non-finite numeric inputs before the validator (IEEE NaN never
        # fails ``sf < limit`` comparisons — fail as ERROR, never a green pass).
        bad = next(
            (
                (k, v)
                for k, v in check.inputs.items()
                if isinstance(v, (int, float))
                and not isinstance(v, bool)
                and not math.isfinite(float(v))
            ),
            None,
        )
        if bad is not None:
            out.append({
                "name": check.name, "validator": check.validator, "status": "error",
                "ok": False, "detail": f"non-finite input {bad[0]}={bad[1]}",
                "result": None, "dimensional_ok": None,
            })
            continue
        try:
            result = fn(**check.inputs)
            if not isinstance(result, dict):
                # a non-dict would crash .get() below — surface as THIS check's error
                raise TypeError(f"validator returned non-dict ({type(result).__name__})")
        except Exception as exc:  # a bad/contradictory input must surface, not pass
            out.append({
                "name": check.name, "validator": check.validator, "status": "error",
                "ok": False, "detail": f"{type(exc).__name__}: {exc}", "result": None,
                "dimensional_ok": None,
            })
            continue
        # Non-finite safety_factor / ratio with ok=True is poison: IEEE NaN never
        # fails ``sf < limit`` comparisons. Fail loud as error, not a green pass
        # (REWORK 2026-07-11).
        sf = result.get("safety_factor", result.get("ratio"))
        if (
            isinstance(sf, (int, float))
            and not isinstance(sf, bool)
            and not math.isfinite(sf)
        ):
            out.append({
                "name": check.name, "validator": check.validator, "status": "error",
                "ok": False,
                "detail": f"non-finite safety_factor/ratio {sf!r}",
                "result": result,
                "dimensional_ok": False,
            })
            continue
        out.append({
            "name": check.name, "validator": check.validator, "status": "ran",
            "ok": bool(result.get("ok", False)), "detail": "", "result": result,
            "dimensional_ok": _dimensional_ok(
                check.validator, check.inputs, check.input_units, result
            ),
        })
    return out


def gate_delta_physics(checks: list[PhysicsCheck]) -> GateResult:
    """Aggregate the declared physics checks into one GATE δ-physics verdict.

    Passes only if EVERY check ran and reported ok. Each non-passing check yields a
    GateFailure: ``PHYSICS_UNKNOWN_VALIDATOR`` (no code to evaluate it),
    ``PHYSICS_CHECK_ERROR`` (the validator raised — un-evaluatable inputs),
    ``PHYSICS_CHECK_FAILED`` (ran but the margin is not cleared, with the safety factor
    in the detail), or ``PHYSICS_DIMENSIONAL_INCONSISTENCY`` (ran and cleared its margin
    but its safety_factor is NOT scale-invariant — a dimensional formula bug in the
    validator itself, caught automatically by the dimensional guard). An empty list passes
    vacuously. Pure; no model calls.
    """
    failures: list[GateFailure] = []
    for r in run_physics_checks(checks):
        if r["status"] == "unknown":
            failures.append(GateFailure(
                code="PHYSICS_UNKNOWN_VALIDATOR",
                detail=f"{r['name']}: {r['detail']}",
            ))
        elif r["status"] == "error":
            failures.append(GateFailure(
                code="PHYSICS_CHECK_ERROR",
                detail=f"{r['name']} ({r['validator']}): {r['detail']}",
            ))
        elif not r["ok"]:
            res = r["result"] or {}
            margin = res.get("safety_factor", res.get("ratio"))
            margin_txt = "no margin reported" if margin is None else f"safety_factor={margin}"
            failures.append(GateFailure(
                code="PHYSICS_CHECK_FAILED",
                detail=f"{r['name']} ({r['validator']}): not ok ({margin_txt})",
            ))
        elif r.get("dimensional_ok") is False:
            failures.append(GateFailure(
                code="PHYSICS_DIMENSIONAL_INCONSISTENCY",
                detail=f"{r['name']} ({r['validator']}): safety_factor is not scale-invariant "
                       "— a dimensionally inconsistent term in the validator formula",
            ))
    return GateResult(gate="delta-physics", passed=not failures, failures=failures)
