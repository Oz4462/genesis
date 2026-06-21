"""archive — a MAP-Elites quality-diversity archive over confirmed discoveries (AlphaEvolve adoption).

AlphaEvolve/FunSearch keep a population, not a single answer: a MAP-Elites grid stores the best
candidate per behavioral CELL, so the search retains DIVERSITY (many distinct kinds of law) alongside
quality (the best fit in each kind). GENESIS adopts the same structure over its gate-passing
discoveries: the behavioral descriptor is the candidate's structural signature (its complexity + which
variables participate), the quality is the fit R², and — the load-bearing invariant — ONLY a
gate-PASSING candidate may be admitted. Nothing untrusted ever enters the archive; it is a curated
collection of confirmed laws, indexed for diversity.

This is a pure container (the search/controller fills it); it never judges correctness — the
deterministic gate already did that before admission. Offline, deterministic, numpy-free.
"""

from __future__ import annotations

from .engine import Candidate, DiscoveryResult

_EXP_EPS = 1e-9

#: A behavioral cell key: (complexity, the frozenset of participating variable names).
Cell = tuple[int, frozenset[str]]


def descriptor_of(candidate: Candidate) -> Cell:
    """The behavioral descriptor (MAP-Elites cell) of a candidate: its parsimony bucket and the set of
    variables it actually uses — so two laws over the same variables at the same complexity compete,
    while structurally different laws occupy different cells (diversity)."""
    used = frozenset(name for name, exp in candidate.exponents.items() if abs(exp) >= _EXP_EPS)
    return (candidate.complexity, used)


class EliteArchive:
    """A MAP-Elites archive: at most one elite (highest R²) per behavioral cell, gate-passing only."""

    def __init__(self) -> None:
        self._cells: dict[Cell, Candidate] = {}

    def add(self, candidate: Candidate, *, passed: bool) -> bool:
        """Admit a GATE-PASSING candidate, keeping the higher-R² elite of its cell. Returns True iff it
        became (or replaced) the cell's elite. A candidate that did NOT pass the gate is never admitted
        (the invariant) and returns False."""
        if not passed:
            return False
        key = descriptor_of(candidate)
        current = self._cells.get(key)
        if current is None or candidate.r_squared > current.r_squared:
            self._cells[key] = candidate
            return True
        return False

    def add_result(self, result: DiscoveryResult) -> int:
        """Admit every gate-passing candidate from a ``DiscoveryResult`` (its ``validated`` verdicts).
        Returns how many became elites (new cells filled or improved)."""
        return sum(self.add(v.candidate, passed=v.passed) for v in result.validated)

    def elites(self) -> list[Candidate]:
        """All current cell elites, best fit first (a deterministic, stable order)."""
        return sorted(self._cells.values(), key=lambda c: (-c.r_squared, c.complexity, c.expression))

    def best(self) -> Candidate | None:
        """The single highest-R² elite across all cells, or None when the archive is empty."""
        elites = self.elites()
        return elites[0] if elites else None

    @property
    def coverage(self) -> int:
        """The number of filled behavioral cells — the diversity of confirmed discoveries held."""
        return len(self._cells)
