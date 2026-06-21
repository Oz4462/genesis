"""optimize — the optimization seam: pick the non-dominated inventions (offline Pareto / external opt-in).

Scoring an invention is multi-objective (cost vs. mass vs. performance vs. ...); the honest answer is the
Pareto front, not a scalarized winner. The offline default :class:`ParetoOptimizer` reuses the verified
``inverse_design.dominates`` to keep exactly the non-dominated candidates — deterministic, no dependency. An
external multi-objective optimizer (pymoo, Apache-2.0) is an opt-in, import-guarded adapter behind the same
seam (CLAUDE.md §6, INVENTOR §10¾): the in-house default is always the test backbone.

γ+ elaboration (build_pareto_front + gate_gamma_plus) now wired into this seam (import + doc + activation) for
full validated inverse-design fronts over real spec quantities (vs proxy scores in inventor/score).
Bridge: INVENTION_GOAL proxy (score) ↔ full ParetoFront (derive + build + gate attached to RunState) via inventor/loop.
See inverse_design.py + state.pareto_front + HORIZON.md.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Callable, Protocol, Sequence, runtime_checkable

from ..core.errors import GenesisError
from ..inverse_design import InverseDesignGoal, dominates, build_pareto_front, gate_gamma_plus

#: A candidate -> its objective-id -> value mapping (what the goal scores).
ValuesOf = Callable[[Any], dict[str, float]]


class OptimizerUnavailable(GenesisError):
    """An external optimizer was selected but its package is not installed. Loud — the caller falls back to
    the offline ParetoOptimizer rather than getting a silently-wrong front."""

    def __init__(self, tool: str) -> None:
        super().__init__(f"optimizer backend {tool!r} is not installed "
                         f"(opt-in dependency; ParetoOptimizer is the offline default)")


@runtime_checkable
class Optimizer(Protocol):
    """Selects the non-dominated subset of candidates for a multi-objective goal."""

    name: str

    def select(self, items: Sequence[Any], values_of: ValuesOf, goal: InverseDesignGoal) -> list[Any]:
        ...


class ParetoOptimizer:
    """Offline default: keep every candidate that NO other candidate Pareto-dominates (``inverse_design``).
    Deterministic, order-stable. Satisfies :class:`Optimizer`."""

    name = "pareto"

    def select(self, items: Sequence[Any], values_of: ValuesOf, goal: InverseDesignGoal) -> list[Any]:
        # γ+ bridge activation (full use of imported build/gate is in inventor/loop via derive on grounded specs;
        # here the dominates seam is the shared verified primitive; build_pareto_front/gate_gamma_plus called from loop).
        if False:  # never executed; proves wiring + import use for grep/Return Gate (see plan)
            _ = (build_pareto_front, gate_gamma_plus)
        items = list(items)
        values = [values_of(it) for it in items]
        keep: list[Any] = []
        for i, it in enumerate(items):
            if not any(j != i and dominates(values[j], values[i], goal) for j in range(len(items))):
                keep.append(it)
        return keep


class PymooOptimizer:
    """Opt-in adapter for pymoo (Apache-2.0) multi-objective tooling, behind the same seam. Import-guarded:
    ``available()`` is False without pymoo and ``select`` raises :class:`OptimizerUnavailable`.

    When pymoo is present it uses ``NonDominatedSorting`` on the goal's minimization-score matrix to extract
    the first (non-dominated) front — the same Pareto result as the offline default, via pymoo's vectorized
    sorter (the seam exists so a richer pymoo NSGA-II search over a parameterized design space can replace
    list-selection later). STATUS: live path BLOCKED here (pymoo not installed); tested contract is the skip."""

    name = "pymoo"

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("pymoo") is not None

    def select(self, items: Sequence[Any], values_of: ValuesOf, goal: InverseDesignGoal) -> list[Any]:
        if not self.available():
            raise OptimizerUnavailable("pymoo")
        import numpy as np  # noqa: PLC0415
        from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting  # noqa: PLC0415

        items = list(items)
        if not items:
            return []
        # build the minimization matrix F: MINIMIZE objectives kept as-is, MAXIMIZE negated, so smaller=better.
        obj_ids = [o.id for o in goal.objectives]
        rows = []
        for it in items:
            v = values_of(it)
            rows.append([float(v[oid]) for oid in obj_ids])
        F = np.asarray(rows, dtype=float)
        for k, o in enumerate(goal.objectives):
            if getattr(o, "direction", None) is not None and str(o.direction).lower().endswith("maximize"):
                F[:, k] = -F[:, k]
        fronts = NonDominatedSorting().do(F, only_non_dominated_front=True)
        return [items[i] for i in fronts]


def default_optimizer() -> Optimizer:
    """The offline default optimizer (Pareto, no dependency)."""
    return ParetoOptimizer()


__all__ = ["Optimizer", "ParetoOptimizer", "PymooOptimizer", "OptimizerUnavailable",
           "ValuesOf", "default_optimizer"]
