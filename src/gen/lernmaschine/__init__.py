"""Lern- und Verbesserungsmaschine (Meta 8-Schritt-Engine per GENESIS_PLATFORM_PLAN.md §3.8).

Erster Stein: deterministischer Cycle der Lücken erkennt (aus open_luecken / specs), Verbesserung vorschlägt, Quellen sammelt, "baut" (via existierende Builder), Gate erzeugt, mit Tests "beweist", in Wissensbasis persistiert (real store + Provenance), und den Lern-Delta zurückgibt.

Jetpack-Kanon + generischer Fallback. Keine LLM im Kern. Naht zu Pipelines (Integrator/Assembly), CAD, Wissensbasis, prior Grenz + Learning.
"""

from .engine import (
    LearningStep,
    LearningCycleResult,
    run_8_step_learning_cycle,
    apply_learning_feedback,
    LearningApplicationResult,
    apply_learning_to_realization,
)

__all__ = [
    "LearningStep",
    "LearningCycleResult",
    "run_8_step_learning_cycle",
    "apply_learning_feedback",
    "LearningApplicationResult",
    "apply_learning_to_realization",
    "apply_learning_to_frontier",
]
