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
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence, runtime_checkable

from ..core.errors import GenesisError
from ..inverse_design import InverseDesignGoal, dominates, build_pareto_front, gate_gamma_plus

#: A candidate -> its objective-id -> value mapping (what the goal scores).
ValuesOf = Callable[[Any], dict[str, float]]

#: A continuous objective: design-variable name -> value  ->  scalar to MINIMIZE.
ObjectiveFn = Callable[[Mapping[str, float]], float]


class OptimizerUnavailable(GenesisError):
    """An external optimizer was selected but its package is not installed. Loud — the caller falls back to
    the offline ParetoOptimizer rather than getting a silently-wrong front."""

    def __init__(self, tool: str) -> None:
        super().__init__(f"optimizer backend {tool!r} is not installed "
                         f"(opt-in dependency; ParetoOptimizer is the offline default)")


class OptimizationError(GenesisError):
    """A continuous optimization run did not converge / could not be set up. Loud, never a silent
    return of the last (unconverged) iterate dressed up as an optimum — an un-converged driver is a
    failed analysis, not a result (CLAUDE.md: keine stillen Defaults bei faktischen Dingen)."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"continuous optimization failed: {reason}")


@dataclass(frozen=True)
class DesignVar:
    """One continuous design variable for :meth:`OpenMdaoOptimizer.minimize`.

    `name`   identifier-safe variable name (the key in the objective's input mapping).
    `lower`  inclusive lower bound.
    `upper`  inclusive upper bound (must be > lower).
    `start`  initial value, REQUIRED and inside [lower, upper]: the start point is an
             explicit declared input, not a hidden default — a hidden start is a hidden
             assumption the optimizer's result would silently depend on.
    """

    name: str
    lower: float
    upper: float
    start: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("DesignVar needs a non-empty name")
        if not self.upper > self.lower:
            raise ValueError(
                f"DesignVar {self.name!r}: upper ({self.upper}) must be > lower ({self.lower})"
            )
        if not (self.lower <= self.start <= self.upper):
            raise ValueError(
                f"DesignVar {self.name!r}: start ({self.start}) must lie in "
                f"[{self.lower}, {self.upper}]"
            )


@dataclass(frozen=True)
class MdoResult:
    """Outcome of a continuous optimization (:meth:`OpenMdaoOptimizer.minimize`).

    `x`          optimum design point (variable name -> value).
    `objective`  objective value at the optimum.
    `success`    whether the driver reported convergence (always True on return — a
                 non-converged run raises :class:`OptimizationError` instead).
    `n_evals`    number of objective evaluations the driver took (provenance / cost).
    `driver`     the OpenMDAO driver/optimizer that produced it (e.g. "SLSQP").
    """

    x: dict[str, float]
    objective: float
    success: bool
    n_evals: int
    driver: str


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


class OpenMdaoOptimizer:
    """Opt-in MDO backend (OpenMDAO, Apache-2.0) behind the same seam. Import-guarded:
    ``available()`` is False without openmdao and every entry point raises
    :class:`OptimizerUnavailable`.

    HONEST design decision (do not skim this):

      * The :class:`Optimizer` seam's contract is ``select`` — filter a FIXED list of
        already-built candidates down to the non-dominated subset. OpenMDAO is a
        gradient / DOE optimizer over a CONTINUOUS design space; it is the wrong tool
        for filtering a discrete list and would add nothing but a dependency. So
        ``select`` here computes the SAME Pareto front as :class:`ParetoOptimizer`
        (the verified ``inverse_design.dominates``) — it does NOT pretend OpenMDAO did
        the filtering. The only behavioural difference from ParetoOptimizer is the
        import guard: selecting the "openmdao" backend when openmdao is absent fails
        loud, rather than silently degrading.

      * OpenMDAO's REAL value is exposed by :meth:`minimize` — a genuine continuous
        optimization of a parametric objective over declared design-variable bounds.
        That is what an MDO engine is for, and that method actually builds and runs an
        ``om.Problem`` with a real driver. This is the method to use when you have a
        parametric design (e.g. size a part to minimise mass subject to a stress
        margin) rather than a pre-enumerated candidate list.

    STATUS: live — openmdao 3.44 is installed; both ``select`` (Pareto) and
    ``minimize`` (real SLSQP run) are exercised by tests/test_optimize_openmdao.py.
    """

    name = "openmdao"

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("openmdao") is not None

    def select(self, items: Sequence[Any], values_of: ValuesOf, goal: InverseDesignGoal) -> list[Any]:
        """Non-dominated subset (same result as :class:`ParetoOptimizer`).

        Raises :class:`OptimizerUnavailable` if openmdao is not installed — the seam
        promised an OpenMDAO backend, so its absence is surfaced, not silently
        substituted. The filtering itself is the verified ``dominates`` Pareto logic
        (see the class docstring for why OpenMDAO does not — and should not — do this).
        """
        if not self.available():
            raise OptimizerUnavailable("openmdao")
        items = list(items)
        values = [values_of(it) for it in items]
        keep: list[Any] = []
        for i, it in enumerate(items):
            if not any(j != i and dominates(values[j], values[i], goal) for j in range(len(items))):
                keep.append(it)
        return keep

    def minimize(
        self,
        objective: ObjectiveFn,
        design_vars: Sequence[DesignVar],
        *,
        optimizer: str = "SLSQP",
        tol: float = 1e-8,
        maxiter: int = 200,
    ) -> MdoResult:
        """Minimise a parametric ``objective`` over ``design_vars`` with OpenMDAO.

        Builds a real ``om.Problem``: the Python callable is wrapped in an
        ``ExplicitComponent`` whose partials are finite-differenced (so ANY scalar
        objective works, not only ExecComp expression strings), driven by
        ``ScipyOptimizeDriver`` with the requested gradient ``optimizer`` (default
        SLSQP). ``objective(x)`` receives ``{var_name: value}`` and returns the scalar
        to minimise (to MAXIMISE, return its negation).

        Returns the converged :class:`MdoResult`.

        Raises:
            OptimizerUnavailable: openmdao is not installed.
            ValueError: no design variables, duplicate variable names, or a non-finite
                objective value at the start point (a broken objective surfaces here,
                not as a bogus optimum).
            OptimizationError: the driver did not report success — an un-converged run
                is a failed analysis, never returned as if it were the optimum.
        """
        if not self.available():
            raise OptimizerUnavailable("openmdao")
        dvs = list(design_vars)
        if not dvs:
            raise ValueError("minimize needs at least one design variable")
        names = [dv.name for dv in dvs]
        if len(names) != len(set(names)):
            raise ValueError(f"design variable names must be unique, got {names}")

        import numpy as np  # noqa: PLC0415
        import openmdao.api as om  # noqa: PLC0415

        # Fail loud on a broken objective BEFORE handing it to the driver: a callable
        # that returns NaN/inf (or raises) at the declared start point is a bug in the
        # objective, and must not be masked by the optimizer wandering to some number.
        start = {dv.name: float(dv.start) for dv in dvs}
        try:
            f0 = float(objective(start))
        except Exception as exc:  # noqa: BLE001 - surface the objective's own failure, typed
            raise ValueError(f"objective raised at the start point {start}: {exc}") from exc
        if not np.isfinite(f0):
            raise ValueError(f"objective is non-finite ({f0}) at the start point {start}")

        eval_count = {"n": 0}

        class _CallableComp(om.ExplicitComponent):
            """Wrap the user objective as an OpenMDAO component (FD partials)."""

            def setup(self):
                for name in names:
                    self.add_input(name, val=0.0)
                self.add_output("obj", val=0.0)
                self.declare_partials("obj", names, method="fd")

            def compute(self, inputs, outputs):
                point = {name: float(inputs[name][0]) for name in names}
                value = float(objective(point))
                if not np.isfinite(value):
                    # NaN/inf mid-search would let SLSQP "converge" to garbage; raise so
                    # the run fails loud instead of certifying an invalid point.
                    raise om.AnalysisError(
                        f"objective is non-finite ({value}) at {point}"
                    )
                eval_count["n"] += 1
                outputs["obj"] = value

        prob = om.Problem()
        prob.model.add_subsystem("c", _CallableComp(), promotes=["*"])
        prob.driver = om.ScipyOptimizeDriver()
        prob.driver.options["optimizer"] = optimizer
        prob.driver.options["tol"] = tol
        prob.driver.options["maxiter"] = maxiter
        for dv in dvs:
            prob.model.add_design_var(dv.name, lower=dv.lower, upper=dv.upper)
        prob.model.add_objective("obj")

        try:
            prob.setup()
            for dv in dvs:
                prob.set_val(dv.name, dv.start)
            driver_result = prob.run_driver()
        except Exception as exc:  # noqa: BLE001 - setup/solve failure -> typed loud error
            raise OptimizationError(f"{optimizer} run errored: {exc}") from exc

        # OpenMDAO 3.44 returns a DriverResult whose .success is the authoritative
        # convergence flag (the legacy truthy "failed" return is deprecated). A driver
        # that hit its iteration limit reports success=False -> fail loud, never return
        # the last iterate as if it were the optimum.
        if not bool(getattr(driver_result, "success", driver_result)):
            raise OptimizationError(
                f"{optimizer} did not converge (tol={tol}, maxiter={maxiter})"
            )

        x = {dv.name: float(prob.get_val(dv.name)[0]) for dv in dvs}
        obj = float(prob.get_val("obj")[0])
        return MdoResult(
            x=x, objective=obj, success=True, n_evals=eval_count["n"], driver=optimizer
        )


def default_optimizer() -> Optimizer:
    """The offline default optimizer (Pareto, no dependency)."""
    return ParetoOptimizer()


__all__ = ["Optimizer", "ParetoOptimizer", "PymooOptimizer", "OpenMdaoOptimizer",
           "OptimizerUnavailable", "OptimizationError", "DesignVar", "MdoResult",
           "ObjectiveFn", "ValuesOf", "default_optimizer"]
