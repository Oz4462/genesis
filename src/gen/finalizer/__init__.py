"""gen.finalizer — the last pipeline stage: package GENESIS results into a deliverable.

``professional_package.finalize_pipeline(result)`` aggregates whatever a GENESIS run actually produced
(claims, gate verdicts, spec, bundle, goldset score, optional research) into a real, honest deliverable
(Markdown + a styled printable HTML; PDF only if a backend is installed). It NEVER fabricates a score, a
gate result, or a "COMPLETE" banner — missing inputs are reported as missing.
"""

from .professional_package import ProfessionalPackage, finalize_pipeline

__all__ = ["ProfessionalPackage", "finalize_pipeline"]
