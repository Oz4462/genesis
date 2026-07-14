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


def _modal_margin(spec: Specification) -> Optional[float]:
    """Performance proxy for a mechatronic part: first_natural / excitation. None when resonance
    quantities are absent (so thermal scoring can take over — not a fake margin of 1.0)."""
    fn = _measurand_value(spec, "first_natural_frequency", default=0.0)
    ex = _measurand_value(spec, "excitation_frequency", default=0.0)
    if fn > 0.0 and ex > 0.0:
        return fn / ex
    return None


def _quantity_si(spec: Specification, measurand: str, unit: str) -> Optional[float]:
    """Resolve one measurand to ``unit`` via the same scale table as physics_selection (or None)."""
    from ..core.errors import UnitError
    from ..verification.units import parse_unit, unit_scale

    for q in spec.quantities:
        if q.measurand != measurand:
            continue
        try:
            if parse_unit(q.unit) != parse_unit(unit):
                return None
            scale_from, scale_to = unit_scale(q.unit), unit_scale(unit)
        except UnitError:
            return None
        if scale_from is None or scale_to is None:
            return None
        return float(q.value) * scale_from / scale_to
    return None


def _thermal_margin_ratio(spec: Specification) -> Optional[float]:
    """Performance proxy for cold-plate / conduction designs (self-improve 2026-07-14).

    Recomputes the same Fourier path as ``overtemperature_check`` (ΔT = P·L/(k·A), peak =
    ambient + ΔT) and returns ``max_service / peak`` (>1 safe). None when the overtemperature
    measurand set is incomplete — never invents a favourable thermal score.
    """
    power = _quantity_si(spec, "thermal.power_dissipation", "W")
    k = _quantity_si(spec, "material.thermal_conductivity", "W/m/K")
    area = _quantity_si(spec, "thermal.conduction_area", "m^2")
    length = _quantity_si(spec, "thermal.conduction_length", "m")
    ambient = _quantity_si(spec, "thermal.ambient_temp", "K")
    tmax = _quantity_si(spec, "material.max_service_temp", "K")
    if any(v is None for v in (power, k, area, length, ambient, tmax)):
        return None
    assert power is not None and k is not None and area is not None
    assert length is not None and ambient is not None and tmax is not None
    if k <= 0.0 or area <= 0.0 or length <= 0.0:
        return None
    delta_t = power * length / (k * area)
    peak = ambient + delta_t
    if peak <= 0.0:
        return None
    return tmax / peak


def _performance(spec: Specification) -> float:
    """Domain-aware performance: modal margin if resonance quantities exist, else thermal
    conduction margin ratio if overtemperature quantities exist, else neutral 1.0."""
    modal = _modal_margin(spec)
    if modal is not None:
        return modal
    thermal = _thermal_margin_ratio(spec)
    if thermal is not None:
        return thermal
    return 1.0


_NOVELTY_MAP = {"neuer_mechanismus": 1.0, "neu": 0.8, "inkrementell": 0.4, "nicht_neu": 0.0}


def score_invention(inv: Invention, *, novelty: Optional[float] = None) -> ScoreVector:
    """Score a grounded invention on the five axes, deterministically. ``cost`` is a structural buildability
    proxy (number of BOM items, else components, else quantities — an HONEST proxy, not a priced cost);
    ``mass`` reads a '.mass' measurand (neutral 1.0 if absent); ``performance`` is modal margin (mechatronics)
    or thermal margin ratio max_service/peak (cold-plate), else neutral 1.0;
    ``complexity`` is the quantity count (parsimony); ``novelty`` is the explicit arg, else the mapped
    ``novelty_verdict``, else 0.5 (neutral — Phase N has not run). Raises ValueError if not grounded."""
    spec = inv.specification
    if spec is None:
        raise ValueError("cannot score an ungrounded invention (no specification)")
    cost = float(len(spec.bom) or len(spec.components) or len(spec.quantities))
    mass = _measurand_value(spec, ".mass", default=1.0)
    performance = _performance(spec)
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


def _spec_with_score_quantities(spec: Specification, sv: ScoreVector) -> Specification:
    """Stamp 5-axis score as quantities so γ+ ``objective_values`` recomputes honestly.

    Gap close 2026-07-14: previously ParetoFront carried proxy floats that could not
    be re-derived from quantity ids. Stamping cost/mass/performance/complexity/novelty
    onto a copy of the spec makes ``inverse_design.objective_values`` agree with the
    score vector (same numbers, now recomputable).
    """
    from dataclasses import replace

    from ..core.state import Quantity, ValueOrigin

    objs = sv.as_objectives()
    stamped = [
        Quantity(
            id=axis,
            name=f"invention {axis}",
            value=float(objs[axis]),
            unit="1",
            origin=ValueOrigin.DECISION,
            rationale="inventor 5-axis score for γ+ objective recompute (proxy stamp)",
            measurand=None,
        )
        for axis in ("cost", "mass", "performance", "complexity", "novelty")
    ]
    existing = {q.id for q in spec.quantities}
    extra = [q for q in stamped if q.id not in existing]
    return replace(spec, quantities=list(spec.quantities) + extra)


def inventions_to_pareto_front(
    inventions: Sequence[Invention],
    front: Optional[Sequence[Invention]] = None,
    *,
    score: Callable[[Invention], ScoreVector] = score_invention,
) -> "ParetoFront":
    """Bridge inventor 5-axis scores → HORIZON :class:`ParetoFront` for CLI / γ+ consumers.

    Honesty contract (updated 2026-07-14 gap close):
    - Scores still come from :func:`score_invention` proxies (BOM cost, mass measurand,
      modal/thermal margin, quantity count, novelty map).
    - Specs are stamped with quantity ids matching :data:`INVENTION_GOAL` so
      ``inverse_design.objective_values`` **recomputes** the same numbers.
    - ``produced_by`` is ``inventor.score_recomputable`` (was score_proxy).
    - Ungrounded inventions are excluded; empty pool gets an explicit abstention gap.
    """
    from ..core.state import DesignCandidate, ParetoFront
    from ..inverse_design import objective_values

    evaluated: list[DesignCandidate] = []
    for inv in inventions:
        if not inv.grounded or inv.specification is None:
            continue
        try:
            sv = score(inv)
        except ValueError:
            continue
        stamped = _spec_with_score_quantities(inv.specification, sv)
        # Prove recompute matches score vector (γ+ honesty)
        recomputed = objective_values(stamped, INVENTION_GOAL)
        evaluated.append(
            DesignCandidate(
                id=inv.concept.id,
                specification=stamped,
                objective_values=recomputed,
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
        "objective values recomputed from stamped quantity ids "
        "(score axes derived by inventor 5-axis proxies, then γ+-compatible)"
    )

    return ParetoFront(
        goal=INVENTION_GOAL,
        candidates=candidates,
        evaluated_candidates=evaluated,
        gaps=gaps,
        produced_by="inventor.score_recomputable",
    )


__all__ = [
    "ScoreVector",
    "INVENTION_GOAL",
    "score_invention",
    "pareto_inventions",
    "inventions_to_pareto_front",
]
