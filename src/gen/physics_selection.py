"""Auto-selection of physics checks from a Specification — the spec→gate wiring.

GATE δ-physics (physics_validation.py) runs a list of declared ``PhysicsCheck``s. This
module is what BUILDS that list from a Specification, so the gate selects its own checks
instead of being handed them. It is the deterministic, LLM-free analogue of the
derivation system: where a Derivation references quantity_ids by name, a ``CheckRecipe``
references quantities by their DECLARED ``measurand`` tag — the same explicit, non-inferred
link GATE γ C-17 already uses to prove two quantities cannot contradict.

How it works: each recipe declares a TRIGGER measurand (the presence of which means the
design has that physics — e.g. ``"shaft.torque"`` means there is a shaft in torsion) and
the measurand+unit each validator input must be resolved from. ``select_physics_checks``:

  • skips a recipe whose trigger is absent — the design simply has no such physics (no
    check, no gap: silence is correct here);
  • emits a ready ``PhysicsCheck`` when the trigger is present and EVERY input resolves —
    converting each quantity to the unit the validator expects (sound unit conversion via
    units.py, not a silent magnitude guess);
  • surfaces a GAP when the trigger is present but an input is missing, dimensionally
    incompatible, or in an opaque unit — an indicated-but-unrunnable check is reported,
    never silently dropped and never fed a wrong-unit number.

So the selection is honest by construction: a physics concern the spec declares either
becomes a real, unit-correct check or an explicit gap. The gate then runs the checks; the
gaps travel alongside, exactly as the spec gates surface what they could not certify.
Offline, pure functions, no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core.errors import UnitError
from .core.state import Quantity, Specification
from .core.interfaces import GateResult
from .physics_validation import PhysicsCheck, gate_delta_physics
from .verification.units import parse_unit, unit_scale


@dataclass(frozen=True)
class CheckRecipe:
    """How to build one PhysicsCheck from a spec's measurand-tagged quantities.

    `name`       human label for the emitted check.
    `validator`  a key in physics_validation.VALIDATORS.
    `trigger`    a measurand whose presence indicates this physics applies.
    `inputs`     validator-kwarg name -> (measurand, expected_unit) to resolve+convert.
    `extra`      fixed non-quantity kwargs (config the validator needs, e.g. an end
                 condition or a wall model) — declared defaults, refined later from
                 spec Decisions.
    """

    name: str
    validator: str
    trigger: str
    inputs: dict[str, tuple[str, str]]
    extra: dict = field(default_factory=dict)


# The catalog: which checks the engine knows how to assemble from declared measurands.
# Extensible — a new validator becomes auto-selectable by adding a recipe here.
RECIPES: list[CheckRecipe] = [
    CheckRecipe(
        name="shaft torsion", validator="torsion", trigger="shaft.torque",
        inputs={
            "torque": ("shaft.torque", "N*mm"),
            "diameter": ("shaft.diameter", "mm"),
            "length": ("shaft.length", "mm"),
            "shear_modulus_g": ("material.shear_modulus", "MPa"),
            "shear_strength": ("material.shear_strength", "MPa"),
        },
    ),
    CheckRecipe(
        name="fatigue (Goodman)", validator="fatigue", trigger="fatigue.stress_amplitude",
        inputs={
            "stress_amplitude": ("fatigue.stress_amplitude", "MPa"),
            "mean_stress": ("fatigue.mean_stress", "MPa"),
            "uts": ("material.uts", "MPa"),
            "endurance": ("material.endurance_limit", "MPa"),
        },
    ),
    CheckRecipe(
        name="column buckling", validator="buckling", trigger="column.axial_load",
        inputs={
            "applied_load": ("column.axial_load", "N"),
            "e_modulus": ("material.elastic_modulus", "MPa"),
            "inertia": ("column.second_moment_area", "mm^4"),
            "length": ("column.length", "mm"),
            "area": ("column.cross_section_area", "mm^2"),
            "yield_strength": ("material.yield_strength", "MPa"),
        },
        extra={"end_condition": "pinned-pinned"},
    ),
    CheckRecipe(
        name="pressure vessel", validator="pressure_vessel", trigger="vessel.pressure",
        inputs={
            "pressure": ("vessel.pressure", "MPa"),
            "r_inner": ("vessel.inner_radius", "mm"),
            "thickness": ("vessel.wall_thickness", "mm"),
            "yield_strength": ("material.yield_strength", "MPa"),
        },
        extra={"model": "thin"},
    ),
    CheckRecipe(
        name="resonance", validator="resonance", trigger="vibration.excitation_frequency",
        inputs={
            "first_natural_hz": ("vibration.first_natural_frequency", "Hz"),
            "excitation_hz": ("vibration.excitation_frequency", "Hz"),
        },
    ),
    CheckRecipe(
        name="notch fatigue", validator="notch_fatigue", trigger="notch.kt",
        inputs={
            "nominal_alternating_stress": ("notch.nominal_alternating_stress", "MPa"),
            "kt": ("notch.kt", "1"),
            "notch_radius": ("notch.radius", "mm"),
            "peterson_constant_a": ("material.peterson_constant", "mm"),
            "smooth_endurance_se": ("material.endurance_limit", "MPa"),
        },
    ),
]


def _measurand_map(spec: Specification) -> dict[str, Quantity]:
    """Index a spec's quantities by their declared measurand (first wins; GATE γ C-17
    guarantees same-measurand quantities agree, so the choice is immaterial)."""
    out: dict[str, Quantity] = {}
    for q in spec.quantities:
        if q.measurand and q.measurand not in out:
            out[q.measurand] = q
    return out


def _resolve(by_measurand: dict[str, Quantity], measurand: str, unit: str):
    """Return (value_in_`unit`, None) or (None, reason). Converts soundly via units.py;
    refuses (reason) on a missing quantity, a dimension mismatch, or an opaque unit."""
    q = by_measurand.get(measurand)
    if q is None:
        return None, f"no quantity tagged measurand {measurand!r}"
    try:
        if parse_unit(q.unit) != parse_unit(unit):
            return None, f"{measurand}: unit {q.unit!r} not dimensionally {unit!r}"
        scale_from, scale_to = unit_scale(q.unit), unit_scale(unit)
    except UnitError as exc:
        return None, f"{measurand}: {exc}"
    if scale_from is None or scale_to is None:
        return None, f"{measurand}: opaque unit {q.unit!r} — refusing to convert"
    return q.value * scale_from / scale_to, None


def select_physics_checks(spec: Specification) -> tuple[list[PhysicsCheck], list[str]]:
    """Build the applicable physics checks from a Specification's measurand-tagged
    quantities.

    Returns ``(checks, gaps)``: `checks` are ready ``PhysicsCheck``s (inputs resolved and
    unit-converted); `gaps` describe physics that is INDICATED (trigger present) but cannot
    be run (a missing/incompatible/opaque input), so an unrunnable check is surfaced rather
    than dropped. A recipe whose trigger is absent contributes neither. Deterministic.
    """
    by_measurand = _measurand_map(spec)
    checks: list[PhysicsCheck] = []
    gaps: list[str] = []
    for recipe in RECIPES:
        if recipe.trigger not in by_measurand:
            continue                                # this physics is simply not present
        inputs = dict(recipe.extra)
        problems: list[str] = []
        for arg, (measurand, unit) in recipe.inputs.items():
            value, reason = _resolve(by_measurand, measurand, unit)
            if reason is not None:
                problems.append(reason)
            else:
                inputs[arg] = value
        if problems:
            gaps.append(
                f"{recipe.name} ({recipe.validator}) indicated by {recipe.trigger!r} "
                f"but cannot run: {'; '.join(problems)}"
            )
        else:
            checks.append(PhysicsCheck(recipe.name, recipe.validator, inputs))
    return checks, gaps


def evaluate_spec_physics(spec: Specification) -> dict:
    """Full spec→verdict flow: select the applicable checks, run GATE δ-physics on them,
    and return ``{"gate": GateResult, "checks": [...], "gaps": [...]}``. The gate verdict
    reflects only the checks that could be assembled; `gaps` lists indicated-but-unrunnable
    physics (which a caller may treat as a soft fail / a reason to enrich the spec)."""
    checks, gaps = select_physics_checks(spec)
    gate: GateResult = gate_delta_physics(checks)
    return {"gate": gate, "checks": checks, "gaps": gaps}
