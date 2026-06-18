"""GENESIS discovery — the universe-explorer core (GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md).

The honest core loop of the build plan: a human (or Grok) hands in an idea + data; the
engine proposes candidate formulas under DIMENSIONAL constraints (Buckingham-π, the
AI-Feynman insight), fits them, runs every candidate through the EXISTING GENESIS gates
(dimensional consistency C-15, independent recompute C-6, fit/physics consistency,
uncertainty) under the δ-asymmetry, and records every candidate — kept AND rejected — in
a Discovery Graph with provenance. The verdict is honest: ``bestaetigt`` / ``widerlegt`` /
``unentschieden``, never a fabricated discovery.

This is Phase 1 of the build doc (the ``discover_new_formulas`` DoD, Anhang B) plus the
Discovery Graph (4.6 / Anhang C) and the Tournament loop (3.1), validated by the
Rediscovery benchmark (Phase 4 — can it recover Kepler / the ideal gas law from data?).
Everything here is offline, deterministic and numpy/sympy-only; nothing claims a discovery
the gates did not earn.

Exports are lazy (PEP 562) so importing the package is cheap and a missing optional path
never drags weight in.
"""

from __future__ import annotations

__all__ = [
    "Variable",
    "Constant",
    "DiscoveryProblem",
    "Candidate",
    "DiscoveryVerdict",
    "DiscoveryResult",
    "symbolic_regress",
    "discover_new_formulas",
    "dimensional_power_law",
    "discover",
    "DiscoveryGraph",
    "GraphNode",
    "evolve",
    "TournamentReport",
    "rediscovery_benchmark",
    "BenchmarkCase",
    "kepler_case",
    "ideal_gas_case",
]


def __getattr__(name: str):
    # Lazy, and — like gen.integration — cached into globals() so a same-named submodule
    # can never shadow a function export.
    if name in ("Variable", "Constant", "DiscoveryProblem", "Candidate",
                "DiscoveryVerdict", "DiscoveryResult", "symbolic_regress",
                "discover_new_formulas", "dimensional_power_law"):
        from . import engine as _m
        for n in ("Variable", "Constant", "DiscoveryProblem", "Candidate",
                  "DiscoveryVerdict", "DiscoveryResult", "symbolic_regress",
                  "discover_new_formulas", "dimensional_power_law"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("DiscoveryGraph", "GraphNode"):
        from . import graph as _m
        globals()["DiscoveryGraph"] = _m.DiscoveryGraph
        globals()["GraphNode"] = _m.GraphNode
        return globals()[name]
    if name == "discover":
        from .run import discover as _discover
        globals()["discover"] = _discover
        return _discover
    if name in ("evolve", "TournamentReport"):
        from . import tournament as _m
        globals()["evolve"] = _m.evolve
        globals()["TournamentReport"] = _m.TournamentReport
        return globals()[name]
    if name in ("rediscovery_benchmark", "BenchmarkCase", "kepler_case", "ideal_gas_case"):
        from . import benchmark as _m
        for n in ("rediscovery_benchmark", "BenchmarkCase", "kepler_case", "ideal_gas_case"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
