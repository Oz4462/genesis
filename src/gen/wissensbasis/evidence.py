"""Evidence Extractor (Bauwelle B4).

Genesis does not hoard full text. It extracts small, structured, provenance-bearing
evidence from a source — an ``EvidenceValue`` — and lets ``SourcePolicy`` (B3) decide
whether even that snippet may be persisted.

An ``EvidenceValue`` is the quantitative pendant of ``core.state.Claim``: a number is
only usable evidence if it carries a source, a unit, and a stated validity range.
Constructing one without these raises ``EvidenceIntegrityError`` — a context-free or
unitless number is the Mars-Climate-Orbiter failure class and must not exist
(GENESIS Kernprinzip 1; docs/GENESIS_PLATFORM_BUILD_TODO.md §3 B4).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import EvidenceIntegrityError
from ..core.state import SourceRef, SourceSupport


@dataclass(frozen=True)
class EvidenceValue:
    """A structured quantitative extract from a source (PLAN B4).

    `claim_text`     what the value asserts, e.g. "max continuous discharge current".
    `value`          the numeric value.
    `unit`           physical unit ("A", "Wh/kg", ...); use "dimensionless" for ratios/counts.
    `validity_range` applicability domain, e.g. "25 °C, pack level"; never empty.
    `source`         SourceRef provenance (url/id, retrieved, content_hash, span).
    `uncertainty`    optional ± / tolerance note.
    `quelle`         build provenance (which extractor/run produced this).

    Rejected at construction (fail-closed) if it lacks a source, a unit, or a
    validity range — there is no context-free fact in GENESIS.
    """

    claim_text: str
    value: float
    unit: str
    validity_range: str
    source: SourceRef
    uncertainty: str | None = None
    quelle: str | None = None

    def __post_init__(self) -> None:
        if self.source is None or not getattr(self.source, "url_or_id", "").strip():
            raise EvidenceIntegrityError(self.claim_text, "no source")
        if not self.unit or not self.unit.strip():
            raise EvidenceIntegrityError(
                self.claim_text, "no unit (use 'dimensionless' for ratios/counts)"
            )
        if not self.validity_range or not self.validity_range.strip():
            raise EvidenceIntegrityError(self.claim_text, "no validity range / applicability domain")


def extract_evidence_value(
    *,
    claim_text: str,
    value: float,
    unit: str,
    validity_range: str,
    source_url: str,
    content_hash: str | None = None,
    span: str | None = None,
    retrieved: bool = True,
    support: SourceSupport = SourceSupport.SUPPORTS,
    uncertainty: str | None = None,
    quelle: str | None = None,
) -> EvidenceValue:
    """Turn a raw extracted datapoint (e.g. a datasheet value) into a structured,
    provenance-bearing ``EvidenceValue`` (PLAN B4 DoD).

    Builds the ``SourceRef`` from ``source_url`` (+ hash/span) and delegates the
    integrity checks to ``EvidenceValue`` — so a missing source URL, unit or
    validity range raises ``EvidenceIntegrityError`` rather than yielding a
    context-free number.
    """
    if not source_url or not source_url.strip():
        raise EvidenceIntegrityError(claim_text, "no source URL/id")
    src = SourceRef(
        url_or_id=source_url,
        retrieved=retrieved,
        content_hash=content_hash,
        span=span,
        support=support,
    )
    return EvidenceValue(
        claim_text=claim_text,
        value=value,
        unit=unit,
        validity_range=validity_range,
        source=src,
        uncertainty=uncertainty,
        quelle=quelle or "wissensbasis.evidence.extract_evidence_value (PLAN B4)",
    )
