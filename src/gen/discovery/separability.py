"""separability — additive / multiplicative separability detection (AI-Feynman adoption).

AI-Feynman's decisive move: before fitting one hard formula, test whether the target DECOMPOSES into
independent sub-blocks — ``y = g(A) + h(B)`` (additive) or ``y = g(A)·h(B)`` (multiplicative) — so each
block becomes a simpler problem GENESIS's power-law engine can solve. This is GENESIS's path from a
single monomial toward multi-term / composition laws (the declared `engine.py` extension).

The test is the mixed second difference: for an additive target, ``∂²y/∂xᵢ∂xⱼ = 0`` across a block
boundary, so the 2×2 corner sum ``y(++) − y(+−) − y(−+) + y(−−)`` vanishes; multiplicative separability
is the SAME test on ``log y``. It is evaluated on a small deterministic (seeded) set of base points over
the variable ranges, normalised by the local magnitude, so "separable" means the relative interaction
is below tolerance everywhere tested.

Honest boundary: this needs a QUERYABLE target ``f(**vars)`` — GENESIS has it for generated/benchmark
problems, or via a fitted surrogate; on raw scattered data alone the mixed difference is not directly
computable (fitting a surrogate first is the documented extension). Deterministic, offline, numpy-only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Mapping, Sequence

import numpy as np

#: An interaction below this (relative) magnitude counts as "no interaction" -> the pair separates.
DEFAULT_SEPARABILITY_TOLERANCE = 1e-6


@dataclass(frozen=True)
class SeparabilityResult:
    """Which variables separate under ``mode`` and the groups that must stay together.

    ``groups`` are the connected components of the NON-separable graph: variables inside one group
    interact (must be discovered jointly), variables in different groups are separable (the law factors
    /sums across the group boundary). ``max_interaction`` is the largest relative residual (0 = perfectly
    separable into singletons)."""

    mode: str
    groups: tuple[frozenset[str], ...]
    separable_pairs: frozenset[frozenset[str]]
    max_interaction: float


def _corner_sum(g: Callable[..., float], base: dict[str, float],
                lo: Mapping[str, float], hi: Mapping[str, float], i: str, j: str) -> float:
    """The 2×2 mixed second difference of ``g`` in variables ``i, j`` (others held at ``base``)."""
    def y(vi: float, vj: float) -> float:
        point = dict(base)
        point[i], point[j] = vi, vj
        return float(g(**point))
    return y(hi[i], hi[j]) - y(hi[i], lo[j]) - y(lo[i], hi[j]) + y(lo[i], lo[j])


def _relative_interaction(g, names, ranges, i, j, *, n_bases: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    lo = {k: float(r[0]) for k, r in ranges.items()}
    hi = {k: float(r[1]) for k, r in ranges.items()}
    worst = 0.0
    for _ in range(n_bases):
        base = {k: float(rng.uniform(lo[k], hi[k])) for k in names}
        mixed = _corner_sum(g, base, lo, hi, i, j)
        corner = dict(base)
        corner[i], corner[j] = hi[i], hi[j]
        scale = abs(float(g(**corner))) + 1e-12
        worst = max(worst, abs(mixed) / scale)
    return worst


def analyze_separability(
    f: Callable[..., float],
    names: Sequence[str],
    ranges: Mapping[str, tuple[float, float]],
    *,
    mode: str = "additive",
    tol: float = DEFAULT_SEPARABILITY_TOLERANCE,
    n_bases: int = 6,
    seed: int = 0,
) -> SeparabilityResult:
    """Detect additive (``mode='additive'``) or multiplicative (``mode='multiplicative'``) separability
    of ``f`` over ``names``. For multiplicative mode ``f`` must be positive on the ranges (it is tested on
    ``log f``). Returns the variable groups that must stay together.

    Raises ``ValueError`` on an unknown ``mode``, on ``n_bases < 1`` (no base point would be sampled, so
    the mixed difference is never evaluated and EVERY pair would be reported separable — a fabricated
    "fully separable" verdict), and on ``tol < 0`` (a non-negative residual can never satisfy
    ``interaction <= tol``, so EVERY pair would be reported coupled — a fabricated "all coupled" verdict).
    Both are silent wrong factual values, so we fail loud instead of guessing (no silent defaults)."""
    if mode not in ("additive", "multiplicative"):
        raise ValueError("mode must be 'additive' or 'multiplicative'")
    if n_bases < 1:
        raise ValueError("n_bases must be >= 1: with no base points the mixed difference is never "
                         "evaluated and every pair would falsely report as separable")
    if tol < 0.0:
        raise ValueError("tol must be >= 0: a negative tolerance can never be met by a non-negative "
                         "relative interaction, so every pair would falsely report as coupled")
    if mode == "multiplicative":
        def g(**kw: float) -> float:
            value = float(f(**kw))
            if value <= 0.0:
                raise ValueError("multiplicative separability needs a positive target on the ranges")
            return math.log(value)
    else:
        g = f  # type: ignore[assignment]

    separable: set[frozenset[str]] = set()
    parent = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    max_interaction = 0.0
    for i, j in combinations(names, 2):
        interaction = _relative_interaction(g, names, ranges, i, j, n_bases=n_bases, seed=seed)
        max_interaction = max(max_interaction, interaction if interaction > tol else 0.0)
        if interaction <= tol:
            separable.add(frozenset((i, j)))
        else:
            union(i, j)  # an interacting pair must stay in the same group

    groups: dict[str, set[str]] = {}
    for n in names:
        groups.setdefault(find(n), set()).add(n)
    group_tuple = tuple(sorted((frozenset(g) for g in groups.values()), key=lambda s: sorted(s)))
    return SeparabilityResult(mode, group_tuple, frozenset(separable), max_interaction)
