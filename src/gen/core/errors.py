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


class UngroundedPossibilityError(GenesisError):
    """Raised when a Possibility is constructed without any grounding.

    The Phase φ pendant of UnsourcedClaimError / UngroundedApproachError: a
    *possibility* (a direction a spark could take) may only exist if it is anchored
    to at least one real mechanism or precedent in the ledger — no invented
    neighbourhood. Divergence has no completeness gate, so this anchoring (plus the
    loud "grounded sample, not the whole space" disclaimer enforced by GATE φ) is the
    only honest guarantee. See HORIZON.md §3/§5.
    """

    def __init__(self, possibility_id: str, statement: str) -> None:
        super().__init__(
            f"Possibility {possibility_id!r} ({statement!r}) has no grounding. "
            "A possibility without an anchored mechanism/precedent cannot exist in "
            "GENESIS (HORIZON.md §3)."
        )


class UngroundedExperimentError(GenesisError):
    """Raised when a FalsificationExperiment has no prediction to falsify.

    The Phase δ⁺ pendant of the grounding guards: an experiment must reference the
    computed/derived claim or quantity whose prediction it tests. An experiment with no
    grounding tests nothing — structurally impossible (HORIZON.md §2B).
    """

    def __init__(self, experiment_id: str, measurand: str) -> None:
        super().__init__(
            f"FalsificationExperiment {experiment_id!r} ({measurand!r}) grounds in no "
            "prediction. An experiment must test a computed claim/quantity (HORIZON.md §2B)."
        )


class UnsourcedMeasurementError(GenesisError):
    """Raised when a Measurement is constructed without provenance.

    A measurement is a factual claim about the world: where/how it was read. Without a
    source it is a fabricated number — structurally impossible, the δ⁺ analogue of
    UnsourcedClaimError (HORIZON.md §2B).
    """

    def __init__(self, measurement_id: str) -> None:
        super().__init__(
            f"Measurement {measurement_id!r} has no source. A measurement without "
            "provenance cannot exist in GENESIS (HORIZON.md §2B)."
        )


class UngroundedFailureModeError(GenesisError):
    """Raised when a declared failure mode has no detectable grounding.

    The Phase delta+ coverage pendant of the grounding guards: a failure mode may be
    declared only if it is anchored in an actual selector trigger, constraint, measured
    gap, or externally reviewed candidate. Otherwise the coverage certificate could
    invent a threat surface and then claim to have handled it.
    """

    def __init__(self, mode_id: str, label: str) -> None:
        super().__init__(
            f"FailureMode {mode_id!r} ({label!r}) has no grounding. A coverage "
            "certificate may only cover failure modes anchored in the spec, selector, "
            "SMT result, or reviewed evidence (HORIZON.md §2B)."
        )


class UncoveredFailureModeError(GenesisError):
    """Raised when a coverage item has no proof of checking or honest residual risk."""

    def __init__(self, mode_id: str) -> None:
        super().__init__(
            f"FailureMode {mode_id!r} has no coverage evidence. A delta+ coverage "
            "certificate must say either 'checked' with evidence or 'untestable' with "
            "an explicit residual risk (HORIZON.md §2B)."
        )


class UnknownRegionError(GenesisError):
    """Raised when a KnownRegion is constructed without anchoring to any fact.

    The Phase χ pendant of the grounding guards: a 'known region' on the frontier map
    claims established knowledge, so it must anchor at least one VERIFIED claim. A region
    with no fact_ids is fabricated certainty — structurally impossible (HORIZON.md §2C).
    """

    def __init__(self, region_id: str) -> None:
        super().__init__(
            f"KnownRegion {region_id!r} anchors no fact. A region of 'known' "
            "territory without >= 1 verified claim cannot exist in GENESIS (HORIZON.md §2C)."
        )


class UnsourcedSourcingError(GenesisError):
    """Raised when a BOM sourcing (supplier/part/price) has no grounding claim.

    The procurement pendant of UnsourcedClaimError: a supplier, order number, or
    price is a factual claim about the world. It must reference at least one
    verified claim — there is no invented shop or price in GENESIS. In doubt the
    sourcing is omitted as an honest gap (PHASE_GAMMA_DEPTH.md §1).
    """

    def __init__(self, bom_id: str) -> None:
        super().__init__(
            f"BOM item {bom_id!r} asserts sourcing without a grounding claim. "
            "A supplier/part/price without provenance cannot exist in GENESIS "
            "(PHASE_GAMMA_DEPTH.md §1)."
        )


class UngroundedValueError(GenesisError):
    """Raised when a GROUNDED Quantity is constructed without any grounding claim.

    The Phase γ pendant of UnsourcedClaimError: a numeric value presented as a
    sourced fact must reference at least one ledger claim. A grounded value
    without grounding is a fabricated value — structurally impossible
    (PHASE_GAMMA.md §0/§3.1).
    """

    def __init__(self, quantity_id: str, name: str) -> None:
        super().__init__(
            f"Quantity {quantity_id!r} ({name!r}) is GROUNDED but has no grounding "
            "claim. A sourced value without provenance cannot exist in GENESIS "
            "(PHASE_GAMMA.md §3.1)."
        )


class InvalidDerivationError(GenesisError):
    """Raised when a Quantity's origin and its derivation field disagree.

    A DERIVED quantity without a Derivation cannot be recomputed — its value
    would be an unauditable guess. A non-DERIVED quantity carrying a Derivation
    (or grounding/rationale on the wrong origin) blurs provenance. Both are
    structural defects, rejected at construction (PHASE_GAMMA.md §3.1).
    """

    def __init__(self, quantity_id: str, detail: str) -> None:
        super().__init__(f"Quantity {quantity_id!r}: invalid derivation: {detail}")


class UndeclaredDecisionError(GenesisError):
    """Raised when a design choice is constructed without a rationale.

    A DECISION quantity or a Decision with an empty rationale/choice is a hidden
    decision — a choice disguised as fact. Decisions must be explicit and
    human-ratifiable (PHASE_GAMMA.md §0, hallucination face #4).
    """

    def __init__(self, item_id: str, detail: str) -> None:
        super().__init__(f"Decision {item_id!r} is undeclared: {detail}")


class FormulaError(GenesisError):
    """A derivation formula could not be parsed or evaluated safely.

    Raised loudly by the safe evaluator (verification/derivation.py) for
    anything outside the allowed arithmetic grammar, unknown identifiers,
    cycles, or division by zero. A formula that cannot be deterministically
    recomputed must never silently yield a value (PHASE_GAMMA.md §3.2).
    """

    def __init__(self, formula: str, reason: str) -> None:
        super().__init__(f"Formula {formula!r} failed: {reason}")


class UnitError(GenesisError):
    """A derivation formula is dimensionally inconsistent.

    Raised loudly when a formula adds/subtracts incommensurable quantities
    (e.g. mass + length), or when a DERIVED quantity's declared unit dimension
    does not match the dimension its formula implies. This is the famous
    Mars-Climate-Orbiter failure class (pound-force·s vs newton·s); dimensional
    homogeneity is "a first check on the correctness of an equation"
    (Kennedy 2009). A dimensionally inconsistent value must never silently
    enter a build specification (PHASE_GAMMA.md §0/§5, condition C-15).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(f"Dimensional inconsistency: {detail}")


class GeometryError(GenesisError):
    """A geometry node could not be reduced to a bounding box.

    Raised loudly (never a guessed extent) when AABB computation meets a node it
    cannot resolve — an unknown geometry kind, a missing parameter, or a
    parameter referencing an absent quantity. Phase δ validation assumes a
    GATE-γ-validated spec but fails loudly rather than fabricating geometry
    (PHASE_DELTA.md §3).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(f"Geometry error: {detail}")


class ToleranceError(GenesisError):
    """A general-tolerance lookup was asked for a value outside the verified table.

    GENESIS encodes only the ISO 2768-1 ranges it has verified against the
    standard. Outside them it raises rather than extrapolate a standard value it
    has not checked — a guessed tolerance is a fabricated engineering fact
    (PHASE_DELTA.md §10).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(f"Tolerance lookup failed: {detail}")


class ExportError(GenesisError):
    """A specification could not be deterministically exported.

    Raised loudly (never emit guessed output) when an exporter meets a node it
    cannot faithfully render — an unknown geometry kind, a missing parameter, or
    a parameter referencing a quantity that is absent. The exporter assumes a
    GATE-γ-validated spec, but fails loudly rather than fabricating a number
    (PHASE_GAMMA.md §0: no silent defaults at factual things).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(f"Export failed: {detail}")


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


class LLMTransportError(GenesisError):
    """An LLM backend could not be reached or returned an unusable envelope.

    Distinct from ``LLMOutputError`` (the model answered, but its content was
    unparseable): here NO model output exists. Raised loudly because a dead or
    misconfigured server must never degrade into "the model said nothing" —
    downstream would honestly treat that as abstention and thereby mask an outage.
    """

    def __init__(self, model: str, reason: str) -> None:
        super().__init__(f"LLM backend for {model!r} failed: {reason}")
