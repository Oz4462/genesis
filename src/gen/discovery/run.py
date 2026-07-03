"""run — the one-call discovery entry that ties the loop together (build doc Anhang B).

``discover(problem)`` is the public Phase-1 entry point: it runs the engine and records
EVERY candidate — kept and rejected — into a Discovery Graph (creating one if none is
passed, or appending to a long-lived one so the graph accumulates across runs and dedups
re-discoveries). It returns both the honest verdicts and the graph, so a caller gets the
result and the provenance in a single step. Deterministic; offline.
"""

from __future__ import annotations

from .engine import DEFAULT_R2_THRESHOLD, DiscoveryProblem, DiscoveryResult, discover_new_formulas
from .graph import DiscoveryGraph


def discover(
    problem: DiscoveryProblem,
    *,
    graph: DiscoveryGraph | None = None,
    known_laws: dict[str, dict[str, float]] | None = None,
    provenance: tuple[str, ...] = ("mensch",),
    timestamp: str | None = None,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
) -> tuple[DiscoveryResult, DiscoveryGraph]:
    """Run a discovery and record it. Returns ``(result, graph)``: `result` carries the
    validated verdicts + the full candidate record; `graph` is the Discovery Graph the run
    was deposited into (a fresh one unless `graph` is supplied, so callers can accumulate).
    """
    g = graph if graph is not None else DiscoveryGraph()
    result = discover_new_formulas(problem, known_laws=known_laws, r2_threshold=r2_threshold)
    g.add_result(result, target_name=problem.target.name, provenance=provenance, timestamp=timestamp)
    return result, g
