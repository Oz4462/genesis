"""GENESIS opt-in live wiring: compose the optional integrations around the core
pipeline (memory + audit). Importing this pulls the `verify` extra; the core
pipeline stays numpy-only. See audited_run.py."""

from __future__ import annotations

from .audited_run import AuditedRunResult, audited_run
from .drift import detect_run_drift, embed_texts

__all__ = ["AuditedRunResult", "audited_run", "detect_run_drift", "embed_texts"]
