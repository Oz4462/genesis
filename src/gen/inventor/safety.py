"""safety — the first-class, FIRST-STEP safety screen + staged-test ladder for the invention loop (TS).

Safety is not an afterthought: it runs BEFORE the proposer is ever called (the loop's ``safety_screen`` slot),
so a weapons / biosecurity brief never even generates concepts. The screen is a DETERMINISTIC rule table — no
LLM, no model judgement that could be coaxed — refusing structurally dangerous intents (bio/chemical weapons,
mass-casualty munitions, untraceable harm). It is honest about its scope: a structural keyword screen is a
NECESSARY first gate, not a complete safety proof; it refuses the obvious and is auditable line by line.

For an ALLOWED physical invention, :func:`build_invention_ladder` attaches a staged test plan (model → sim →
bench → supervised field) built from the existing ``grenzverschiebung.safety_ladder`` ``SafetyStage`` types —
so a buildable invention carries a graded, abort-gated path to realization rather than a leap to a manned test.
Deterministic, offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..grenzverschiebung.safety_ladder import SafetyStage, SafetyStagePlan
from .brief import InventionBrief

#: The deterministic refusal table: category -> the phrases (lowercased) that trigger a hard refusal. Kept
#: explicit and auditable; extend by adding rows, never by a model's discretion.
REFUSAL_RULES: dict[str, tuple[str, ...]] = {
    "bioweapon": (
        "nerve agent", "nervengift", "bioweapon", "biowaffe", "biological weapon", "pathogen enhancement",
        "gain of function", "gain-of-function", "enhance virulence", "weaponize", "weaponize a virus",
        "anthrax", "select agent", "toxin weapon", "aerosolize a pathogen",
    ),
    "chemical_weapon": (
        "chemical weapon", "chemiewaffe", "sarin", "vx nerve", "mustard gas", "nerve gas", "chlorine gas weapon",
        "tabun", "soman", "novichok",
    ),
    "mass_casualty": (
        "antipersonnel mine", "landmine to kill", "ied", "improvised explosive device", "explosive vest",
        "dirty bomb", "bomb to kill", "maximize casualties", "mass casualty", "chemical attack on",
    ),
    "untraceable_harm": (
        "untraceable poison", "undetectable poison", "assassinate", "covertly kill", "poison someone",
    ),
}


@dataclass(frozen=True)
class SafetyVerdict:
    """The screen's verdict. ``refused`` stops the loop before generation; ``category`` and ``matched`` name
    exactly which rule fired (auditable); ``reason`` is the human explanation. An allowed brief has
    ``refused=False`` and no category."""

    refused: bool
    category: Optional[str]
    matched: Optional[str]
    reason: str


def screen_brief(brief: InventionBrief) -> SafetyVerdict:
    """Run the deterministic refusal table over the brief's field + goal + constraints. Returns a refusing
    :class:`SafetyVerdict` naming the category and the matched phrase on the FIRST rule hit, else an allowing
    verdict. No LLM — a rule, not a judgement. Honest scope: this refuses obvious dangerous intent; it is the
    first gate, not a guarantee of benign use."""
    haystack = " ".join([brief.field, brief.goal, *brief.constraints]).lower()
    for category, phrases in REFUSAL_RULES.items():
        for phrase in phrases:
            if phrase in haystack:
                return SafetyVerdict(
                    refused=True, category=category, matched=phrase,
                    reason=f"strukturell abgelehnt: '{phrase}' ({category}) — Waffen-/Biosecurity-Screen "
                           f"vor jeder Konzept-Erzeugung")
    return SafetyVerdict(refused=False, category=None, matched=None,
                         reason="kein struktureller Refusal-Treffer (Erstgate bestanden; keine Sicherheitsgarantie)")


def safety_gate(brief: InventionBrief) -> bool:
    """The loop's ``safety_screen`` adapter: True = allowed (the proposer may run), False = refused. Wire as
    ``run_invention(..., safety_screen=safety_gate)`` so a dangerous brief never reaches generation."""
    return not screen_brief(brief).refused


def build_invention_ladder(brief: InventionBrief, *, run_id: Optional[str] = None) -> SafetyStagePlan:
    """A graded, abort-gated test ladder for an ALLOWED physical invention: model → simulation → bench →
    supervised field, each with a safe form, a gate, measurement criteria, and abort conditions. Composes the
    existing ``SafetyStage``/``SafetyStagePlan`` types. Raises ValueError if the brief would be refused — a
    dangerous intent gets NO ladder, it gets stopped."""
    verdict = screen_brief(brief)
    if verdict.refused:
        raise ValueError(f"cannot build a safety ladder for a refused brief: {verdict.reason}")
    stages = [
        SafetyStage(
            name="S0 Modell", beschreibung="Geometrie + δ-Physik-Gate, rein rechnerisch.",
            safe_form="Modell", gate="δ-Physik-Gate bestanden, keine offenen Lücken",
            messkriterien=["physics_verified == True", "Lücken == 0"], abbruch=["Gate scheitert"]),
        SafetyStage(
            name="S1 Simulation", beschreibung="Dynamik-Simulation (RK4/PyBullet/MuJoCo-Backend).",
            safe_form="Simulation", gate="Sim reproduziert das Soll-Verhalten innerhalb Toleranz",
            messkriterien=["Sim-Abweichung < Toleranz"], abbruch=["Instabilität", "Energie nicht erhalten"]),
        SafetyStage(
            name="S2 Prüfstand", beschreibung="Gedrucktes Bauteil am Prüfstand, ohne Mensch in der Gefahrenzone.",
            safe_form="Prüfstand", gate="Bauteil hält die gemessene Last über die Auslegung",
            messkriterien=["gemessene Marge >= Auslegungsmarge"], abbruch=["Bruch unter Auslegungslast"]),
        SafetyStage(
            name="S3 Überwachter Feldtest", beschreibung="Betrieb unter Aufsicht, mit Distanz/Schutz und Abbruch.",
            safe_form="unbemannt/gesichert", gate="Stabiler Betrieb über die Testdauer mit aktivem Abort",
            messkriterien=["keine unerwarteten Ausfälle", "Abort funktioniert"],
            abbruch=["unerwarteter Ausfall", "Abort ausgelöst"]),
    ]
    return SafetyStagePlan(
        source_traum=brief.field,
        stages=stages,
        zusammenfassung="4-stufige Leiter (S0 Modell → S3 überwachter Feldtest), jede Stufe mit safe form, "
                        "Gate, Messkriterien und Abbruch — keine Stufe ohne bestandene Vorstufe.",
        run_id=run_id or brief.run_id)


__all__ = ["SafetyVerdict", "REFUSAL_RULES", "screen_brief", "safety_gate", "build_invention_ladder"]
