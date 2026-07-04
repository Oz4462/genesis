"""GENESIS core state — the typed data that flows through the pipeline.

This is the single source of truth for the shapes that agents read and write.
The Claim is the most important type in the whole system: it is how the
anti-hallucination guarantee is made concrete. A Claim cannot meaningfully exist
without provenance.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# =============================================================================
# Generalist Subsystem Abstraction (B item from gap analysis)
# For clear interfaces across ANY idea domain (mech/elec/thermal/data/safety/software/bio/energy...).
# Not electronics-specific. Used by LUMEN, integrator, wissensbasis for better modularity.
# =============================================================================

@dataclass
class ModuleSpec:
    """A general, reusable description of a subsystem/module in a larger system.
    Ports/budgets are domain-agnostic (power, thermal, data, mechanical interface, safety level, software API).
    Enables Subsystem-Abstraktion, multi-board reasoning, and inverse design across all ideas.
    """
    name: str
    kind: str  # e.g. "power_distribution", "sensor_array", "control_unit", "structure", "energy_storage", "biological_reactor"
    interfaces: dict[str, Any] = field(default_factory=dict)  # e.g. {"mech": "mounting_points", "elec": "48V_rail", "data": "CAN", "thermal": "heatsink", "safety": "S3", "software": "firmware_v1"}
    power_budget_w: float = 0.0
    thermal_budget_w: float = 0.0
    mass_kg: float = 0.0
    volume_cm3: float = 0.0
    safety_level: str = "S0"
    open_issues: list[str] = field(default_factory=list)
    quelle: str = "generalist subsystem abstraction"


# =============================================================================
# Nano + Space-Colony Extensions (2036 10y leap, Genesis 2026 core)
# Bio full, local, 4 Linsen provenance. For planetary engineering, closed-loop
# habitats, molecular machines / self-assembling structures.
# =============================================================================

@dataclass
class ColonyModule:
    """Colony / habitat subsystem for space-colony and planetary engineering sims.
    Extends generalist ModuleSpec for ECLSS bio-loops, radiation shielding,
    micro-g countermeasures, self-assembling nano-hab components.
    All fields carry explicit quelle for L1. Sim-ready (local numpy dispatch).
    """
    name: str
    kind: str  # e.g. "eclss_algae_loop", "radiation_shield_regolith_pe", "microg_centrifuge", "self_assemble_nano_hab", "life_support_compartment", "planetary_isru_nano"
    interfaces: dict[str, Any] = field(default_factory=dict)
    power_budget_w: float = 0.0
    thermal_budget_w: float = 0.0
    mass_kg: float = 0.0
    volume_cm3: float = 0.0
    safety_level: str = "S0"
    # Space-colony specifics (grounded in real concepts: MELiSSA/ACLS, regolith+PE/water shielding, micro-g countermeasures)
    bio_yield_g_per_day: float = 0.0          # algae/biomass output for closed O2/food loop
    o2_gen_rate_g_per_h: float = 0.0          # net O2 from bio-loop under given light/CO2
    co2_scrub_rate_g_per_h: float = 0.0
    shield_thickness_mm: float = 0.0
    shield_material: str = ""                 # "regolith", "polyethylene", "water_wall", "regolith_pe_composite"
    radiation_dose_reduction: float = 1.0     # 1.0 = unshielded; factor <1 after shielding (primary GCR/SPE + secondaries)
    microg_mitigation: str = ""               # "centrifuge_1g", "resistance_exercise", "pharma_loading", "none"
    self_assemble_rate: float = 0.0           # proxy for nano self-assembly kinetics (steps/h or %/day)
    open_issues: list[str] = field(default_factory=list)
    quelle: str = "colony module 2036 leap (MELiSSA ESA + regolith/PE shielding NTRS + micro-g countermeasures + nano self-assemble)"
    source: str = "Genesis Nano-Designer & Space-Colony Engineer integration"


@dataclass(frozen=True)
class NanoRecipe:
    """Nano-scale design recipe for molecular machines and self-assembling structures.
    Used in wissensbasis seeding, colony habitat assembly, planetary ISRU nano-factories.
    Carries molecular_fidelity from bio_molecular MD/ODE dispatch (local numpy).
    No facts without quelle (L1); assembly conditions are DECISION or GROUNDED.
    """
    id: str
    name: str
    kind: str  # "rotary_molecular_motor", "dna_origami_scaffold", "self_healing_nano_binder", "flagellar_pump_actuator", "quorum_nano_swarm", "isru_nano_factory"
    specs: dict[str, Any]  # e.g. stall_torque_pN_nm, step_size, assembly_temp_C, yield_pct, binding_energy_kT
    assembly_conditions: dict[str, Any] = field(default_factory=dict)  # pH, temp, ions, light, quorum signal
    molecular_fidelity: Optional[dict[str, Any]] = None  # from bio_molecular.run_* (trajectory, period, force, 4_lenses)
    footprint_nm: Optional[tuple[float, float, float]] = None
    source: str = "representative_synthetic_bio_or_nano_2036_local"
    quelle: str = "nano recipes 2036 leap (F1-ATPase/flagellar motors + DNA origami self-assembly literature + bio_molecular.numpy + 4_LINSEN)"


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

    INVARIANT (enforced in __post_init__, LedgerStore, and DB): `sources` is
    non-empty. A sourceless fact cannot even be constructed (fail-fast below),
    let alone persisted — there is no such thing as a sourceless fact in GENESIS.

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


# --- Phase φ: the spark and grounded divergence (HORIZON.md) ------------------

@dataclass(frozen=True)
class Spark:
    """A human's raw, undeveloped input — a problem hunch or idea seed, not a spec.

    The entry point of Movement A ("the workshop for the spark"). A Spark asserts no
    fact; it is the raw text Genesis will develop into grounded Possibilities. There
    is no invariant: a spark is allowed to be vague — that is its nature.
    """

    id: str
    raw: str
    created_at: datetime = field(default_factory=_now)


@dataclass
class Possibility:
    """One direction a Spark could take — a REAL possibility, never an invented one.

    INVARIANT (enforced here AND re-checked by GATE φ): `grounding` is non-empty.
    Divergence has no completeness gate (you cannot prove a possibility space is
    whole), so the only honest guarantee is that every possibility is anchored to at
    least one VERIFIED claim / real precedent in the ledger — the same DNA as α's
    "no fact without a source". A possibility without grounding is structurally
    impossible (UngroundedPossibilityError). See HORIZON.md §3/§5.

    A Possibility asserts NO new fact: `statement` is a direction (e.g. "store heat in
    a phase-change material"), the factual substance lives in the grounding claims.

    `statement`   short human-readable direction (NOT a fact).
    `mechanism`   short label of the real mechanism/precedent it leans on.
    `grounding`   claim_ids of VERIFIED claims anchoring the mechanism. MUST be non-empty.
    `produced_by` agent name (provenance of the structuring, not of any fact).
    `model`       model family that produced the structuring (for auditing).
    """

    id: str
    statement: str
    mechanism: str
    grounding: list[str]
    produced_by: str = ""
    model: str = ""
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        # Fail fast: a possibility with no grounding must never be constructed.
        if not self.grounding:
            from .errors import UngroundedPossibilityError
            raise UngroundedPossibilityError(self.id, self.statement)


@dataclass
class Divergence:
    """The output of Phase φ: a Spark opened into grounded Possibilities.

    INVARIANT (re-checked by GATE φ): `grounded_sample` MUST be True — Genesis always
    says out loud "this is a grounded sample, not the whole space" (HORIZON.md §3).
    Marking it False is the structural equivalent of claiming completeness, which is
    unprovable; the gate rejects it. Zero possibilities is valid abstention (honest
    "nothing groundable").

    `spark`           the originating Spark.
    `possibilities`   the grounded directions (each anchored; may be empty = abstain).
    `grounded_sample` honest disclaimer flag; must be True to pass GATE φ.
    """

    spark: Spark
    possibilities: list[Possibility] = field(default_factory=list)
    grounded_sample: bool = True


# --- Phase χ: the frontier map (HORIZON.md §2C) ------------------------------

@dataclass(frozen=True)
class KnownRegion:
    """An island of certainty on the frontier map: a cluster of VERIFIED facts.

    INVARIANT (enforced here AND re-checked by GATE χ): `fact_ids` is non-empty and
    each references a VERIFIED claim. A region of 'known' territory without an anchor is
    fabricated certainty — structurally impossible (UnknownRegionError).

    `label` is a human-readable domain label (NOT a fact); the factual substance lives in
    the referenced VERIFIED claims.
    """

    id: str
    label: str
    fact_ids: list[str]

    def __post_init__(self) -> None:
        if not self.fact_ids:
            from .errors import UnknownRegionError
            raise UnknownRegionError(self.id)


@dataclass(frozen=True)
class FrontierEdge:
    """An honest edge of the unknown: an open question grounded in a REAL detected gap.

    Never an invented question. `grounded_in` MUST reference a real gap of the run — a
    surfaced gap from a gated phase (α/β/γ report.gaps) or a REFUTED/UNSUPPORTED claim.
    GATE χ rejects any edge whose `grounded_in` does not match a real gap (no invented
    neighbourhood of the unknown, the χ analogue of α's no-fact-without-source).

    `question` is the open question (NOT a fact). `category` is a human label.
    """

    id: str
    question: str
    grounded_in: str
    category: str = "open"

    def __post_init__(self) -> None:
        # An edge with no question or no real grounding reference is an invented edge —
        # structurally impossible (empty/whitespace would otherwise slip past GATE χ when
        # an upstream report carried an empty gap string).
        if not self.question.strip() or not self.grounded_in.strip():
            raise ValueError(
                f"FrontierEdge {self.id!r} needs a non-empty question and grounded_in "
                "(no invented edge; HORIZON.md §2C)."
            )


@dataclass
class FrontierMap:
    """Phase χ output: a deterministic, honest map of known territory + the open frontier.

    Pure synthesis of the proven phases (α/β/γ) — no new research, no LLM facts. Empty
    known_regions with non-empty frontier_edges is valid abstention ("we mapped the open
    questions, found no verified foundation"). GATE χ re-checks every region and edge.
    """

    run_id: str
    topic: str
    known_regions: list[KnownRegion] = field(default_factory=list)
    frontier_edges: list[FrontierEdge] = field(default_factory=list)
    produced_by: str = ""
    created_at: datetime = field(default_factory=_now)


# --- Phase δ⁺: the reality proof (HORIZON.md §2B) ----------------------------

class EmpiricalStatus(enum.Enum):
    """Empirical lifecycle of a predicted quantity.

    COMPUTED      predicted/derived; no real measurement yet (not corroborated).
    CORROBORATED  a real measurement fell within the experiment's tolerance band.
    REFUTED       a real measurement fell OUTSIDE tolerance — re-specify honestly.
    INCONCLUSIVE  the measurement cannot be compared (unit mismatch / unparseable).
    """

    COMPUTED = "computed"
    CORROBORATED = "corroborated"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class FalsificationExperiment:
    """A self-designed experiment that tries to FALSIFY a computed prediction.

    INVARIANT (constructor): grounds in >=1 claim/quantity (the prediction it tests),
    a non-empty `predicted_unit`, and a non-negative `tolerance`. An experiment that
    tests nothing is structurally impossible (UngroundedExperimentError, HORIZON §2B).

    `tolerance` is the acceptance band as an ABSOLUTE value in `predicted_unit`.
    `method` is the human-readable measurement procedure (NOT a fact).
    """

    id: str
    measurand: str
    predicted_value: float
    predicted_unit: str
    tolerance: float
    method: str
    grounding: list[str]

    def __post_init__(self) -> None:
        if not self.grounding:
            from .errors import UngroundedExperimentError
            raise UngroundedExperimentError(self.id, self.measurand)
        if not self.predicted_unit.strip():
            raise ValueError(f"experiment {self.id!r}: predicted_unit must be non-empty")
        if not math.isfinite(self.predicted_value) or not math.isfinite(self.tolerance):
            raise ValueError(f"experiment {self.id!r}: predicted_value and tolerance must be finite")
        if self.tolerance < 0:
            raise ValueError(f"experiment {self.id!r}: tolerance must be >= 0")


@dataclass(frozen=True)
class Measurement:
    """A real, provenance-bearing reading taken for a FalsificationExperiment.

    INVARIANT (constructor): `sources` is non-empty — a measurement is a factual claim
    about the world and may not be a fabricated number (UnsourcedMeasurementError).
    """

    id: str
    experiment_id: str
    value: float
    unit: str
    sources: list[SourceRef]

    def __post_init__(self) -> None:
        # A measurement needs a REAL (actually-retrieved) reading and a finite value —
        # an unretrieved source or a NaN/inf value is a fabricated number, structurally
        # impossible (no corroboration from invented evidence; HORIZON §2B, CLAUDE.md §1).
        if not self.sources or not any(s.retrieved for s in self.sources):
            from .errors import UnsourcedMeasurementError
            raise UnsourcedMeasurementError(self.id)
        if not math.isfinite(self.value):
            raise ValueError(f"measurement {self.id!r}: value must be finite")
        if not self.unit.strip():
            # Mirror FalsificationExperiment.predicted_unit: a unitless measurement cannot
            # be compared to its experiment's prediction (would silently read INCONCLUSIVE).
            raise ValueError(f"measurement {self.id!r}: unit must be non-empty")


@dataclass(frozen=True)
class EmpiricalVerdict:
    """Deterministic outcome of comparing a Measurement to its experiment's prediction."""

    status: EmpiricalStatus
    residual: float          # |measured - predicted| in predicted_unit (nan if inconclusive)
    within_tolerance: bool
    detail: str = ""


# --- Phase delta+: coverage proof (HORIZON.md §2B) ---------------------------

class CoverageStatus(enum.Enum):
    """How a declared failure mode is handled by a coverage certificate.

    CHECKED     Genesis ran a deterministic check or feasibility proof for the mode.
    UNTESTABLE  Genesis could not run the check and states the residual gap explicitly.
    """

    CHECKED = "checked"
    UNTESTABLE = "untestable"


@dataclass(frozen=True)
class FailureMode:
    """One failure mode the delta+ coverage proof must account for.

    INVARIANT (enforced here AND re-checked by the coverage gate): `grounding` is
    non-empty. A failure mode can be declared only when it is anchored in something real:
    a physics selector trigger, an SMT constraint set, a measured gap, or a reviewed
    external candidate. Otherwise the certificate could invent its own threat surface.
    """

    id: str
    label: str
    source: str
    grounding: list[str]

    def __post_init__(self) -> None:
        if not self.grounding:
            from .errors import UngroundedFailureModeError
            raise UngroundedFailureModeError(self.id, self.label)
        if not self.id.strip() or not self.label.strip() or not self.source.strip():
            raise ValueError("FailureMode needs non-empty id, label, and source")


@dataclass(frozen=True)
class FailureModeCoverage:
    """How a certificate covers one declared FailureMode.

    `evidence` is required for CHECKED modes (e.g. physics-check id, SMT feasibility
    result). `residual_risk` is required for UNTESTABLE modes: the certificate must say
    what remains unproved instead of hiding it.
    """

    mode_id: str
    status: CoverageStatus
    evidence: list[str] = field(default_factory=list)
    residual_risk: str = ""

    def __post_init__(self) -> None:
        if not self.mode_id.strip():
            raise ValueError("FailureModeCoverage needs a non-empty mode_id")
        if self.status is CoverageStatus.CHECKED and not self.evidence:
            from .errors import UncoveredFailureModeError
            raise UncoveredFailureModeError(self.mode_id)
        if self.status is CoverageStatus.UNTESTABLE and not self.residual_risk.strip():
            from .errors import UncoveredFailureModeError
            raise UncoveredFailureModeError(self.mode_id)


@dataclass
class CoverageCertificate:
    """Delta+ coverage proof: what was checked, and what honestly remains untestable.

    GATE delta+ coverage re-derives the required failure modes from the spec's declared
    measurands and constraints, then checks this certificate against them. `complete`
    means "complete for the deterministic evidence Genesis can derive today" — it is
    rejected if any indicated mode is missing.
    """

    spec_run_id: str
    failure_modes: list[FailureMode] = field(default_factory=list)
    coverage: list[FailureModeCoverage] = field(default_factory=list)
    complete: bool = True
    produced_by: str = ""
    created_at: datetime = field(default_factory=_now)


# --- Phase γ: specification building blocks ----------------------------------

class ValueOrigin(enum.Enum):
    """Declared provenance of a numeric value in a Specification.

    GROUNDED   literally backed by VERIFIED ledger claims (value appears in the
               claim text — the γ analogue of scholar's verbatim-quote guard).
    DERIVED    deterministically computed by CODE from other quantities via a
               recorded formula; the gate recomputes it. The LLM never does math.
    DECISION   an explicit, human-ratifiable design choice with a rationale —
               never presented as fact.
    """

    GROUNDED = "grounded"
    DERIVED = "derived"
    DECISION = "decision"


@dataclass(frozen=True)
class Derivation:
    """A recomputable arithmetic recipe: `formula` over quantity-id `inputs`.

    Evaluated only by the safe evaluator (verification/derivation.py). Anything
    outside the allowed grammar fails loudly (FormulaError) — a value that
    cannot be deterministically recomputed must never exist as DERIVED.
    """

    formula: str
    inputs: tuple[str, ...] = ()


@dataclass
class Quantity:
    """A named, unit-carrying numeric value with DECLARED provenance.

    INVARIANT (enforced here AND re-checked by GATE γ): the origin and the
    provenance fields must agree — grounding only with GROUNDED (non-empty),
    derivation only with DERIVED, rationale only with DECISION. A value whose
    provenance shape lies about its origin is the γ-equivalent of a sourceless
    fact (PHASE_GAMMA.md §3.1).

    `id`        identifier-safe (usable as a variable in derivation formulas).
    `value`     numeric only; non-numeric choices are `Decision`s, non-numeric
                facts stay Claims.
    `unit`      non-empty; "1" for dimensionless (GATE γ C-12).
    `measurand` optional DECLARED key naming the physical quantity this measures
                (e.g. "led_strip.voltage"). Two quantities sharing a measurand
                must agree (same dimension, same value after unit conversion) —
                GATE γ C-17 proves they cannot contradict. The link is declared,
                not inferred: GENESIS makes the cross-claim structure explicit
                rather than guessing it with language understanding.
    `uncertainty` optional standard uncertainty u(x) of the value, SAME unit. For
                a measured/declared input it is a Type A/B estimate (GUM); for a
                DERIVED value it is the combined standard uncertainty, which GATE γ
                C-18 independently recomputes from the inputs by the GUM law of
                propagation (uncertainty.py). None means "treated as exact".
    """

    id: str
    name: str
    value: float
    unit: str
    origin: ValueOrigin
    grounding: list[str] = field(default_factory=list)
    derivation: Derivation | None = None
    rationale: str = ""
    measurand: str | None = None
    uncertainty: float | None = None
    produced_by: str = ""
    model: str = ""
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        from .errors import (
            InvalidDerivationError,
            UndeclaredDecisionError,
            UngroundedValueError,
        )

        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise InvalidDerivationError(self.id, "value must be numeric (int|float)")
        if not math.isfinite(self.value):
            # Root guard for the non-finite theme both reviewers surfaced (geometry/consensus/
            # derivation/units): a quantity carrying inf/nan would silently poison AABB, volume,
            # mass, tolerance and dimensional checks downstream. No silent bad value (PHASE_GAMMA §0).
            raise InvalidDerivationError(self.id, "value must be finite (not inf/nan)")

        if self.measurand is not None and not self.measurand.strip():
            raise InvalidDerivationError(
                self.id, "measurand, if set, must be a non-empty key"
            )

        if self.uncertainty is not None and (
            isinstance(self.uncertainty, bool)
            or not isinstance(self.uncertainty, (int, float))
            or not math.isfinite(self.uncertainty)
            or self.uncertainty < 0.0
        ):
            # math.isfinite before the <0 test: inf/nan both pass `< 0.0` (both
            # comparisons are False), so without this an infinitely/NaN-uncertain
            # quantity would silently poison GUM uncertainty propagation (C-18). The
            # `or` short-circuits past isfinite only once it is a real int|float.
            raise InvalidDerivationError(
                self.id, "uncertainty, if set, must be a finite non-negative number"
            )

        if self.origin is ValueOrigin.GROUNDED:
            if not self.grounding:
                raise UngroundedValueError(self.id, self.name)
            if self.derivation is not None:
                raise InvalidDerivationError(
                    self.id, "GROUNDED quantity must not carry a derivation"
                )
            if self.rationale:
                raise InvalidDerivationError(
                    self.id,
                    "GROUNDED quantity must not carry a rationale — a sourced "
                    "fact is not a choice",
                )
        elif self.origin is ValueOrigin.DERIVED:
            if self.derivation is None:
                raise InvalidDerivationError(
                    self.id, "DERIVED quantity requires a derivation"
                )
            if self.grounding:
                raise InvalidDerivationError(
                    self.id,
                    "DERIVED quantity must not carry grounding — its provenance "
                    "is the formula over its inputs",
                )
            if self.rationale:
                raise InvalidDerivationError(
                    self.id, "DERIVED quantity must not carry a rationale"
                )
        else:  # ValueOrigin.DECISION
            if not self.rationale.strip():
                raise UndeclaredDecisionError(
                    self.id, "DECISION quantity requires a non-empty rationale"
                )
            if self.grounding:
                raise InvalidDerivationError(
                    self.id,
                    "DECISION quantity must not carry grounding — a choice is "
                    "not a sourced fact",
                )
            if self.derivation is not None:
                raise InvalidDerivationError(
                    self.id, "DECISION quantity must not carry a derivation"
                )


# CSG vocabulary (PHASE_GAMMA.md §3.3). Param values are quantity_ids, never raw
# numbers — every dimension in the 3D model traces back to a Quantity. The gate
# (not the constructor) validates shape, so adversarial gate tests can construct
# invalid geometry.
GEOMETRY_PRIMITIVES: dict[str, tuple[str, ...]] = {
    "box": ("size_x", "size_y", "size_z"),
    "cylinder": ("radius", "height"),
    "sphere": ("radius",),
}
GEOMETRY_OPERATIONS: frozenset[str] = frozenset({"union", "difference", "intersection"})
GEOMETRY_TRANSFORMS: dict[str, tuple[str, ...]] = {
    "translate": ("x", "y", "z"),
    # rotation about an arbitrary axis THROUGH THE ORIGIN, angle in DEGREES —
    # the convention all backends share (OpenSCAD rotate(a, v); cadquery
    # Shape.rotate; build123d Shape.rotate(Axis, deg); AABB layer Rodrigues).
    "rotate": ("axis_x", "axis_y", "axis_z", "angle_deg"),
}


@dataclass
class GeometryNode:
    """One node of a parametric CSG tree (PHASE_GAMMA.md §3.3).

    `params` maps the node's parameter names to quantity_ids. Primitives carry
    exactly their required params and no children; operations carry >= 2
    children (order significant for `difference`); transforms carry exactly one.
    GATE γ enforces all of this (C-8 resolution, C-9 shape/positivity).
    """

    kind: str
    params: dict[str, str] = field(default_factory=dict)
    children: list["GeometryNode"] = field(default_factory=list)


@dataclass
class Component:
    """A part of the design — fabricated (with geometry) or abstract/purchased.

    `material_density` (optional) is the quantity_id of a density quantity (a
    GROUNDED material fact or a DECISION), used by Phase δ to compute the part's
    mass = volume × density. It must reference an existing quantity of dimension
    mass/length³ (GATE γ resolves it; δ checks the dimension).
    """

    id: str
    name: str
    geometry: GeometryNode | None = None
    quantity_ids: list[str] = field(default_factory=list)
    material_density: str | None = None


class BomRole(enum.Enum):
    PART = "part"
    MATERIAL = "material"
    TOOL = "tool"


class BomDomain(enum.Enum):
    """Which bill of materials a line belongs to. The electronics BOM is kept
    separate from the mechanical BOM (PHASE_GAMMA_DEPTH.md §4)."""

    MECHANICAL = "mechanical"
    ELECTRONIC = "electronic"


@dataclass
class Sourcing:
    """Procurement provenance for a BOM item — where to actually buy it.

    INVARIANT (enforced here AND re-checked by GATE γ C-16): `grounding` is
    non-empty. A supplier, order number, or price is a factual claim about the
    world; it must be anchored in VERIFIED claims, and GATE γ additionally
    requires `supplier` and `part_number` to appear in a grounding claim's text
    (the string analogue of the value-in-claim guard C-4). The price is a
    GROUNDED quantity (`price_quantity_id`), so its number is verbatim-checked
    against a claim too. No invented shop, order number, or price
    (PHASE_GAMMA_DEPTH.md §1).

    `supplier`          e.g. "McMaster-Carr" — must appear in a grounding claim.
    `part_number`       order number or standard, e.g. "91290A115" / "ISO 4762".
    `price_quantity_id` a GROUNDED price quantity (currency unit), or None.
    `grounding`         claim_ids backing the sourcing. MUST be non-empty.
    """

    supplier: str
    part_number: str
    price_quantity_id: str | None = None
    grounding: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.grounding:
            from .errors import UnsourcedSourcingError
            raise UnsourcedSourcingError(f"{self.supplier}/{self.part_number}")


@dataclass
class BomItem:
    """One line of the bill of materials.

    A PART with `component_id` is fabricated in-house (the component defines
    its geometry); without one it is purchased/external. Optional `grounding`
    holds claim_ids backing factual properties of the item (availability,
    spec) — if present, GATE γ requires them sound like any other reference.
    `sourcing` (optional) says where to buy it — every field claim-backed.
    """

    id: str
    name: str
    role: BomRole
    count: int = 1
    component_id: str | None = None
    grounding: list[str] = field(default_factory=list)
    sourcing: "Sourcing | None" = None
    domain: BomDomain = BomDomain.MECHANICAL


@dataclass
class Step:
    """One numbered instruction of the build plan.

    The artifact namespace starts with all BomItem ids; each step may consume
    `inputs` (available artifacts), use `uses` (BOM items), and produce new
    `outputs`. `check` tells the human how to verify success — a step without a
    check is incomplete (GATE γ C-10/C-11; hallucination face #5).
    """

    id: str
    index: int
    action: str
    uses: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    check: str = ""
    quantity_refs: list[str] = field(default_factory=list)
    tool: str = ""                              # which tool the step needs (optional)
    torque_quantity_id: str | None = None       # a tightening torque quantity (N·m)


CONSTRAINT_KINDS: frozenset[str] = frozenset({"le", "lt", "ge", "gt", "eq"})


@dataclass
class Constraint:
    """A numerically checked compatibility condition between two expressions.

    `left` and `right` are arithmetic EXPRESSIONS over quantity_ids (a bare id
    is the trivial case, so old two-quantity constraints are unchanged), e.g.
    ``"q_hole_d" >= "q_screw_d"``, ``"q_t" >= "0.1 * q_w"``, or a plausibility
    bound ``"q_t" > "0"``. GATE γ resolves every referenced id (C-8), requires
    both sides to be dimensionally comparable (C-12/C-15; a pure numeric literal
    side is dimension-agnostic), and evaluates the comparison (C-13). `reason`
    states why it must hold — for the human, not a fact.
    """

    id: str
    kind: str
    left: str
    right: str
    reason: str = ""


@dataclass
class Decision:
    """An explicit, non-numeric design choice (material, process, ...).

    INVARIANT: a decision without a stated choice and rationale is a hidden
    decision — structurally impossible (UndeclaredDecisionError). Optional
    `informed_by` claim_ids must exist and be sound (GATE γ C-2/C-5), but a
    decision never becomes a fact: it appears on the decision sheet, ratifiable
    by the human.
    """

    id: str
    title: str
    choice: str
    rationale: str
    informed_by: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        from .errors import UndeclaredDecisionError

        if not self.choice.strip():
            raise UndeclaredDecisionError(self.id, "Decision requires a non-empty choice")
        if not self.rationale.strip():
            raise UndeclaredDecisionError(
                self.id, "Decision requires a non-empty rationale"
            )


class PinType(enum.Enum):
    """The electrical role of a component pin, for the deterministic ERC.

    POWER_OUT  a driver/source (PSU +, regulator output) — supplies a net.
    POWER_IN   a sink/load (LED +, MCU VCC) — must be driven by a POWER_OUT.
    GROUND     a ground/return pin.
    PASSIVE    a directionless lead (resistor, connector) — neither drives nor
               needs driving.
    """

    POWER_OUT = "power_out"
    POWER_IN = "power_in"
    GROUND = "ground"
    PASSIVE = "passive"


@dataclass
class Pin:
    """One electrical pin of a BOM part. `part` is a BomItem id, `name` the pin
    label (e.g. "V+"); `type` is its electrical role. A pin is referenced from a
    Net as ``"{part}.{name}"``."""

    part: str
    name: str
    type: PinType


@dataclass
class Net:
    """A node of the electrical netlist — a set of pins that are wired together.
    `pins` holds ``"{part}.{name}"`` references into the declared Pins. GATE ERC
    (verification/gates.py) checks connectivity and power-direction rules."""

    name: str
    pins: list[str] = field(default_factory=list)


@dataclass
class Netlist:
    """The electrical connectivity of a Specification — typed pins plus the nets
    that connect them. Optional; present only for designs with an electronics
    domain. The deterministic ERC (no SPICE) proves connectivity soundness:
    no floating net, no unconnected pin, no two drivers on one net, no undriven
    load, no dangling pin reference (PHASE_DELTA.md §13)."""

    pins: list[Pin] = field(default_factory=list)
    nets: list[Net] = field(default_factory=list)


@dataclass
class ExperimentDesign:
    """The reproducibility design of a wet-lab / field protocol (the bio ε arc).

    A protocol that measures a quantitative outcome but has no control group or too
    few replicates is the root of the reproducibility crisis. GATE PROTOCOL checks
    this deterministically (PHASE_DELTA.md §19): a measured outcome needs >= 2
    groups including a named control, and at least `MIN_REPLICATES` replicates.
    Parameter safety limits (e.g. concentration <= toxic threshold) and unit
    correctness reuse the existing constraint machinery (C-13 / C-15).

    `measured`    the outcome variable (e.g. "stem height"); "" if exploratory.
    `groups`      experimental group names (e.g. ["treatment", "control"]).
    `control`     which group is the control, or None.
    `replicates`  independent replicates per group.
    """

    measured: str = ""
    groups: list[str] = field(default_factory=list)
    control: str | None = None
    replicates: int = 1


@dataclass
class CodeArtifact:
    """A software deliverable whose correctness is proven by EXECUTION.

    The software-domain analogue of geometry/statics: instead of a formula the gate
    re-checks, the deliverable is `source` code plus a `check` that exercises it;
    GATE CODE runs them and passes only if the checks pass. This is the strongest
    deterministic validator GENESIS has — the machine executes, no model judgement.

    `language`  currently only "python" runs deterministically with a local runtime.
    `source`    the code under test.
    `check`     assertions exercising `source`; a non-zero exit (e.g. AssertionError)
                means the deliverable is broken.
    """

    id: str
    name: str
    language: str
    source: str
    check: str
    description: str = ""


@dataclass
class SiteRequirements:
    """Where to set the thing up and what the location must provide.

    `available_space` (optional) is a triple of quantity_ids giving the room's
    L×W×H; GATE δ checks that each fabricated component's bounding box fits inside
    it (axis-aligned, any orientation). `requirements` are declared site needs —
    ventilation, indoor/outdoor, mains connection, safety clearances — each a
    `Decision` (claim-informed or a justified choice), never an invented demand
    (PHASE_GAMMA_DEPTH.md §5).
    """

    available_space: tuple[str, str, str] | None = None
    requirements: list["Decision"] = field(default_factory=list)


@dataclass
class Specification:
    """Final output of Phase γ — the complete, actionable build specification.

    Assembled by `architect`/`conductor` ONLY from ledger claims, recomputed
    derivations and declared decisions (GATE γ enforces all five Zwänge). A
    specification that asserts content (components or steps) must be anchored
    in a grounded Approach of the run (`approach_id`, C-14) — the β chain. If
    nothing can be grounded, everything is empty and `gaps` explains why
    (abstention) — never a partial or drifted build plan.
    """

    run_id: str
    idea: str
    approach_id: str | None = None
    quantities: list[Quantity] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    bom: list[BomItem] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    site: "SiteRequirements | None" = None
    netlist: "Netlist | None" = None
    code_artifacts: list["CodeArtifact"] = field(default_factory=list)
    experiment: "ExperimentDesign | None" = None
    gaps: list[str] = field(default_factory=list)
    claim_ids_used: list[str] = field(default_factory=list)
    produced_by: str = ""
    #: Optional ASSEMBLY placements for rendering the finished product (not just the flat parts tray):
    #: each is ``(component_id, x_mm, y_mm, z_mm, rot_x_deg, rot_y_deg, rot_z_deg)`` in the body frame.
    #: A component may appear multiple times (e.g. two legs). When present, the bundle renders the
    #: assembled robot as a 3D image + an OpenSCAD assembly view. Empty = no assembled view.
    assembly: list[tuple[str, float, float, float, float, float, float]] = field(default_factory=list)
    model: str = ""


# --- Phase gamma+: inverse design (HORIZON.md §2B) ---------------------------

class ObjectiveDirection(enum.Enum):
    """How an inverse-design objective is optimized.

    Internally the Pareto gate converts every direction to a "lower is better" score:
    minimize -> value, maximize -> -value, target -> |value - target|.
    """

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    TARGET = "target"


@dataclass(frozen=True)
class DesignObjective:
    """One measurable goal for inverse design.

    The objective references a Quantity by id; the gate reads the value from every
    candidate Specification and converts it to `unit` before comparing candidates. The
    objective never invents a score: all numbers come from candidate quantities that γ
    already proves sound.
    """

    id: str
    quantity_id: str
    direction: ObjectiveDirection
    unit: str
    target: float | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.quantity_id.strip() or not self.unit.strip():
            raise ValueError("DesignObjective needs non-empty id, quantity_id, and unit")
        if self.direction is ObjectiveDirection.TARGET:
            if self.target is None or not math.isfinite(self.target):
                raise ValueError("target objective needs a finite target")
        elif self.target is not None:
            raise ValueError("target is only valid for TARGET objectives")


@dataclass(frozen=True)
class InverseDesignGoal:
    """The gamma+ input: a target expressed as measurable objectives."""

    id: str
    description: str
    objectives: list[DesignObjective]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.description.strip():
            raise ValueError("InverseDesignGoal needs non-empty id and description")
        if not self.objectives:
            raise ValueError("InverseDesignGoal needs at least one objective")
        ids = [objective.id for objective in self.objectives]
        if len(ids) != len(set(ids)):
            raise ValueError("InverseDesignGoal objective ids must be unique")


@dataclass
class DesignCandidate:
    """One candidate Specification evaluated for an inverse-design goal."""

    id: str
    specification: Specification
    objective_values: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("DesignCandidate needs a non-empty id")


@dataclass
class ParetoFront:
    """Gamma+ output: the nondominated validated candidates for a goal.

    `evaluated_candidates` is the proof boundary: every valid evaluated candidate must
    either be on the front or be dominated/equivalent to a front candidate. Empty front is
    valid only as honest abstention with `gaps`.
    """

    goal: InverseDesignGoal
    candidates: list[DesignCandidate] = field(default_factory=list)
    evaluated_candidates: list[DesignCandidate] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    produced_by: str = ""
    created_at: datetime = field(default_factory=_now)


# --- Phase epsilon: verified seams across domains (HORIZON.md §2B) -----------

class SeamDomain(enum.Enum):
    """Engineering domains that may be explicitly coupled by an epsilon seam.
    Extended for space multi-physics (radiation for habitats, TPS, electronics derating in vacuum).
    """

    MECHANICAL = "mechanical"
    THERMAL = "thermal"
    ELECTRICAL = "electrical"
    FIRMWARE = "firmware"
    COST = "cost"
    RADIATION = "radiation"  # vacuum/radiation dominant for multi-planetary (Mars, deep space)
    ISRU = "isru"  # In-Situ Resource Utilization: regolith processing, O2/CH4 propellant production on Mars (Elon/SpaceX vision)
    LIFE_SUPPORT = "life_support"  # ECLSS: O2/CO2/H2O loops, crew consumables, closed-loop for habitats (multi-planetary)


class SeamRelation(enum.Enum):
    """A deterministic relation between two domain expressions."""

    EQ = "eq"
    LE = "le"
    GE = "ge"
    COST_ROLLUP = "cost_rollup"


@dataclass(frozen=True)
class DomainSeam:
    """One explicit cross-domain coupling.

    For EQ/LE/GE, `left_expr` and `right_expr` are formulas over Quantity ids. The
    epsilon gate evaluates them in SI-scaled units and proves dimensional compatibility
    plus the declared relation. For COST_ROLLUP, `left_expr` is the declared total-cost
    Quantity id and `right_expr` is the currency subtotal to compare against `bom_cost`.
    """

    id: str
    left_domain: SeamDomain
    right_domain: SeamDomain
    relation: SeamRelation
    left_expr: str
    right_expr: str
    rationale: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.left_expr.strip() or not self.right_expr.strip():
            raise ValueError("DomainSeam needs non-empty id, left_expr, and right_expr")
        if self.left_domain is self.right_domain:
            raise ValueError("DomainSeam must connect two distinct domains")
        if not self.rationale.strip():
            raise ValueError("DomainSeam needs a rationale; hidden seams are not valid")


@dataclass
class SeamCertificate:
    """Phase epsilon output: the declared, verified cross-domain seams for a spec."""

    spec_run_id: str
    seams: list[DomainSeam] = field(default_factory=list)
    complete: bool = True
    produced_by: str = ""
    created_at: datetime = field(default_factory=_now)


# --- Phase zeta: shared memory / connective tissue (HORIZON.md §2C) ----------

class MemoryHealthStatus(enum.Enum):
    """Whether the shared-memory layer is cleared for reuse in this run."""

    OK = "ok"
    NOT_ENOUGH_BASELINE = "not_enough_baseline"
    DRIFT_ALERT = "drift_alert"


@dataclass(frozen=True)
class MemoryDeposit:
    """One fact deposited from a run into the shared verified-facts memory."""

    claim_id: str
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ValueError("MemoryDeposit needs a non-empty claim_id")
        if not self.sources:
            raise ValueError("MemoryDeposit needs preserved source ids")


@dataclass(frozen=True)
class MemoryRecallLink:
    """One prior fact reused by a run under a conformal threshold."""

    query: str
    claim_id: str
    score: float
    tau: float | None
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.query.strip() or not self.claim_id.strip():
            raise ValueError("MemoryRecallLink needs non-empty query and claim_id")
        if not math.isfinite(self.score):
            raise ValueError("MemoryRecallLink score must be finite")
        if self.tau is not None and not math.isfinite(self.tau):
            raise ValueError("MemoryRecallLink tau must be finite when present")
        if not self.sources:
            raise ValueError("MemoryRecallLink needs preserved source ids")


@dataclass
class MemoryFabricCertificate:
    """Phase ζ output: deposits + conformal recall links + memory health.

    The certificate is allowed to be empty. That is honest abstention. Accepted recalls,
    however, must carry a calibrated threshold and pass it; deposits must refer only to
    VERIFIED claims with source provenance. Drift alerts block reuse.
    """

    run_id: str
    deposits: list[MemoryDeposit] = field(default_factory=list)
    recalls: list[MemoryRecallLink] = field(default_factory=list)
    calibration_ready: bool = False
    health: MemoryHealthStatus = MemoryHealthStatus.NOT_ENOUGH_BASELINE
    produced_by: str = ""
    created_at: datetime = field(default_factory=_now)


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
      architect  -> specification (Phase γ; references claim_ids/approach only)
      conductor  -> sub_questions, report, round counters
    """

    question: Question
    sub_questions: list[SubQuestion] = field(default_factory=list)
    candidates: list[SourceCandidate] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    report: Report | None = None
    approaches: list[Approach] = field(default_factory=list)
    solution_report: "SolutionReport | None" = None
    specification: "Specification | None" = None
    spark: "Spark | None" = None          # Phase φ input (the workshop for the spark)
    divergence: "Divergence | None" = None  # Phase φ output; forge owns this field
    frontier_map: "FrontierMap | None" = None  # Phase χ output; cartographer owns this
    pareto_front: "ParetoFront | None" = None  # Phase γ+ output; inverse design owns this
    seam_certificate: "SeamCertificate | None" = None  # Phase ε output; seams own this
    memory_fabric: "MemoryFabricCertificate | None" = None  # Phase ζ output
    refine_round: int = 0
    log: list[str] = field(default_factory=list)
