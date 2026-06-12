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
from dataclasses import dataclass, replace

from .core.state import Quantity, Specification, ValueOrigin
from .physics_selection import RECIPES

# Human-readable question per measurand the recipes need (German — the questions
# are user-facing results, PHASE_DELTA §57). A measurand without a template gets a
# generic, honest prompt (it never invents a misleading specific question).
_QUESTION_TEMPLATES: dict[str, str] = {
    "shaft.torque": "Welches Drehmoment überträgt die Welle (z. B. in N*m)?",
    "shaft.diameter": "Wie groß ist der Wellendurchmesser (mm)?",
    "shaft.length": "Wie lang ist die Welle zwischen den Lagern (mm)?",
    "material.shear_modulus": "Wie groß ist der Schubmodul G des Materials (MPa)?",
    "material.shear_strength": "Wie groß ist die Scherfestigkeit des Materials (MPa)?",
    "material.elastic_modulus": "Wie groß ist der Elastizitätsmodul E des Materials (MPa)?",
    "material.yield_strength": "Wie groß ist die Streckgrenze des Materials (MPa)?",
    "material.uts": "Wie groß ist die Zugfestigkeit des Materials (MPa)?",
    "material.endurance_limit": "Wie groß ist die Dauerfestigkeit (Ermüdungsgrenze) des Materials (MPa)?",
    "material.peterson_constant": "Wie groß ist Petersons Kerbempfindlichkeits-Konstante a (mm) für das Material?",
    "fatigue.stress_amplitude": "Wie groß ist die zyklische Spannungsamplitude (MPa)?",
    "fatigue.mean_stress": "Wie groß ist die mittlere (statische) Spannung des Lastzyklus (MPa)?",
    "column.axial_load": "Welche axiale Drucklast trägt die Stütze (N)?",
    "column.second_moment_area": "Wie groß ist das Flächenträgheitsmoment I der Stütze (mm^4)?",
    "column.length": "Wie groß ist die wirksame Knicklänge der Stütze (mm)?",
    "column.cross_section_area": "Wie groß ist die Querschnittsfläche der Stütze (mm^2)?",
    "vessel.pressure": "Wie hoch ist der Innendruck (MPa)?",
    "vessel.inner_radius": "Wie groß ist der Innenradius des Behälters (mm)?",
    "vessel.wall_thickness": "Wie dick ist die Wand (mm)?",
    "vibration.excitation_frequency": "Wie hoch ist die Betriebs-/Anregungsfrequenz (Hz)?",
    "vibration.first_natural_frequency": "Wie hoch ist die erste Eigenfrequenz des Teils (Hz)?",
    "notch.kt": "Wie groß ist der Spannungskonzentrationsfaktor Kt an der Kerbe?",
    "notch.nominal_alternating_stress": "Wie groß ist die nominale Wechselspannung an der Kerbe (MPa)?",
    "notch.radius": "Wie groß ist der Kerbgrundradius (mm)?",
    # printability (PHASE_DELTA §52)
    "feature.bridge_span": "Wie lang ist die längste freitragende Brücke im Teil (mm)?",
    "fit.clearance": "Wie groß ist das vorgesehene Passungsspiel (mm)?",
    "feature.pin_diameter": "Wie dick ist der dünnste gedruckte Pin (mm)?",
    "feature.thread_major_diameter": "Wie groß ist der Gewinde-Nenndurchmesser (mm)?",
    "feature.unsupported_wall_thickness": "Wie dick ist die dünnste freistehende Wand (mm)?",
    "feature.emboss_width": "Wie breit ist das feinste erhabene/vertiefte Detail (mm)?",
    "print.stress_across_layers": "Welche Zugspannung wirkt quer zu den Druckschichten (MPa)?",
    # flight (PHASE_DELTA §54)
    "vehicle.mass": "Wie schwer ist das Fluggerät insgesamt (kg)?",
    "rotor.disk_area": "Wie groß ist die gesamte Rotorkreisfläche (m^2)?",
    "rotor.count": "Wie viele Rotoren hat das Fluggerät?",
    "rotor.max_total_thrust": "Wie groß ist der maximale Gesamtschub aller Rotoren (N)?",
    "battery.capacity": "Wie groß ist die Akkukapazität (Wh)?",
    "battery.capacity_ah": "Wie groß ist die Akkukapazität (Ah)?",
    "battery.voltage": "Wie hoch ist die Akkuspannung (V)?",
    "battery.c_rating": "Welches C-Rating hat der Akku?",
    "flight.hover_power": "Wie viel Leistung braucht das Schweben (W)?",
    "flight.required_endurance": "Wie lange soll der Flug mindestens dauern (min)?",
    "flight.max_power": "Wie groß ist die maximale Leistungsaufnahme (W)?",
    "esc.current_limit": "Wie hoch ist das Dauerstrom-Limit des Reglers/ESC (A)?",
    "control.attitude_kp": "Wie groß ist die Proportionalverstärkung Kp der Lageregelung (N*m)?",
    "control.attitude_kd": "Wie groß ist die Dämpfungsverstärkung Kd der Lageregelung (N*m*s)?",
    "vehicle.attitude_inertia": "Wie groß ist das Massenträgheitsmoment um die Regelachse (kg*m^2)?",
    # crypto (PHASE_DELTA §55)
    "crypto.nonce_bits": "Wie viele Bits hat die Nonce / der IV?",
    "crypto.messages_per_key": "Wie viele Nachrichten werden pro Schlüssel verschlüsselt?",
    "crypto.symmetric_key_bits": "Wie viele Bits hat der symmetrische Schlüssel?",
    "crypto.rsa_modulus_bits": "Wie viele Bits hat der RSA-Modulus?",
    "crypto.ecc_key_bits": "Wie viele Bits hat der ECC-Schlüssel?",
    "crypto.gcm_invocations": "Wie oft wird GCM mit demselben Schlüssel aufgerufen?",
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
    return _QUESTION_TEMPLATES.get(measurand, f"Bitte gib einen Wert für {measurand!r} an.")


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


def expected_unit(measurand: str) -> str | None:
    """The unit the recipes expect for `measurand` (a hint for an answer form), or None
    if no recipe consumes it."""
    for recipe in RECIPES:
        for _arg, (m, unit) in recipe.inputs.items():
            if m == measurand:
                return unit
    return None


def apply_answers(
    spec: Specification, answers: dict[str, tuple[float, str]]
) -> Specification:
    """Fold the human's clarification answers into the spec — each as a DECLARED
    DECISION quantity carrying its measurand (the same provenance discipline as every
    other value: the human's answer is a design decision, not a fact).

    `answers` maps measurand -> (value, unit). Only answers for measurands the spec does
    NOT already declare are added (an existing declaration is never silently overwritten);
    the unit is taken as declared — the selection layer converts soundly and surfaces a
    dimension mismatch as a gap rather than guessing. Returns a NEW Specification (the
    input is not mutated). Deterministic.
    """
    present = {q.measurand for q in spec.quantities if q.measurand}
    new_quantities = list(spec.quantities)
    for i, (measurand, (value, unit)) in enumerate(sorted(answers.items())):
        if measurand in present:
            continue
        qid = f"q_clarified_{i}_{measurand.replace('.', '_')}"
        new_quantities.append(Quantity(
            id=qid, name=f"geklärt: {measurand}", value=float(value), unit=unit,
            origin=ValueOrigin.DECISION,
            rationale="vom Menschen im Klärungsdialog angegeben",
            measurand=measurand,
        ))
    return replace(spec, quantities=new_quantities)
