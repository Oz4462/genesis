"""GENESIS core state — the typed data that flows through the pipeline.

This is the single source of truth for the shapes that agents read and write.
The Claim is the most important type in the whole system: it is how the
anti-hallucination guarantee is made concrete. A Claim cannot meaningfully exist
without provenance.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Verification status -----------------------------------------------------

class ClaimStatus(enum.Enum):
    """Lifecycle of a factual claim.

    UNVERIFIED  Just extracted by `scholar`; not yet independently checked.
    VERIFIED    `skeptic` found independent support meeting the threshold.
    REFUTED     A credible source contradicts it.
    UNSUPPORTED `skeptic` found no independent support; remains an unbacked claim.
    """

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REFUTED = "refuted"
    UNSUPPORTED = "unsupported"


# --- Provenance --------------------------------------------------------------

@dataclass(frozen=True)
class SourceRef:
    """A reference to a retrievable source backing (or contradicting) a claim.

    `url_or_id`     web URL, arXiv id, DOI, PubMed id, etc.
    `retrieved`     True only if the source was actually fetched in this run.
    `content_hash`  hash of fetched content, for reproducibility.
    `span`          optional location within the source (offsets/section).
    `support`       whether this source SUPPORTS or CONTRADICTS the claim.
    """

    url_or_id: str
    retrieved: bool
    content_hash: str | None = None
    span: str | None = None
    support: "SourceSupport" = None  # type: ignore[assignment]


class SourceSupport(enum.Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


@dataclass(frozen=True)
class SourceCandidate:
    """A candidate source found by `scout`, before deep reading.

    Not yet a fact — just 'this might be relevant, and here is why'. `scholar`
    decides whether reading it actually yields any Claim.
    """

    url_or_id: str
    title: str | None
    backend: str            # which SearchBackend produced it
    relevance_note: str     # short justification, not a fact
    fetched_ok: bool = False


# --- The Claim (heart of the system) -----------------------------------------

@dataclass
class Claim:
    """A single atomic, independently checkable factual statement.

    INVARIANT (enforced in LedgerStore and DB): `sources` is non-empty at the
    moment a Claim is persisted by `scholar`. There is no such thing as a
    sourceless fact in GENESIS.

    `text`            one atomic assertion, no compound 'and'/'because' chains.
    `sources`         provenance from the agent that produced the claim.
    `quote`           minimal verbatim support snippet (kept SHORT, < ~15 words).
    `status`          see ClaimStatus.
    `confidence`      0..1, updated by `skeptic`.
    `verification`    independent sources gathered by `skeptic` (must be NEW).
    `produced_by`     agent name (provenance of the reasoning, not the fact).
    `model`           model family that produced it (for cross-model auditing).
    """

    id: str
    text: str
    sources: list[SourceRef]
    quote: str | None = None
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    confidence: float = 0.0
    verification: list[SourceRef] = field(default_factory=list)
    produced_by: str = ""
    model: str = ""
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        # Fail fast: a claim with no sources must never be constructed as a fact.
        if not self.sources:
            from .errors import UnsourcedClaimError
            raise UnsourcedClaimError(self.id, self.text)


# --- The Approach (heart of Phase β) -----------------------------------------

@dataclass
class Approach:
    """A distinct, REAL solution approach to a (solved) problem.

    INVARIANT (enforced here AND re-checked by GATE β): `grounding` is non-empty.
    An approach must point to at least one Claim establishing that it is real and
    used for this problem. A fabricated approach is the β-equivalent of a sourceless
    fact — and is made structurally impossible (UngroundedApproachError), exactly as
    a sourceless Claim is. See PHASE_BETA.md §0/§4.

    An Approach asserts NO new fact of its own. All factual substance lives in the
    referenced ledger Claims; `grounding` and `tradeoffs` hold claim_ids. The
    `synthesizer` that builds an Approach is a structurer, not a fact source — the
    same discipline the `conductor` follows when assembling a Report.

    `name`         short human label of the approach (NOT a fact; e.g. "Token bucket").
    `grounding`    claim_ids of VERIFIED claims establishing the approach exists /
                   is used for the problem. MUST be non-empty.
    `tradeoffs`    claim_ids of claims describing properties / pros / cons.
    `produced_by`  agent name (provenance of the structuring, not of any fact).
    `model`        model family that produced the structuring (for auditing).
    """

    id: str
    name: str
    grounding: list[str]
    tradeoffs: list[str] = field(default_factory=list)
    produced_by: str = ""
    model: str = ""
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        # Fail fast: an approach with no grounding claim must never be constructed.
        if not self.grounding:
            from .errors import UngroundedApproachError
            raise UngroundedApproachError(self.id, self.name)


# --- Questions & report ------------------------------------------------------

@dataclass(frozen=True)
class Question:
    """The human's input — the intentional spark GENESIS amplifies."""

    raw: str
    run_id: str


@dataclass(frozen=True)
class SubQuestion:
    """A researchable decomposition of the original Question."""

    id: str
    text: str
    parent_run_id: str


@dataclass
class Report:
    """Final output of Phase α.

    Assembled by `conductor` ONLY from ledger claims. The conductor invents
    nothing: every factual sentence maps to a claim_id. UNSUPPORTED claims may
    appear, but only flagged as such; REFUTED claims never appear as fact.
    """

    run_id: str
    question: str
    body: str                       # human-readable, every fact mapped below
    statement_to_claim: dict[str, str] = field(default_factory=dict)  # sentence -> claim_id
    gaps: list[str] = field(default_factory=list)   # explicitly unanswerable parts
    sources_used: list[str] = field(default_factory=list)


@dataclass
class SolutionReport:
    """Final output of Phase β — the real solution space for a solved problem.

    Assembled by `synthesizer`/`conductor` ONLY from ledger claims. Every asserted
    `Approach` is grounded in VERIFIED claims and every trade-off is a ledger claim
    (GATE β enforces this). Approaches that cannot be grounded are surfaced as gaps,
    never as fact. If no approach can be grounded, `approaches` is empty and `gaps`
    explains why (abstention) — the β analogue of α's "No claim could be verified".

    `problem`        the human's solved-problem input.
    `approaches`     the grounded approaches asserted as real (may be empty).
    `gaps`           ungroundable approaches, abstention, or contested verdicts —
                     explicitly flagged, never presented as fact.
    `claim_ids_used` every claim referenced by any approach (for audit/repro).
    """

    run_id: str
    problem: str
    approaches: list["Approach"] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    claim_ids_used: list[str] = field(default_factory=list)


# --- Run state ---------------------------------------------------------------

@dataclass
class RunState:
    """Everything one run carries. Checkpointable for reproducibility.

    Each agent owns specific fields and must not mutate others':
      scout      -> candidates
      scholar    -> claims (creates, status=UNVERIFIED)
      skeptic    -> claims (updates status/confidence/verification)
      synthesizer-> approaches, solution_report (Phase β; references claim_ids only)
      conductor  -> sub_questions, report, round counters
    """

    question: Question
    sub_questions: list[SubQuestion] = field(default_factory=list)
    candidates: list[SourceCandidate] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    report: Report | None = None
    approaches: list[Approach] = field(default_factory=list)
    solution_report: "SolutionReport | None" = None
    refine_round: int = 0
    log: list[str] = field(default_factory=list)
