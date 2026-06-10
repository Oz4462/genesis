"""GENESIS typed errors.

Anti-hallucination depends on failing loudly. Where a system might be tempted to
guess a value, GENESIS raises instead. Every error here represents a situation
where a silent default would risk fabricating reality.
"""

from __future__ import annotations


class GenesisError(Exception):
    """Base for all GENESIS errors."""


class UnsourcedClaimError(GenesisError):
    """Raised when a Claim is constructed without any source.

    This is the most important guard in the system: it makes a sourceless fact
    structurally impossible, not merely discouraged.
    """

    def __init__(self, claim_id: str, text: str) -> None:
        super().__init__(
            f"Claim {claim_id!r} has no sources: {text!r}. "
            "A fact without provenance cannot exist in GENESIS (CLAUDE.md §1)."
        )


class UngroundedApproachError(GenesisError):
    """Raised when an Approach is constructed without any grounding claim.

    The Phase β pendant of UnsourcedClaimError: it makes a fabricated (ungrounded)
    solution approach structurally impossible, not merely discouraged. An approach
    is only 'real' if anchored in at least one Claim that it exists and is used for
    the problem (PHASE_BETA.md §0/§4).
    """

    def __init__(self, approach_id: str, name: str) -> None:
        super().__init__(
            f"Approach {approach_id!r} ({name!r}) has no grounding claim. "
            "A solution approach without verified grounding cannot exist in GENESIS "
            "(PHASE_BETA.md §0)."
        )


class FetchFailedError(GenesisError):
    """A source could not be retrieved. The source must NOT be cited as fact."""

    def __init__(self, url_or_id: str, reason: str) -> None:
        super().__init__(f"Fetch failed for {url_or_id!r}: {reason}")


class NoIndependentSourceError(GenesisError):
    """`skeptic` could not find a source independent of `scholar`'s sources.

    Not necessarily fatal — leads to status UNSUPPORTED — but never to a silent
    VERIFIED.
    """


class ModelConflictError(GenesisError):
    """Generator and verifier resolved to the same model family.

    Cross-model verification is mandatory (PHASE_ALPHA §3.4 / config). Same-model
    self-checking does not count as verification.
    """

    def __init__(self, generator: str, verifier: str) -> None:
        super().__init__(
            f"Verifier model family ({verifier!r}) must differ from generator "
            f"({generator!r}). Self-verification is not verification."
        )


class RefineBudgetExceeded(GenesisError):
    """Re-research rounds hit the configured limit; remaining items become gaps."""


class SearchBackendError(GenesisError):
    """A search backend could not be reached or returned an unusable response.

    Raised loudly so a degraded backend is visible to the conductor (which may
    continue with other backends) instead of silently yielding zero candidates —
    a silent empty result would hide a systemic outage.
    """

    def __init__(self, backend: str, reason: str) -> None:
        super().__init__(f"Search backend {backend!r} failed: {reason}")


class LLMOutputError(GenesisError):
    """An LLM returned output that could not be parsed into the expected shape.

    Handled per-item by agents (the offending source/claim is skipped and logged)
    so a single malformed response never fabricates content nor crashes a run —
    but it is never silently ignored either.
    """

    def __init__(self, agent: str, detail: str) -> None:
        super().__init__(f"{agent}: unparseable LLM output: {detail}")
