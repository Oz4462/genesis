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
    # robot dynamics — motion over a gait cycle (dynamic balance + swing inverse dynamics)
    "swing_resonance": swing_resonance_check,
    "zmp_dynamic": zmp_dynamic_check,
    "joint_swing_torque": joint_swing_torque_check,
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
        try:
            result = fn(**check.inputs)
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
            failures.append(GateFailure(
                code="PHYSICS_CHECK_FAILED",
                detail=f"{r['name']} ({r['validator']}): not ok (safety_factor={margin})",
            ))
        elif r.get("dimensional_ok") is False:
            failures.append(GateFailure(
                code="PHYSICS_DIMENSIONAL_INCONSISTENCY",
                detail=f"{r['name']} ({r['validator']}): safety_factor is not scale-invariant "
                       "— a dimensionally inconsistent term in the validator formula",
            ))
    return GateResult(gate="delta-physics", passed=not failures, failures=failures)
