"""GENESIS — Generative Engine for Networked Ideation, Synthesis & Specification.

Public surface:
  run / run_solution / run_specification — the wired α/β/γ pipelines
  Dependencies                           — the injection point for models/backends
  default_config / Config / config_hash  — configuration + reproducibility anchor
  assess_specification                   — the quality engine's honest verdict over a
                                           Specification (lazy: importing it pulls the
                                           physics stack / numpy; `import gen` stays light)
  process_dream                          — LUMENCRUCIBLE HORIZON entry (dream → hammer + ε/ζ certs + RunState)
                                           (lazy import via grenzverschiebung.lumencrucible)
"""

from __future__ import annotations

from .config import Config, config_hash, default_config
from .runner import Dependencies, run, run_solution, run_specification

__all__ = [
    "run", "run_solution", "run_specification", "Dependencies",
    "Config", "default_config", "config_hash", "assess_specification",
    "process_dream",  # LUMEN HORIZON entry (full cert seams)
]


def __getattr__(name: str):
    # PEP 562 lazy export: the assessment pulls the physics validators (numpy); keep
    # `import gen` dependency-light for consumers that only run the α/β/γ pipelines.
    if name == "assess_specification":
        from .pipeline import assess_specification
        return assess_specification
    # Math-research branch (lazy: pulls sympy/mpmath; keep `import gen` light).
    if name in ("assess_identity", "assess_inequality", "explore_family", "run_identity_research",
                "AssumptionManifest", "IdentityArtifact", "NoveltyIndex", "OnlineNoveltyBackend",
                "ConjectureTemplate", "load_exact_physical_anchors", "scipy_special_eval", "verify_formula_numeric"):
        from . import identity_research as _ir
        return getattr(_ir, name)

    # Formula / authoritative constants (lazy: pulls codata + registry + dlmf, no heavy deps at import time)
    if name in ("PhysicalConstant", "load_codata_constants", "get_constant",
                "codata_table_source_ref", "make_codata_constant_claim", "content_hash_of",
                "DlmfEntry", "fetch_dlmf_entry", "dlmf_source_ref", "load_curated_dlmf",
                "WikidataLawHit", "search_physical_law", "get_formula_for", "sparql_query",
                "FormulaRecord", "FormulaRegistry"):
        from . import formulas as _f
        return getattr(_f, name)
    if name in ("autonomous_stage", "promote_to_established", "PromotionLedger"):
        from . import research_promotion as _rp
        return getattr(_rp, name)
    # HORIZON LUMEN entrypoint (process_dream): first-class dream→hammer + seam/memory cert attach to RunState.
    # Exposed for conductor/CLI/web consumers; guarded in lumencrucible; full 4L seams.
    if name == "process_dream":
        from .grenzverschiebung.lumencrucible import process_dream
        return process_dream
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
