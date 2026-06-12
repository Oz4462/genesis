"""GENESIS — Generative Engine for Networked Ideation, Synthesis & Specification.

Public surface:
  run / run_solution / run_specification — the wired α/β/γ pipelines
  Dependencies                           — the injection point for models/backends
  default_config / Config / config_hash  — configuration + reproducibility anchor
  assess_specification                   — the quality engine's honest verdict over a
                                           Specification (lazy: importing it pulls the
                                           physics stack / numpy; `import gen` stays light)
"""

from __future__ import annotations

from .config import Config, config_hash, default_config
from .runner import Dependencies, run, run_solution, run_specification

__all__ = [
    "run", "run_solution", "run_specification", "Dependencies",
    "Config", "default_config", "config_hash", "assess_specification",
]


def __getattr__(name: str):
    # PEP 562 lazy export: the assessment pulls the physics validators (numpy); keep
    # `import gen` dependency-light for consumers that only run the α/β/γ pipelines.
    if name == "assess_specification":
        from .pipeline import assess_specification
        return assess_specification
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
