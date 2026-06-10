"""GENESIS — Generative Engine for Networked Ideation, Synthesis & Specification.

Phase α public surface:
  run / Dependencies   — the wired pipeline (question -> verified Report).
  default_config / Config / config_hash — configuration + reproducibility anchor.
"""

from __future__ import annotations

from .config import Config, config_hash, default_config
from .runner import Dependencies, run

__all__ = ["run", "Dependencies", "Config", "default_config", "config_hash"]
