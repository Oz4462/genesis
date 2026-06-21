"""Grounding integrity — is the claim graph soundly corroborated (TIER 3 #3).

The research's knowledge-graph / grounding pillar (KG integration improves factuality; cross-
model corroboration) points at two graph-level properties GENESIS should hold but did not
measure as such:

  • CORROBORATION INDEPENDENCE — a VERIFIED claim is only as trustworthy as the INDEPENDENCE of
    its corroboration. If the skeptic's verification sources merely re-cite the scholar's own
    sources, the "verification" is circular, not independent. This module checks that, for every
    verified claim, the verification sources are DISJOINT from the original sources — genuine
    cross-corroboration, the graph property that makes "verified" mean something.

  • REPORT GROUNDING COVERAGE — the FActScore principle that every asserted sentence maps to a
    real, non-refuted claim. Given a Report's statement->claim map, it flags any sentence backed
    by a missing claim (dangling) or a REFUTED claim (a contradiction asserted as fact), and
    reports the coverage.

Both are deterministic graph checks over the existing ledger types — no model calls, no new
dependency. They complement the per-claim gates with a graph-level integrity view: not just "is
each claim sourced", but "is the corroboration independent and the report fully grounded". A
clean result is necessary, not sufficient; it does not judge whether the sources are themselves
correct. Offline, pure functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core.state import Claim, ClaimStatus, Report


@dataclass
class CorroborationReport:
    n_verified: int
    circular: list[str] = field(default_factory=list)   # verified claims whose corroboration
    #                                                     re-cites an original source (not independent)

    @property
    def independent_rate(self) -> float:
        return (self.n_verified - len(self.circular)) / self.n_verified if self.n_verified else 1.0

    @property
    def ok(self) -> bool:
        return not self.circular


def corroboration_independence(claims: list[Claim]) -> CorroborationReport:
    """Check that every VERIFIED claim is corroborated by sources INDEPENDENT of its own — the
    verification source ids must be disjoint from the original source ids. Returns the verified
    count and the ids of any claim whose corroboration is circular (re-cites an original source).
    Deterministic."""
    verified = [c for c in claims if c.status is ClaimStatus.VERIFIED]
    circular: list[str] = []
    for c in verified:
        original = {s.url_or_id for s in c.sources}
        corroborating = {s.url_or_id for s in c.verification}
        if original & corroborating:                    # any reused source -> not independent
            circular.append(c.id)
    return CorroborationReport(len(verified), circular)


@dataclass
class GroundingCoverage:
    n_statements: int
    n_grounded: int
    dangling: list[tuple[str, str]] = field(default_factory=list)     # (sentence, missing claim_id)
    refuted_backed: list[tuple[str, str]] = field(default_factory=list)  # (sentence, refuted claim_id)

    @property
    def coverage(self) -> float:
        return self.n_grounded / self.n_statements if self.n_statements else 1.0

    @property
    def ok(self) -> bool:
        return not self.dangling and not self.refuted_backed


def report_grounding(report: Report, claims: list[Claim]) -> GroundingCoverage:
    """Check that every sentence in a Report's statement->claim map is backed by a real,
    non-refuted claim. Flags sentences whose claim id is missing from `claims` (dangling) or
    whose claim is REFUTED (a contradiction asserted as fact), and reports the coverage
    (sentences soundly grounded / total). Deterministic."""
    by_id = {c.id: c for c in claims}
    dangling: list[tuple[str, str]] = []
    refuted_backed: list[tuple[str, str]] = []
    grounded = 0
    for sentence, claim_id in report.statement_to_claim.items():
        claim = by_id.get(claim_id)
        if claim is None:
            dangling.append((sentence, claim_id))
        elif claim.status is ClaimStatus.REFUTED:
            refuted_backed.append((sentence, claim_id))
        else:
            grounded += 1
    return GroundingCoverage(len(report.statement_to_claim), grounded, dangling, refuted_backed)
