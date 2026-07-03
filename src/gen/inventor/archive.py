"""archive — concept-level MAP-Elites for inventions, plus recombination (TE1 + TE3).

Open-ended invention is quality-DIVERSITY, not a single optimum (Mouret & Clune 2015): the archive keeps the
BEST invention per behavioral NICHE, so distinct kinds of solution coexist instead of collapsing to one. This
is the storage structure (the ``evolve_engine`` MAP-Elites is the search); together they keep the loop diverse.

``invention_niche`` describes an invention's KIND (its mechanism family + a coarse performance band) and
``invention_fitness`` scores it from the 5-axis :func:`score.score_invention` — both injectable. Recombination
(:func:`recombine_concepts`) crosses two elite concepts into a grounded hybrid concept (its grounding is the
UNION of the parents', so the hybrid stays anchored — the concept-level grounding invariant is preserved).
Deterministic, offline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Sequence

from ..core.state import Possibility
from .brief import Invention
from .score import score_invention

NicheOf = Callable[[Invention], object]
Fitness = Callable[[Invention], float]


def invention_niche(inv: Invention) -> tuple:
    """An invention's behavioral niche: (mechanism family keyword, performance band). The mechanism's first
    word captures the KIND of solution; the performance band (integer modal margin) captures how strong it is.
    Two inventions of the same family and band compete; different families/bands coexist."""
    mech = inv.concept.mechanism.strip().lower()
    family = mech.split()[0] if mech else ""
    perf_band = int(score_invention(inv).performance) if inv.grounded else -1
    return (family, perf_band)


def invention_fitness(inv: Invention) -> float:
    """A scalar fitness (higher = better) from the 5-axis score: reward performance + novelty, lightly
    penalize cost + complexity. Ungrounded inventions score -inf — they are not elites."""
    if not inv.grounded:
        return float("-inf")
    s = score_invention(inv)
    return s.performance + s.novelty - 0.01 * s.cost - 0.01 * s.complexity


class InventionArchive:
    """A MAP-Elites archive: one cell per niche, holding the highest-fitness invention seen for it."""

    def __init__(self, *, niche_of: NicheOf = invention_niche, fitness: Fitness = invention_fitness) -> None:
        self._niche_of = niche_of
        self._fitness = fitness
        self._cells: dict[object, tuple[float, Invention]] = {}

    def consider(self, inv: Invention) -> bool:
        """Offer an invention to the archive. Returns True iff it was inserted (a new niche) or REPLACED the
        cell's incumbent (strictly higher fitness). A lower-fitness invention in an occupied niche is rejected."""
        niche = self._niche_of(inv)
        score = self._fitness(inv)
        current = self._cells.get(niche)
        if current is None or score > current[0]:
            self._cells[niche] = (score, inv)
            return True
        return False

    def extend(self, inventions: Sequence[Invention]) -> int:
        """Offer many inventions; returns how many were inserted/replaced."""
        return sum(1 for inv in inventions if self.consider(inv))

    def elites(self) -> list[Invention]:
        """The current elite per niche, ordered by niche for reproducibility."""
        return [self._cells[n][1] for n in sorted(self._cells, key=repr)]

    def __len__(self) -> int:
        return len(self._cells)


def recombine_concepts(a: Possibility, b: Possibility, *, now: datetime, run_id: str = "hybrid",
                       index: int = 1) -> Possibility:
    """Cross two elite concepts into a hybrid concept (TE3 recombination). The hybrid's statement names both
    parents and its mechanism couples theirs; its grounding is the UNION of the parents' anchors, so the
    hybrid is itself grounded (the concept-level invariant holds — a hybrid is not an ungrounded guess).
    Raises ValueError if both parents are anchorless (the union would be empty)."""
    grounding = list(dict.fromkeys([*a.grounding, *b.grounding]))
    if not grounding:
        raise ValueError("cannot recombine two anchorless concepts (the hybrid would be ungrounded)")
    statement = f"Hybrid: {a.statement} × {b.statement}"
    mechanism = f"{a.mechanism}; gekoppelt mit {b.mechanism}"
    return Possibility(id=f"{run_id}-h{index}", statement=statement, mechanism=mechanism,
                       grounding=grounding, produced_by="inventor.recombine", model="recombine", created_at=now)


__all__ = ["InventionArchive", "invention_niche", "invention_fitness", "recombine_concepts",
           "NicheOf", "Fitness"]
