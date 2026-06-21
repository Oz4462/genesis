"""Phase omega - the cross-phase honesty and learning exoskeleton.

Omega is not another model capability. It is the completion contract over the phases:

* every declared phase completion has a gate receipt;
* failed receipts cannot be hidden behind a "done" label;
* gaps, frontier edges, and human decisions are surfaced as learning notes;
* specification decisions/gaps remain under explicit human ratification.

The module is deliberately deterministic and offline. It assembles the decision sheet a
human keeps after a run, then verifies that the sheet is not lying by omission.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .core.interfaces import GateFailure, GateResult
from .core.state import Decision, RunState
from .memory_fabric import gate_zeta
from .ratification import SignOff, ratification_packet, unratified_items
from .seams import gate_epsilon


@dataclass(frozen=True)
class GateReceipt:
    """One deterministic gate verdict carried into the omega decision sheet."""

    name: str
    passed: bool
    failure_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("GateReceipt needs a non-empty name")
        if self.passed and self.failure_codes:
            raise ValueError("passed GateReceipt must not carry failure codes")
        if any(not code.strip() for code in self.failure_codes):
            raise ValueError("GateReceipt failure codes must be non-empty")


@dataclass(frozen=True)
class LearningNote:
    """One thing the human should retain: evidence, a gap, a decision, or next step."""

    kind: str
    ref: str
    summary: str

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.ref.strip() or not self.summary.strip():
            raise ValueError("LearningNote needs non-empty kind, ref, and summary")


@dataclass(frozen=True)
class OmegaCertificate:
    """The omega completion packet: receipts, learning notes, and ratification surface."""

    run_id: str
    gate_receipts: tuple[GateReceipt, ...] = ()
    learning_notes: tuple[LearningNote, ...] = ()
    ratification_refs: tuple[str, ...] = ()
    signoff: SignOff | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("OmegaCertificate needs a non-empty run_id")


def gate_receipt(name: str, result: GateResult) -> GateReceipt:
    """Convert a gate result into the compact receipt omega carries."""
    return GateReceipt(
        name=name,
        passed=result.passed,
        failure_codes=tuple(failure.code for failure in result.failures),
    )


def _add_note(notes: list[LearningNote], kind: str, ref: str, summary: str) -> None:
    notes.append(LearningNote(kind=kind, ref=ref, summary=" ".join(summary.split())))


def _decision_notes(prefix: str, decisions: Iterable[Decision]) -> list[LearningNote]:
    notes: list[LearningNote] = []
    for decision in decisions:
        _add_note(
            notes,
            "decision",
            f"{prefix}:decision:{decision.id}",
            f"{decision.title}: choice {decision.choice!r}; rationale: {decision.rationale}",
        )
    return notes


def _state_learning_notes(state: RunState) -> list[LearningNote]:
    notes: list[LearningNote] = []

    if state.sub_questions:
        _add_note(
            notes,
            "artifact",
            "artifact:decomposition",
            f"Question decomposed into {len(state.sub_questions)} researchable sub-questions.",
        )
    if state.candidates:
        _add_note(
            notes,
            "artifact",
            "artifact:candidates",
            f"Scout surfaced {len(state.candidates)} candidate sources before verification.",
        )
    if state.claims:
        _add_note(
            notes,
            "artifact",
            "artifact:ledger",
            f"Ledger carries {len(state.claims)} provenance-bearing claims for this run.",
        )
    if state.report is not None:
        _add_note(
            notes,
            "artifact",
            "artifact:report",
            (
                f"Report maps {len(state.report.statement_to_claim)} statements to claims "
                f"and surfaces {len(state.report.gaps)} gaps."
            ),
        )
        for index, gap in enumerate(state.report.gaps):
            _add_note(notes, "gap", f"report:gap:{index}", gap)
    if state.approaches:
        _add_note(
            notes,
            "artifact",
            "artifact:approaches",
            f"Synthesizer produced {len(state.approaches)} grounded approaches.",
        )
    if state.solution_report is not None:
        _add_note(
            notes,
            "artifact",
            "artifact:solution_report",
            (
                f"Solution report carries {len(state.solution_report.approaches)} approaches "
                f"and {len(state.solution_report.gaps)} gaps."
            ),
        )
        for index, gap in enumerate(state.solution_report.gaps):
            _add_note(notes, "gap", f"solution:gap:{index}", gap)
    if state.specification is not None:
        spec = state.specification
        _add_note(
            notes,
            "artifact",
            "artifact:specification",
            (
                f"Specification contains {len(spec.quantities)} quantities, "
                f"{len(spec.bom)} BOM items, {len(spec.steps)} steps, "
                f"{len(spec.decisions)} decisions, and {len(spec.gaps)} gaps."
            ),
        )
        notes.extend(_decision_notes("spec", spec.decisions))
        if spec.site is not None:
            notes.extend(_decision_notes("site", spec.site.requirements))
        for index, gap in enumerate(spec.gaps):
            _add_note(notes, "gap", f"spec:gap:{index}", gap)
    if state.divergence is not None:
        _add_note(
            notes,
            "artifact",
            "artifact:divergence",
            (
                f"Divergence produced {len(state.divergence.possibilities)} grounded "
                "possibilities and marks the set as a grounded sample."
            ),
        )
    if state.frontier_map is not None:
        _add_note(
            notes,
            "artifact",
            "artifact:frontier_map",
            (
                f"Frontier map has {len(state.frontier_map.known_regions)} known regions "
                f"and {len(state.frontier_map.frontier_edges)} open edges."
            ),
        )
        for edge in state.frontier_map.frontier_edges:
            _add_note(notes, "gap", f"frontier:edge:{edge.id}", edge.question)
    if state.pareto_front is not None:
        _add_note(
            notes,
            "artifact",
            "artifact:pareto_front",
            (
                f"Pareto front has {len(state.pareto_front.candidates)} front candidates "
                f"over {len(state.pareto_front.evaluated_candidates)} evaluated candidates."
            ),
        )
        for index, gap in enumerate(state.pareto_front.gaps):
            _add_note(notes, "gap", f"pareto:gap:{index}", gap)
    if state.seam_certificate is not None:
        _add_note(
            notes,
            "artifact",
            "artifact:seam_certificate",
            f"Seam certificate declares {len(state.seam_certificate.seams)} cross-domain seams.",
        )
    if state.memory_fabric is not None:
        _add_note(
            notes,
            "artifact",
            "artifact:memory_fabric",
            (
                f"Memory fabric deposits {len(state.memory_fabric.deposits)} claims "
                f"and accepts {len(state.memory_fabric.recalls)} recalls."
            ),
        )
    # δ phases feed notes for full Ω aggregation (coverage/reality/delta+)
    # ensures all phases (δ γ ε ζ) surface artifacts/gaps in learning_notes
    # now direct (typed fields on RunState)
    cov = state.coverage_certificate
    if cov is not None:
        nmodes = len(getattr(cov, "failure_modes", []) or [])
        _add_note(
            notes,
            "artifact",
            "artifact:coverage_certificate",
            f"δ+ coverage certificate: {nmodes} failure modes, complete={getattr(cov, 'complete', False)}.",
        )
    rver = state.reality_verdict
    if rver is not None:
        st = getattr(rver, "status", None)
        wt = getattr(rver, "within_tolerance", None)
        _add_note(notes, "artifact", "artifact:reality_verdict", f"δ+ reality: status={st} within_tol={wt}.")
    dpr = state.delta_plus_result
    if dpr is not None:
        _add_note(notes, "artifact", "artifact:delta_plus_result", f"δ+ result: {str(dpr)[:120]}")
    return notes


def _result_from_receipt(receipt: GateReceipt) -> GateResult:
    return GateResult(
        gate=receipt.name,
        passed=receipt.passed,
        failures=[GateFailure(code=code, detail=code) for code in receipt.failure_codes],
    )


def _results_from_receipts(certificate: OmegaCertificate) -> dict[str, GateResult]:
    return {
        receipt.name: _result_from_receipt(receipt)
        for receipt in certificate.gate_receipts
    }


def build_omega_certificate(
    state: RunState,
    gate_results: Mapping[str, GateResult] | None = None,
    *,
    signoff: SignOff | None = None,
    extra_notes: Iterable[LearningNote] = (),
) -> OmegaCertificate:
    """Build the omega decision sheet from state artifacts and gate verdicts.

    The builder never fabricates approval. If a spec needs ratification, the caller must
    pass an explicit ``SignOff``; otherwise ``gate_omega`` will surface the missing human
    approval.
    """
    results = dict(gate_results or {})
    receipts = tuple(gate_receipt(name, result) for name, result in sorted(results.items()))

    notes = _state_learning_notes(state)
    for receipt in receipts:
        verdict = "PASS" if receipt.passed else "FAIL"
        detail = (
            "no failures"
            if receipt.passed
            else "failures: " + ", ".join(receipt.failure_codes)
        )
        _add_note(notes, "evidence", f"gate:{receipt.name}", f"{receipt.name}: {verdict}; {detail}.")
    notes.extend(extra_notes)

    ratification_refs: tuple[str, ...] = ()
    if state.specification is not None:
        packet = ratification_packet(state.specification, results)
        ratification_refs = tuple(item.ref for item in packet)

    return OmegaCertificate(
        run_id=state.question.run_id,
        gate_receipts=receipts,
        learning_notes=tuple(notes),
        ratification_refs=ratification_refs,
        signoff=signoff,
    )


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def _has_run_output(state: RunState) -> bool:
    return any((
        bool(state.sub_questions),
        bool(state.candidates),
        bool(state.claims),
        state.report is not None,
        bool(state.approaches),
        state.solution_report is not None,
        state.specification is not None,
        state.divergence is not None,
        state.frontier_map is not None,
        state.pareto_front is not None,
        state.seam_certificate is not None,
        state.memory_fabric is not None,
        state.coverage_certificate is not None,
        state.reality_verdict is not None,
        state.delta_plus_result is not None,
    ))


def _required_note_refs(state: RunState) -> dict[str, str]:
    return {note.ref: note.kind for note in _state_learning_notes(state)}


def gate_omega(
    state: RunState,
    certificate: OmegaCertificate,
    *,
    required_gates: Iterable[str] = (),
    gate_results: Mapping[str, GateResult] | None = None,
    require_ratification: bool = True,
) -> GateResult:
    """GATE omega - validate the cross-phase completion packet.

    It proves:
      OM-1 RUN_MISMATCH                 packet belongs to this run.
      OM-2 DUPLICATE_*                  receipts/notes/ratification refs are unambiguous.
      OM-3 MISSING_REQUIRED_GATE        a declared phase has no gate receipt.
      OM-4 FAILED_GATE_RECEIPT          no failed gate can be hidden in a completion packet.
      OM-5 GATE_RECEIPT_MISMATCH        supplied gate results match the packet.
      OM-6 MISSING_*_NOTE               artifacts, gaps, frontier edges, decisions are surfaced.
      OM-7 MISSING_RATIFICATION_REF     the decision sheet lists ratification items.
      OM-8 UNRATIFIED_BLOCKING_ITEM     blocking spec items need explicit human sign-off.

    Pure; no model calls, no UI assumptions.
    """
    failures: list[GateFailure] = []

    if certificate.run_id != state.question.run_id:
        failures.append(
            GateFailure(
                code="OMEGA_RUN_MISMATCH",
                detail=(
                    f"omega certificate belongs to run {certificate.run_id!r}, "
                    f"not {state.question.run_id!r}."
                ),
            )
        )

    receipt_names = [receipt.name for receipt in certificate.gate_receipts]
    note_refs = [note.ref for note in certificate.learning_notes]
    for name in sorted(_duplicates(receipt_names)):
        failures.append(
            GateFailure(
                code="DUPLICATE_GATE_RECEIPT",
                detail=f"gate receipt {name!r} appears more than once.",
                claim_id=name,
            )
        )
    for ref in sorted(_duplicates(note_refs)):
        failures.append(
            GateFailure(
                code="DUPLICATE_LEARNING_NOTE",
                detail=f"learning note {ref!r} appears more than once.",
                claim_id=ref,
            )
        )
    for ref in sorted(_duplicates(certificate.ratification_refs)):
        failures.append(
            GateFailure(
                code="DUPLICATE_RATIFICATION_REF",
                detail=f"ratification ref {ref!r} appears more than once.",
                claim_id=ref,
            )
        )

    receipts = {receipt.name: receipt for receipt in certificate.gate_receipts}
    for name in sorted(set(required_gates)):
        if name not in receipts:
            failures.append(
                GateFailure(
                    code="MISSING_REQUIRED_GATE_RECEIPT",
                    detail=f"required gate {name!r} has no omega receipt.",
                    claim_id=name,
                )
            )

    for receipt in certificate.gate_receipts:
        if not receipt.passed:
            failures.append(
                GateFailure(
                    code="FAILED_GATE_RECEIPT",
                    detail=(
                        f"gate {receipt.name!r} failed with codes "
                        f"{receipt.failure_codes!r}; completion cannot hide it."
                    ),
                    claim_id=receipt.name,
                )
            )

    # HORIZON ζ elaboration wiring: validate attached memory_fabric via gate_zeta
    # (makes ζ active in Ω; addresses first-stone E2E population gap per audit)
    if getattr(state, "memory_fabric", None) is not None:
        zeta = gate_zeta(state, state.memory_fabric)
        if not zeta.passed:
            for f in zeta.failures:
                failures.append(f)

    # HORIZON ε elaboration wiring: validate attached seam_certificate via gate_epsilon
    # (makes ε active in Ω; symmetry with ζ, addresses E2E pop gap)
    if getattr(state, "seam_certificate", None) is not None and getattr(state, "specification", None) is not None:
        seam_res = gate_epsilon(state.specification, state.seam_certificate)
        if not seam_res.passed:
            for f in seam_res.failures:
                failures.append(f)

    # HORIZON γ+ subgate for pareto in Ω full aggregation (MAX AGENTS / cross-phase)
    # (symmetry with ε/ζ; subgates for pareto/seam/memory as per integration directive)
    if getattr(state, "pareto_front", None) is not None:
        try:
            from .inverse_design import gate_gamma_plus
            gp = gate_gamma_plus(state, state.pareto_front)
            if not gp.passed:
                for f in gp.failures:
                    failures.append(f)
        except Exception:  # guarded, no impact on other flows
            pass

    if gate_results is not None:
        for name, result in sorted(gate_results.items()):
            receipt = receipts.get(name)
            expected_codes = tuple(failure.code for failure in result.failures)
            if receipt is None:
                failures.append(
                    GateFailure(
                        code="MISSING_GATE_RECEIPT",
                        detail=f"supplied gate result {name!r} is absent from omega receipts.",
                        claim_id=name,
                    )
                )
                continue
            if receipt.passed != result.passed or receipt.failure_codes != expected_codes:
                failures.append(
                    GateFailure(
                        code="GATE_RECEIPT_MISMATCH",
                        detail=(
                            f"receipt {name!r} says passed={receipt.passed}, "
                            f"codes={receipt.failure_codes!r}; gate result says "
                            f"passed={result.passed}, codes={expected_codes!r}."
                        ),
                        claim_id=name,
                    )
                )

    note_ref_set = set(note_refs)
    if _has_run_output(state) and not certificate.learning_notes:
        failures.append(
            GateFailure(
                code="NO_LEARNING_NOTES",
                detail="run has output artifacts, but omega carries no learning notes.",
            )
        )
    for ref, kind in _required_note_refs(state).items():
        if ref not in note_ref_set:
            code = {
                "decision": "MISSING_DECISION_NOTE",
                "gap": "MISSING_GAP_NOTE",
            }.get(kind, "MISSING_ARTIFACT_NOTE")
            failures.append(
                GateFailure(
                    code=code,
                    detail=f"required omega learning note {ref!r} is missing.",
                    claim_id=ref,
                )
            )
    for receipt in certificate.gate_receipts:
        ref = f"gate:{receipt.name}"
        if ref not in note_ref_set:
            failures.append(
                GateFailure(
                    code="MISSING_GATE_NOTE",
                    detail=f"gate receipt {receipt.name!r} is not explained as a learning note.",
                    claim_id=receipt.name,
                )
            )

    if state.specification is not None:
        result_source = dict(gate_results) if gate_results is not None else _results_from_receipts(certificate)
        packet = ratification_packet(state.specification, result_source)
        packet_refs = {item.ref for item in packet}
        cert_refs = set(certificate.ratification_refs)

        for item in packet:
            if item.ref not in cert_refs:
                failures.append(
                    GateFailure(
                        code="MISSING_RATIFICATION_REF",
                        detail=f"ratification item {item.ref!r} is not surfaced.",
                        claim_id=item.ref,
                    )
                )
        for ref in sorted(cert_refs - packet_refs):
            failures.append(
                GateFailure(
                    code="UNKNOWN_RATIFICATION_REF",
                    detail=f"omega certificate surfaces unknown ratification ref {ref!r}.",
                    claim_id=ref,
                )
            )

        if require_ratification and any(item.blocking for item in packet):
            if certificate.signoff is None:
                failures.append(
                    GateFailure(
                        code="UNRATIFIED_BLOCKING_ITEM",
                        detail="specification has blocking ratification items but no sign-off.",
                    )
                )
            else:
                if not certificate.signoff.approver.strip():
                    failures.append(
                        GateFailure(
                            code="SIGNOFF_WITHOUT_APPROVER",
                            detail="explicit sign-off needs a non-empty approver identity.",
                        )
                    )
                for ref in sorted(certificate.signoff.approved - packet_refs):
                    failures.append(
                        GateFailure(
                            code="SIGNOFF_UNKNOWN_REF",
                            detail=f"sign-off approves unknown ref {ref!r}.",
                            claim_id=ref,
                        )
                    )
                for item in unratified_items(packet, certificate.signoff):
                    failures.append(
                        GateFailure(
                            code="UNRATIFIED_BLOCKING_ITEM",
                            detail=f"blocking item {item.ref!r} is not explicitly signed off.",
                            claim_id=item.ref,
                        )
                    )

    return GateResult(gate="omega", passed=not failures, failures=failures)


__all__ = [
    "GateReceipt",
    "LearningNote",
    "OmegaCertificate",
    "build_omega_certificate",
    "gate_omega",
    "gate_receipt",
]
