"""simulated_data — build a SELF-GENERATED-DATA DiscoveryProblem by sampling a GENESIS simulator / closed form.

INVENTOR §10 (the research core's owner-priority point): GENESIS must not only regress on user-supplied
numbers — it ERZEUGT seine eigenen Daten und entdeckt damit Gesetze, die in keinem Trainingsdatensatz stehen.
The SINDy/ODE path (``discovery.sindy`` ← ``simulation.multibody.simulate_pendulum``) already does this for
dynamics. This module closes the SAME loop for the DIMENSIONAL power-law engine: sample a target function
``f(**inputs) -> float`` over the inputs' ranges → a :class:`DiscoveryProblem` whose target values are
SELF-GENERATED → :func:`discover_new_formulas` finds the law (and gets the same callable for its separability
annotation).

The sampling is log-uniform per input (a power law needs magnitudes spanning decades to be identifiable) and
seeded (reproducible). Magnitudes are kept strictly positive — the engine rejects a non-positive base loudly
rather than return nan. Offline, deterministic given the seed. NO new fact type: it only produces the engine's
own ``DiscoveryProblem`` from a function instead of from a file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .engine import (
    Constant,
    DiscoveryProblem,
    DiscoveryResult,
    Variable,
    discover_new_formulas,
)


@dataclass(frozen=True)
class InputSpec:
    """One input to sample: a ``name``, a ``unit`` (parsed by the engine's units algebra), and the strictly
    positive ``[lo, hi]`` range it is sampled over (log-uniformly)."""

    name: str
    unit: str
    lo: float
    hi: float

    def __post_init__(self) -> None:
        if not (0.0 < self.lo < self.hi):
            raise ValueError(f"input {self.name!r} needs 0 < lo < hi (got lo={self.lo}, hi={self.hi})")


def problem_from_simulation(
    idea: str,
    *,
    target_name: str,
    target_unit: str,
    inputs: tuple[InputSpec, ...],
    sim_fn: Callable[..., float],
    n_samples: int = 200,
    seed: int = 0,
    constants: tuple[Constant, ...] = (),
    run_id: str | None = None,
) -> tuple[DiscoveryProblem, Callable[..., float]]:
    """Sample ``sim_fn(**inputs, **constants)`` over the inputs' log-uniform ranges to GENERATE the target
    data, returning the SELF-GENERATED :class:`DiscoveryProblem` plus an input-only ``baked`` callable (the
    constants closed in) for the engine's separability annotation. Raises ValueError on an empty input set, a
    too-small sample count, or a non-positive/non-finite target sample (the dimensional engine needs positive
    magnitudes)."""
    if not inputs:
        raise ValueError("need at least one input to sample")
    if n_samples < 2:
        raise ValueError("need at least 2 samples")
    # Names are the engine's key space: it identifies every source (input OR constant) by name in one
    # dict of exponents. A duplicate name would silently collapse two distinct quantities into one column
    # (the dict comprehension below keeps only the last 'cols' entry) and corrupt the dimensional solve —
    # a "keine stillen Defaults" bug. Fail loud instead of discovering on a silently corrupted problem.
    source_names = [s.name for s in inputs] + [c.name for c in constants]
    if len(set(source_names)) != len(source_names):
        raise ValueError(f"input and constant names must be unique (got {source_names})")
    rng = np.random.default_rng(seed)
    cols = {s.name: np.exp(rng.uniform(math.log(s.lo), math.log(s.hi), size=n_samples)) for s in inputs}
    const_kwargs = {c.name: c.value for c in constants}

    target_vals: list[float] = []
    for i in range(n_samples):
        kwargs = {name: float(cols[name][i]) for name in cols}
        y = float(sim_fn(**kwargs, **const_kwargs))
        if not math.isfinite(y) or y <= 0.0:
            raise ValueError(f"sim_fn produced a non-positive/non-finite target ({y}) at sample {i}; "
                             "the dimensional power-law engine needs positive magnitudes")
        target_vals.append(y)

    target = Variable(target_name, target_unit, tuple(target_vals))
    invars = tuple(Variable(s.name, s.unit, tuple(float(v) for v in cols[s.name])) for s in inputs)
    problem = DiscoveryProblem(idea=idea, target=target, inputs=invars,
                               constants=constants, run_id=run_id)

    def baked(**input_kwargs: float) -> float:
        return sim_fn(**input_kwargs, **const_kwargs)

    return problem, baked


def discover_from_simulation(
    idea: str,
    *,
    target_name: str,
    target_unit: str,
    inputs: tuple[InputSpec, ...],
    sim_fn: Callable[..., float],
    n_samples: int = 200,
    seed: int = 0,
    constants: tuple[Constant, ...] = (),
    run_id: str | None = None,
    **discover_kwargs,
) -> DiscoveryResult:
    """One call: GENERATE self-sampled data from ``sim_fn`` and run the dimensional SR engine on it (handing the
    engine the same callable for its separability annotation). The discovered law is found from data GENESIS
    produced itself — not from any supplied dataset. ``discover_kwargs`` pass through to
    :func:`discover_new_formulas` (e.g. ``known_laws``, ``r2_threshold``)."""
    problem, baked = problem_from_simulation(
        idea, target_name=target_name, target_unit=target_unit, inputs=inputs, sim_fn=sim_fn,
        n_samples=n_samples, seed=seed, constants=constants, run_id=run_id)
    return discover_new_formulas(problem, target_fn=baked, **discover_kwargs)


__all__ = ["InputSpec", "problem_from_simulation", "discover_from_simulation"]
