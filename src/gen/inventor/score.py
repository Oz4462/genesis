"""score — the 5-axis Pareto scoring of grounded inventions (over the verified inverse_design seam).

An invention is not one number: it trades COST against MASS against PERFORMANCE against COMPLEXITY against
NOVELTY. The honest answer is the Pareto front, so this module scores each invention on five axes and keeps
exactly the non-dominated ones via the verified ``inventor.optimize.ParetoOptimizer`` (which wraps
``inverse_design.dominates``). Every axis is computed deterministically from the grounded Specification, with
honest neutral fallbacks where a value is not declared (never a fabricated favourable number).

Axes (direction): cost↓, mass↓, performance↑, complexity↓, novelty↑. ``novelty`` is neutral (0.5) until Phase N
fills it — scoring composes with, but does not fake, the novelty verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from ..inverse_design import DesignObjective, InverseDesignGoal, ObjectiveDirection
from ..core.state import Specification
from .brief import Invention
from .optimize import ParetoOptimizer

#: The fixed 5-axis goal. cost/mass/complexity are MINIMIZED, performance/novelty MAXIMIZED.
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
    the resonance quantities are absent — neutral, not a claimed margin."""
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


def inventions_to_pareto_front(
    inventions: Sequence[Invention],
    front: Optional[Sequence[Invention]] = None,
    *,
    score: Callable[[Invention], ScoreVector] = score_invention,
) -> "ParetoFront":
    """Bridge inventor 5-axis scores → HORIZON :class:`ParetoFront` for CLI / γ+ consumers.

    Honesty contract (self-improve 2026-07-14):
    - ``objective_values`` come from :func:`score_invention` **proxies** (BOM cost, mass
      measurand, modal margin, quantity count, novelty map) — **not** from
      ``inverse_design.objective_values`` recompute against quantity ids matching
      :data:`INVENTION_GOAL`.
    - ``produced_by`` is ``inventor.score_proxy`` so consumers never mistake this for a
      full γ+ quantity-recomputed front.
    - Ungrounded inventions are excluded; empty pool gets an explicit abstention gap.
    """
    from ..core.state import DesignCandidate, ParetoFront

    evaluated: list[DesignCandidate] = []
    for inv in inventions:
        if not inv.grounded or inv.specification is None:
            continue
        try:
            sv = score(inv)
        except ValueError:
            continue
        evaluated.append(
            DesignCandidate(
                id=inv.concept.id,
                specification=inv.specification,
                objective_values=sv.as_objectives(),
            )
        )

    if front is None:
        front_ids = {i.concept.id for i in pareto_inventions(inventions, score=score)}
    else:
        front_ids = {i.concept.id for i in front}
    candidates = [c for c in evaluated if c.id in front_ids]

    gaps: list[str] = []
    ungrounded = sum(1 for i in inventions if not (i.grounded and i.specification is not None))
    if ungrounded:
        gaps.append(f"{ungrounded} invention(s) ungrounded — excluded from γ+ pool")
    if not evaluated:
        gaps.append("No grounded inventions for γ+ Pareto (honest empty front)")
    gaps.append(
        "objective values from inventor 5-axis score proxies "
        "(not quantity-id recompute via inverse_design.objective_values)"
    )

    return ParetoFront(
        goal=INVENTION_GOAL,
        candidates=candidates,
        evaluated_candidates=evaluated,
        gaps=gaps,
        produced_by="inventor.score_proxy",
    )


__all__ = [
    "ScoreVector",
    "INVENTION_GOAL",
    "score_invention",
    "pareto_inventions",
    "inventions_to_pareto_front",
]
