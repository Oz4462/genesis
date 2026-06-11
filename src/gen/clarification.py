"""Proactive clarification — detect underspecification and ask targeted questions (research #3).

A real product cannot run on a vague idea: SOTA work ("Clarify Before You Draw"; Ask-before-
Plan; Active Task Disambiguation) shows an agent must DETECT what is underspecified and ask
the few highest-value questions BEFORE producing a solution — and avoid needless questions
that frustrate. This module is the deterministic, offline core of that: it inspects a
Specification for physics that is INDICATED but cannot be evaluated, and turns each gap into a
prioritized clarifying question.

The detection reuses the measurand machinery (physics_selection): a recipe whose TRIGGER
measurand is present means the design has that physics; if one of its input measurands is
absent, the design is underspecified for that check — and the missing input is exactly what to
ask for. Questions are prioritized by an EVPI proxy (Expected Value of Perfect Information): a
missing quantity that would unblock SEVERAL checks is asked first, and each measurand is asked
exactly once (no redundant questions). Physics that is simply not present (no trigger) is never
asked about — the agent does not interrogate the user about a shaft when there is no shaft.

So clarification is honest by construction: it asks only for inputs a declared physics concern
genuinely needs, ranked by how much they unblock. Detecting ambiguity in raw free-text ideas
(distinct plausible interpretations) is the LLM-driven part that plugs in upstream; this layer
handles structured underspecification deterministically. Offline, pure functions.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .core.state import Specification
from .physics_selection import RECIPES

# Human-readable question per measurand the recipes need. A measurand without a template
# gets a generic, honest prompt (it never invents a misleading specific question).
_QUESTION_TEMPLATES: dict[str, str] = {
    "shaft.torque": "What torque does the shaft transmit (e.g. in N*m)?",
    "shaft.diameter": "What is the shaft diameter (mm)?",
    "shaft.length": "What is the shaft length between supports (mm)?",
    "material.shear_modulus": "What is the material's shear modulus G (MPa)?",
    "material.shear_strength": "What is the material's shear strength (MPa)?",
    "material.elastic_modulus": "What is the material's elastic modulus E (MPa)?",
    "material.yield_strength": "What is the material's yield strength (MPa)?",
    "material.uts": "What is the material's ultimate tensile strength (MPa)?",
    "material.endurance_limit": "What is the material's endurance (fatigue) limit (MPa)?",
    "material.peterson_constant": "What is Peterson's notch-sensitivity constant a (mm) for the material?",
    "fatigue.stress_amplitude": "What is the cyclic stress amplitude (MPa)?",
    "fatigue.mean_stress": "What is the mean (steady) stress of the load cycle (MPa)?",
    "column.axial_load": "What axial compressive load does the column carry (N)?",
    "column.second_moment_area": "What is the column's second moment of area I (mm^4)?",
    "column.length": "What is the column's effective length (mm)?",
    "column.cross_section_area": "What is the column's cross-section area (mm^2)?",
    "vessel.pressure": "What is the internal pressure (MPa)?",
    "vessel.inner_radius": "What is the vessel's inner radius (mm)?",
    "vessel.wall_thickness": "What is the wall thickness (mm)?",
    "vibration.excitation_frequency": "What is the operating / forcing frequency (Hz)?",
    "vibration.first_natural_frequency": "What is the part's first natural frequency (Hz)?",
    "notch.kt": "What is the stress concentration factor Kt at the notch?",
    "notch.nominal_alternating_stress": "What is the nominal alternating stress at the notch (MPa)?",
    "notch.radius": "What is the notch root radius (mm)?",
}


@dataclass(frozen=True)
class ClarifyingQuestion:
    """One targeted question to resolve underspecification.

    `measurand`  the missing quantity tag the answer would supply.
    `question`   the human-readable prompt.
    `unblocks`   the check names this answer would make runnable (sorted).
    `priority`   EVPI proxy = how many checks the answer unblocks (higher = ask first).
    """

    measurand: str
    question: str
    unblocks: tuple[str, ...]
    priority: int


def _question_for(measurand: str) -> str:
    return _QUESTION_TEMPLATES.get(measurand, f"Please provide a value for {measurand!r}.")


def clarifying_questions(spec: Specification, *, top_k: int | None = None) -> list[ClarifyingQuestion]:
    """The prioritized clarifying questions for a Specification's underspecified physics.

    For every recipe whose TRIGGER measurand is present (so the physics is indicated), each
    missing input measurand becomes a question, aggregated so a measurand needed by several
    checks is asked ONCE with a higher `priority`. Returns the questions sorted by priority
    (then measurand, for determinism); `top_k` caps the list to the most valuable few (None =
    all). A fully specified or physics-free spec yields an empty list. Deterministic.
    """
    present = {q.measurand for q in spec.quantities if q.measurand}
    missing_to_checks: dict[str, set[str]] = defaultdict(set)
    for recipe in RECIPES:
        if recipe.trigger not in present:
            continue                              # this physics is not indicated — don't ask
        for _arg, (measurand, _unit) in recipe.inputs.items():
            if measurand not in present:
                missing_to_checks[measurand].add(recipe.name)

    questions = [
        ClarifyingQuestion(
            measurand=measurand,
            question=_question_for(measurand),
            unblocks=tuple(sorted(checks)),
            priority=len(checks),
        )
        for measurand, checks in missing_to_checks.items()
    ]
    questions.sort(key=lambda q: (-q.priority, q.measurand))
    return questions if top_k is None else questions[:top_k]


def is_underspecified(spec: Specification) -> bool:
    """True if any indicated physics is missing an input — i.e. clarification is warranted
    before the design can be fully evaluated."""
    return bool(clarifying_questions(spec))
