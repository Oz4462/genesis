"""Vendored ANAMNESIS memory primitives (storage + conformal + retrieve).

Vendored — NOT a pip dependency — on purpose: the upstream `anamnesis` package
declares `anthropic` and `openai` as hard core dependencies and its top-level
`__init__` imports them transitively, which would drag cloud-LLM SDKs into GENESIS.
GENESIS is local-first / anti-cloud-leak, so we vendor only the four modules that
the cross-run memory needs — all numpy + stdlib, zero cloud deps.

Upstream: C:/Users/Ozan/Desktop/alle apps/ANAMNESIS/anamnesis-py/src/anamnesis
Owner: Ozan Küsmez (same author as GENESIS) — vendoring is licence-clean.
Pinned: anamnesis v0.1.0 (2026-06-13). See WHY.md for the update procedure.

Only intra-package imports were rewritten to relative form; logic is unchanged so
the behaviour proven in PoV-2 (correct reuse + honest abstention with a real
embedder) carries over verbatim.
"""

from __future__ import annotations

from .conformal import ConformalCalibrator, ReuseBound
from .retrieve import ConformalRetriever, RetrievalResult
from .storage import Embedder, ReasoningStep, TraceStore

__all__ = [
    "ConformalCalibrator",
    "ReuseBound",
    "ConformalRetriever",
    "RetrievalResult",
    "Embedder",
    "ReasoningStep",
    "TraceStore",
]
