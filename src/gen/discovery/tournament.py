"""tournament — population-based hypothesis evolution (build doc 3.1).

The base engine's dimensional solve returns ONE constrained candidate. That is exactly
right when the dimensional system is fully determined (Kepler: the exponents are forced).
But when several inputs share a dimension, the system is UNDER-determined: a whole FAMILY
of power laws is dimensionally valid, and only the DATA can choose among them. The
single-shot least-norm pick is often not the truest one. This is where evolution earns its
keep.

The elegant move: evolve only inside the NULL SPACE of the dimensional constraint. Every
candidate is ``p = p_particular + Σ tᵢ·nullᵢ``, so ``A·p = b`` holds for ALL of them —
mutation and crossover can never produce a dimensionally invalid law. The search is purely
over the free π-group coefficients ``t``; the data (fitness = R² − parsimony·complexity)
selects. When the null space is empty (a determined system), there is nothing to search and
the tournament honestly returns the single-shot candidate unchanged.

DoD (the doc): over N generations the tournament finds a MEASURABLY better candidate than
single-shot. The test pins exactly that on a free-π-group problem whose true law is not the
least-norm one. Deterministic (seeded RNG); offline; numpy-only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import (
    Candidate,
    DiscoveryProblem,
    candidate_from_exponents,
    dimensional_system,
    symbolic_regress,
)

#: Default parsimony penalty (per non-zero exponent) subtracted from R² in the fitness.
DEFAULT_PARSIMONY = 0.01


@dataclass(frozen=True)
class TournamentReport:
    """The outcome of an evolutionary run: the best candidate, the best-fitness trajectory
    (proving improvement), and the single-shot baseline it is compared against."""

    best: Candidate
    single_shot: Candidate
    best_fitness_per_generation: tuple[float, ...]
    generations: int
    population_size: int
    improved: bool


def _nullspace(a_matrix: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Orthonormal basis of the null space of `a_matrix` (rows), via SVD. Shape
    ``(n_free, n_sources)``; empty when the system is fully determined."""
    _, s, vh = np.linalg.svd(a_matrix)
    rank = int((s > tol).sum())
    return vh[rank:]


def _fitness(cand: Candidate, parsimony: float) -> float:
    """R² rewarded, complexity penalised — the selection pressure (higher = better)."""
    return cand.r_squared - parsimony * cand.complexity


def evolve(
    problem: DiscoveryProblem,
    *,
    generations: int = 16,
    population: int = 24,
    parsimony: float = DEFAULT_PARSIMONY,
    mutation_scale: float = 0.6,
    seed: int = 0,
) -> TournamentReport:
    """Evolve a population of dimensionally-valid power laws to best explain `problem`.

    Starts from the single-shot candidate and random points along the dimensional null
    space; each generation keeps the fittest half (selection), recombines survivors
    (crossover) and perturbs the offspring along the null space (mutation). Returns the best
    candidate found and the per-generation best fitness. When the null space is empty the
    single-shot candidate is already the only dimensionally-valid law and is returned with
    ``improved=False``. Deterministic for a fixed `seed`. Raises ValueError on bad data (via
    the engine).
    """
    single_shot = symbolic_regress(problem)[0]
    a_matrix, b_vec, names = dimensional_system(problem)
    particular, *_ = np.linalg.lstsq(a_matrix, b_vec, rcond=None)
    null = _nullspace(a_matrix)
    n_free = null.shape[0]

    base_fitness = _fitness(single_shot, parsimony)
    if n_free == 0:  # determined system — nothing to search, be honest
        return TournamentReport(best=single_shot, single_shot=single_shot,
                                best_fitness_per_generation=(base_fitness,),
                                generations=0, population_size=1, improved=False)

    rng = np.random.default_rng(seed)

    def exps_from_t(t: np.ndarray) -> dict[str, float]:
        p = particular + t @ null
        return {name: float(p[i]) for i, name in enumerate(names)}

    def evaluate(t: np.ndarray) -> tuple[float, Candidate]:
        cand = candidate_from_exponents(problem, exps_from_t(t))
        return _fitness(cand, parsimony), cand

    # initial population: the single-shot (t = 0) plus random null-space offsets
    pop_t = [np.zeros(n_free)] + [rng.normal(0.0, 1.0, n_free) for _ in range(population - 1)]
    best_per_gen: list[float] = []
    best_overall: tuple[float, Candidate] = evaluate(np.zeros(n_free))

    for _ in range(generations):
        scored = sorted((( *evaluate(t),) + (t,) for t in pop_t),
                        key=lambda r: -r[0])  # (fitness, candidate, t) desc
        best_per_gen.append(scored[0][0])
        if scored[0][0] > best_overall[0]:
            best_overall = (scored[0][0], scored[0][1])
        survivors = [r[2] for r in scored[: max(2, population // 2)]]
        # next generation: survivors carried over + crossover/mutation offspring
        children: list[np.ndarray] = list(survivors)
        while len(children) < population:
            pa = survivors[rng.integers(len(survivors))]
            pb = survivors[rng.integers(len(survivors))]
            w = rng.uniform(0.0, 1.0)
            child = w * pa + (1.0 - w) * pb + rng.normal(0.0, mutation_scale, n_free)
            children.append(child)
        pop_t = children

    improved = best_overall[0] > base_fitness + 1e-9
    return TournamentReport(
        best=best_overall[1],
        single_shot=single_shot,
        best_fitness_per_generation=tuple(best_per_gen),
        generations=generations,
        population_size=population,
        improved=improved,
    )
