"""evolve_engine — the evolutionary-search seam: in-house MAP-Elites (offline) / external engine (opt-in).

Open-ended invention is a quality-DIVERSITY search, not a single optimum: MAP-Elites (Mouret & Clune 2015)
keeps the best genome per behavioral NICHE, so the loop returns a diverse Pareto-like set of inventions rather
than one over-fit winner. The offline default :class:`MapElitesEngine` is a deterministic, dependency-free
MAP-Elites with optional ISLANDS (independent archives merged per niche — a diversity pump, after OpenEvolve/
ShinkaEvolve). An external evolutionary engine is an opt-in, import-guarded adapter behind the same seam.

Generic by design: ``evaluate``/``mutate``/``niche_of`` are injected, so this same engine drives concept-level
invention (TE phases) without knowing the genome type. Deterministic given a seed.
"""

from __future__ import annotations

import importlib.util
import random
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence, runtime_checkable

from ..core.errors import GenesisError

Evaluate = Callable[[Any], float]                 # genome -> score (higher is better)
Mutate = Callable[[Any, random.Random], Any]      # (genome, rng) -> child genome (rng for determinism)
NicheOf = Callable[[Any], Any]                     # genome -> hashable behavioral descriptor


class EvolveEngineUnavailable(GenesisError):
    """An external evolutionary engine was selected but its package is not installed. Loud — the caller falls
    back to the offline MapElitesEngine rather than getting a silently-degraded search."""

    def __init__(self, tool: str) -> None:
        super().__init__(f"evolve engine {tool!r} is not installed "
                         f"(opt-in dependency; MapElitesEngine is the offline default)")


@dataclass(frozen=True)
class Elite:
    """The best genome found for one behavioral niche, with its score."""

    genome: Any
    niche: Any
    score: float


@runtime_checkable
class EvolveEngine(Protocol):
    """A quality-diversity search: from seed genomes, return the best genome per niche."""

    name: str

    def evolve(self, seeds: Sequence[Any], *, evaluate: Evaluate, mutate: Mutate, niche_of: NicheOf,
               generations: int, seed: int = 0) -> list[Elite]:
        ...


def _run_island(seeds, evaluate, mutate, niche_of, generations, rng) -> dict[Any, Elite]:
    archive: dict[Any, Elite] = {}

    def consider(genome: Any) -> None:
        niche = niche_of(genome)
        score = evaluate(genome)
        current = archive.get(niche)
        if current is None or score > current.score:
            archive[niche] = Elite(genome=genome, niche=niche, score=score)

    for g in seeds:
        consider(g)
    for _ in range(generations):
        if not archive:
            break
        parent = rng.choice(list(archive.values()))
        consider(mutate(parent.genome, rng))
    return archive


class MapElitesEngine:
    """Offline default MAP-Elites with optional islands. Satisfies :class:`EvolveEngine`.

    ``islands`` independent archives run with distinct sub-seeds and are merged per niche keeping the best —
    the diversity pump that resists collapse to a single niche. Deterministic given ``seed``; the returned
    elites are sorted by niche for reproducible order."""

    name = "map-elites"

    def __init__(self, *, islands: int = 1) -> None:
        if islands < 1:
            raise ValueError("islands must be >= 1")
        self._islands = islands

    def evolve(self, seeds: Sequence[Any], *, evaluate: Evaluate, mutate: Mutate, niche_of: NicheOf,
               generations: int, seed: int = 0) -> list[Elite]:
        if generations < 0:
            raise ValueError("generations must be >= 0")
        seeds = list(seeds)
        if not seeds:
            raise ValueError("evolve needs at least one seed genome")
        merged: dict[Any, Elite] = {}
        for k in range(self._islands):
            rng = random.Random(seed * 100003 + k)            # distinct, deterministic per-island stream
            for niche, elite in _run_island(seeds, evaluate, mutate, niche_of, generations, rng).items():
                current = merged.get(niche)
                if current is None or elite.score > current.score:
                    merged[niche] = elite
        return [merged[n] for n in sorted(merged, key=repr)]


class OpenEvolveEngine:
    """Opt-in adapter for an external evolutionary engine (OpenEvolve / ShinkaEvolve, Apache-2.0) behind the
    same seam. Import-guarded: ``available()`` is False without the package and ``evolve`` raises
    :class:`EvolveEngineUnavailable`. STATUS: live path BLOCKED here (package not installed); the tested
    contract is the clean absent-skip. The offline MapElitesEngine follows the same MAP-Elites principle."""

    name = "openevolve"

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("openevolve") is not None

    def evolve(self, seeds: Sequence[Any], *, evaluate: Evaluate, mutate: Mutate, niche_of: NicheOf,
               generations: int, seed: int = 0) -> list[Elite]:
        if not self.available():
            raise EvolveEngineUnavailable("openevolve")
        raise EvolveEngineUnavailable("openevolve")  # live wiring is owner-gated; never a fabricated result


def default_engine() -> EvolveEngine:
    """The offline default evolutionary engine (in-house MAP-Elites, no dependency)."""
    return MapElitesEngine()


__all__ = ["Elite", "EvolveEngine", "MapElitesEngine", "OpenEvolveEngine", "EvolveEngineUnavailable",
           "Evaluate", "Mutate", "NicheOf", "default_engine"]
