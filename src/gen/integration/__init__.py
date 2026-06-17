"""GENESIS opt-in live wiring: compose the optional integrations around the core
pipeline (memory + audit). The audited-run path pulls the ``verify`` extra (trust-core);
the core pipeline — and the default-off side-channel hooks (e.g. identity_research_hook) —
stay numpy-only. Exports are therefore LAZY (PEP 562): importing a submodule that does NOT
need trust-core (the research hook) must not drag the extra in. See audited_run.py."""

from __future__ import annotations

__all__ = ["AuditedRunResult", "audited_run", "detect_run_drift", "embed_texts"]


def __getattr__(name: str):
    # Lazy so `import gen.integration.identity_research_hook` (numpy-only) does not require
    # the optional `verify` extra that audited_run/drift pull in.
    if name in ("AuditedRunResult", "audited_run"):
        from .audited_run import AuditedRunResult, audited_run
        return {"AuditedRunResult": AuditedRunResult, "audited_run": audited_run}[name]
    if name in ("detect_run_drift", "embed_texts"):
        from .drift import detect_run_drift, embed_texts
        return {"detect_run_drift": detect_run_drift, "embed_texts": embed_texts}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
