"""knowledge_graph — a discovery KG over confirmed laws with a dimensional-type filter (SciAgents).

SciAgents proposes cross-domain hypotheses by walking a knowledge graph; the failure mode is that a
random path between distant nodes is *spurious by default*. GENESIS's advantage (agent-C analysis) is
that it owns a DETERMINISTIC disposer the LLM-only systems lack: a dimensional-type filter. So this
module builds a graph over GENESIS's own confirmed laws (nodes = variables typed by dimension, edges =
co-occurrence in a law) and proposes cross-domain variable groupings — but every proposal is first run
through ``dimensional_type_filter``: a grouping whose dimensions CANNOT form the target dimension is
rejected before any data or gate work. The KG suggests breadth; the dimensional types dispose the
impossible; the deterministic gate (downstream) judges what remains. Nothing is ever a *finding* here —
only a gate input.

Deterministic (seeded), offline, reuses the existing dimensional algebra (``units`` + ``engine``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..verification.units import Dimension, parse_unit
from .engine import DIMENSION_TOLERANCE, dimensional_power_law


@dataclass
class DiscoveryGraph:
    """Variables seen in confirmed laws, each typed by its dimension, with co-occurrence edges."""

    _dimension: dict[str, Dimension] = field(default_factory=dict)
    _edges: dict[str, set[str]] = field(default_factory=dict)

    def add_law(self, *, target_name: str, target_unit: str, source_units: dict[str, str]) -> None:
        """Register a confirmed law: its target and source variables (typed by dimension), with a
        co-occurrence edge between every pair of its sources (they appear together in a real law)."""
        self._dimension[target_name] = parse_unit(target_unit)
        for name, unit in source_units.items():
            self._dimension[name] = parse_unit(unit)
        names = list(source_units)
        for a in names:
            for b in names:
                if a != b:
                    self._edges.setdefault(a, set()).add(b)

    @property
    def variables(self) -> frozenset[str]:
        return frozenset(self._dimension)

    def neighbours(self, name: str) -> frozenset[str]:
        return frozenset(self._edges.get(name, set()))

    def dimensional_type_filter(self, sources: list[str], target: Dimension) -> bool:
        """Deterministic disposer: can these sources' dimensions form ``target`` via a power law (the
        exponent system has residual ≈ 0)? An ill-typed cross-domain grouping is rejected here — before
        any data or the gate — which is the anti-hallucination lever LLM-only KG systems lack."""
        dims = [self._dimension[s] for s in sources if s in self._dimension]
        if not dims or len(dims) != len(sources):
            return False
        _, residual = dimensional_power_law(target, list(sources), dims)
        return residual < DIMENSION_TOLERANCE

    def propose_cross_domain(
        self, target: Dimension, *, size: int = 2, n: int = 8, seed: int = 0
    ) -> list[list[str]]:
        """Randomized-waypoint proposals: sample variable groupings (possibly drawn from DIFFERENT laws)
        and keep only those that PASS the dimensional-type filter for ``target``. Returns dimensionally-
        feasible candidate source subsets for the gate to judge on data; the spurious rest never reach
        it. Deterministic for a fixed ``seed``."""
        rng = np.random.default_rng(seed)
        names = sorted(self._dimension)
        if size > len(names):
            return []
        feasible: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()
        for _ in range(n * 16):
            if len(feasible) >= n:
                break
            subset = sorted(rng.choice(names, size=size, replace=False).tolist())
            key = tuple(subset)
            if key in seen:
                continue
            seen.add(key)
            if self.dimensional_type_filter(subset, target):
                feasible.append(subset)
        return feasible
