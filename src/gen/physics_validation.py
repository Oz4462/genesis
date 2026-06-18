"""GATE δ-physics — runs the engineering validators and aggregates one verdict.

The δ-layer validators (torsion, buckling, fatigue, contact, pressure_vessel, creep,
thermal over-temperature, thermal-expansion mismatch, resonance, …) each answer a
single failure mode in isolation. This module is the GATE that ties them into the
pipeline: given a list of declared ``PhysicsCheck``s — each naming a validator and the
resolved numeric inputs for it — it runs every one and returns a single
``GateResult`` that passes ONLY if every check actually ran and reported ``ok``.

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

from dataclasses import dataclass, field

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
}


@dataclass(frozen=True)
class PhysicsCheck:
    """One declared engineering check: run validator `validator` with `inputs`.

    `name`       human label for the location/check (e.g. "drive shaft torsion").
    `validator`  a key in ``VALIDATORS``.
    `inputs`     keyword arguments for that validator (resolved numeric values).
    """

    name: str
    validator: str
    inputs: dict = field(default_factory=dict)


def run_physics_checks(checks: list[PhysicsCheck]) -> list[dict]:
    """Run every check and return per-check evidence (no pass/fail decision here).

    Each result dict carries ``{"name", "validator", "status", "ok", "detail",
    "result"}``: status is "ran" | "unknown" | "error"; ok is the validator's verdict
    (False for unknown/error); result is the validator's full output dict (or None);
    detail is a short human reason for unknown/error. Deterministic; runs each validator
    in a try/except so one bad check cannot abort the batch.
    """
    out: list[dict] = []
    for check in checks:
        fn = VALIDATORS.get(check.validator)
        if fn is None:
            out.append({
                "name": check.name, "validator": check.validator, "status": "unknown",
                "ok": False, "detail": f"no validator named {check.validator!r}",
                "result": None,
            })
            continue
        try:
            result = fn(**check.inputs)
        except Exception as exc:  # a bad/contradictory input must surface, not pass
            out.append({
                "name": check.name, "validator": check.validator, "status": "error",
                "ok": False, "detail": f"{type(exc).__name__}: {exc}", "result": None,
            })
            continue
        out.append({
            "name": check.name, "validator": check.validator, "status": "ran",
            "ok": bool(result.get("ok", False)), "detail": "", "result": result,
        })
    return out


def gate_delta_physics(checks: list[PhysicsCheck]) -> GateResult:
    """Aggregate the declared physics checks into one GATE δ-physics verdict.

    Passes only if EVERY check ran and reported ok. Each non-passing check yields a
    GateFailure: ``PHYSICS_UNKNOWN_VALIDATOR`` (no code to evaluate it),
    ``PHYSICS_CHECK_ERROR`` (the validator raised — un-evaluatable inputs), or
    ``PHYSICS_CHECK_FAILED`` (ran but the margin is not cleared, with the safety factor
    in the detail). An empty list passes vacuously. Pure; no model calls.
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
    return GateResult(gate="delta-physics", passed=not failures, failures=failures)
