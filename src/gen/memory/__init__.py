"""GENESIS cross-run memory: durable, conformal-bounded verified-facts library.

Public surface only — the conformal/retrieval internals are vendored under
`_vendor/` (see `_vendor/WHY.md`) to keep cloud-LLM SDKs out of GENESIS.
"""

from __future__ import annotations

from .verified_facts import (
    RecalledFact,
    RecallResult,
    VerifiedFactsLibrary,
    ollama_embedder,
)

__all__ = ["VerifiedFactsLibrary", "RecalledFact", "RecallResult", "ollama_embedder"]
