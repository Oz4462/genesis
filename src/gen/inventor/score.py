"""score — the 5-axis Pareto scoring of grounded inventions (over the verified inverse_design seam).

An invention is not one number: it trades COST against MASS against PERFORMANCE against COMPLEXITY against
NOVELTY. The honest answer is the Pareto front, so this module scores each invention on five axes and keeps
exactly the non-dominated ones via the verified ``inventor.optimize.ParetoOptimizer`` (which wraps
``inverse_design.dominates``). Every axis is computed deterministically from the grounded Specification, with
honest neutral fallbacks where a value is not declared (never a fabricated favourable number).

Axes (direction): cost↓, mass↓, performance↑, complexity↓, novelty↑. ``novelty`` is neutral (0.5) until Phase N
fills it — scoring composes with, but does not fake, the novelty verdict.

γ+ bridge: INVENTION_GOAL (this proxy) ↔ full ParetoFront via derive_goal in inventor/loop (and optimize seam).
Full path: δ-grounded specs → derive → real InverseDesignGoal → build_pareto_front (enforces δ+ assess + γ) → RunState attach.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from ..inverse_design import DesignObjective, InverseDesignGoal, ObjectiveDirection
from ..core.state import Specification
from .brief import Invention
from .optimize import ParetoOptimizer

#: The fixed 5-axis goal. cost/mass/complexity are MINIMIZED, performance/novelty MAXIMIZED.
# BRIDGE to full γ+: INVENTION_GOAL is proxy (synthetic qids for inventor 5-axis ScoreVector).
# Full γ+/δ+ uses derive_goal_from_spec(real_spec_from_δ_ground) → InverseDesignGoal (real quantity_ids/units)
# + DesignCandidate + build_pareto_front + gate_gamma_plus → ParetoFront attached to RunState (see loop.py:141).
# Proxy kept for backward (tests, archive, evolve use ScoreVector); bridge activated in inventor loop/optimize.
INVENTION_GOAL = InverseDesignGoal(
    id="invention", description="cost vs mass vs performance vs complexity vs novelty",
    objectives=[
        DesignObjective(id="cost", quantity_id="cost", direction=ObjectiveDirection.MINIMIZE, unit="1", target=None),
        DesignObjective(id="mass", quantity_id="mass", direction=ObjectiveDirection.MINIMIZE, unit="1", target=None),
        DesignObjective(id="performance", quantity_id="performance", direction=ObjectiveDirection.MAXIMIZE, unit="1", target=None),
        DesignObjective(id="complexity", quantity_id="complexity", direction=ObjectiveDirection.MINIMIZE, unit="1", target=None),
        DesignObjective(id="novelty", quantity_id="novelty", direction=ObjectiveDirection.MAXIMIZE, unit="1", target=None),
    ])


@dataclass(frozen=True)
class ScoreVector:
    """A grounded invention's five objective values. ``as_objectives`` maps to the dict ``ParetoOptimizer``
    and ``inverse_design.dominates`` consume."""

    cost: float
    mass: float
    performance: float
    complexity: float
    novelty: float

    def as_objectives(self) -> dict[str, float]:
        return {"cost": self.cost, "mass": self.mass, "performance": self.performance,
                "complexity": self.complexity, "novelty": self.novelty}


def _measurand_value(spec: Specification, suffix: str, default: float) -> float:
    """First quantity whose measurand ends with ``suffix`` (e.g. '.mass'), else ``default`` — an honest
    neutral fallback, not a fabricated favourable number."""
    for q in spec.quantities:
        if q.measurand and q.measurand.endswith(suffix):
            return float(q.value)
    return default


def _modal_margin(spec: Specification) -> float:
    """Performance proxy for a mechatronic part: first_natural / excitation (a modal safety margin). 1.0 when
    the resonance quantities are absent — neutral, not a claimed margin.
    Richer: prefer real δ-physics value from spec (e.g. 'performance' or 'margin' measurand) if present."""
    real = _measurand_value(spec, "performance", default=None)
    if real is not None:
        return float(real)
    real = _measurand_value(spec, "modal_margin", default=None)
    if real is not None:
        return float(real)
    fn = _measurand_value(spec, "first_natural_frequency", default=0.0)
    ex = _measurand_value(spec, "excitation_frequency", default=0.0)
    if fn > 0.0 and ex > 0.0:
        return fn / ex
    return 1.0


_NOVELTY_MAP = {"neuer_mechanismus": 1.0, "neu": 0.8, "inkrementell": 0.4, "nicht_neu": 0.0}


def score_invention(inv: Invention, *, novelty: Optional[float] = None) -> ScoreVector:
    """Score a grounded invention on the five axes, deterministically. ``cost`` is a structural buildability
    proxy (number of BOM items, else components, else quantities — an HONEST proxy, not a priced cost);
    ``mass`` reads a '.mass' measurand (neutral 1.0 if absent); ``performance`` is the modal margin;
    ``complexity`` is the quantity count (parsimony); ``novelty`` is the explicit arg, else the mapped
    ``novelty_verdict``, else 0.5 (neutral — Phase N has not run). Raises ValueError if not grounded."""
    spec = inv.specification
    if spec is None:
        raise ValueError("cannot score an ungrounded invention (no specification)")
    cost = float(len(spec.bom) or len(spec.components) or len(spec.quantities))
    mass = _measurand_value(spec, ".mass", default=1.0)
    performance = _modal_margin(spec)
    complexity = float(len(spec.quantities))
    if novelty is None:
        novelty = _NOVELTY_MAP.get(inv.novelty_verdict or "", 0.5)
    return ScoreVector(cost=cost, mass=mass, performance=performance, complexity=complexity, novelty=novelty)


def pareto_inventions(
    inventions: Sequence[Invention],
    *,
    score: Callable[[Invention], ScoreVector] = score_invention,
    optimizer: Optional[ParetoOptimizer] = None,
) -> list[Invention]:
    """Keep exactly the non-dominated grounded inventions, scored on the 5 axes. Ungrounded inventions (no
    physics-verified spec) are dropped first — an honest gap is not a Pareto competitor. ``score`` is
    injectable for testing. Deterministic, order-stable."""
    grounded = [i for i in inventions if i.grounded and i.specification is not None]
    opt = optimizer or ParetoOptimizer()
    return opt.select(grounded, lambda i: score(i).as_objectives(), INVENTION_GOAL)


__all__ = ["ScoreVector", "INVENTION_GOAL", "score_invention", "pareto_inventions"]
