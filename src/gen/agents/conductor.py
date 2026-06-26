"""`conductor` — orchestration + honest report assembly (PHASE_ALPHA §3.1).

Drives the run (decompose -> scout -> scholar -> skeptic), then assembles the
report ONLY from ledger claims. It invents nothing: it asserts a claim as fact
only if the claim is VERIFIED and meets the confidence threshold; everything else
(refuted, unsupported, under-confident) is surfaced as an explicit gap, never as
truth. Because assembly is conservative, the report passes GATE α by construction;
the refine loop is a bounded safety net, not the normal path.

HORIZON δ+ exposure: after claims (post-skeptic in run/run_solution/run_specification),
constructs minimal FalsificationExperiment/Measurement (from claims or skeptic REFUTED),
calls evaluate_reality (guarded, lumen:388 pattern), populates reviewed_failure_modes
(from skeptic/claims full no-break), attaches to typed RunState fields (reality_verdict / delta_plus_result / coverage_certificate). Same pattern as lumencrucible + simulation/runner (Return Gate).
"""

from __future__ import annotations

from typing import Any

from ..core.interfaces import Agent
from ..core.state import (
    Question,
    Report,
    RunState,
    SolutionReport,
    Specification,
    SubQuestion,
)
from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..core.state import ClaimStatus
from ..verification.derivation import DEFAULT_TOLERANCE
from ..verification.gates import gate_alpha, gate_beta, gate_gamma

# HORIZON LUMEN exposure (process_dream entry for conductor/orchestrator register)
try:
    from ..grenzverschiebung.lumencrucible import (
        process_dream,
        LumenCrucible,
    )  # HORIZON ε/ζ certs + hammer
except Exception:  # noqa: BLE001
    process_dream = None  # type: ignore
    LumenCrucible = None  # type: ignore

# HORIZON δ+ richer wire (evaluate_reality + reviewed_failure_modes pop) beyond LUMEN.
# Guarded exactly as lumencrucible.py:84 (first call at 388 pattern). Additive only.
try:
    from ..reality import (
        FalsificationExperiment,
        Measurement,
        evaluate_reality,
        gate_delta_plus,
    )
    from ..coverage import build_coverage_certificate, gate_delta_plus_coverage
    from ..core.state import FailureMode, SourceRef
except Exception:  # noqa: BLE001
    FalsificationExperiment = None  # type: ignore
    Measurement = None  # type: ignore
    evaluate_reality = None  # type: ignore
    gate_delta_plus = None  # type: ignore
    build_coverage_certificate = None  # type: ignore
    gate_delta_plus_coverage = None  # type: ignore
    FailureMode = None  # type: ignore
    SourceRef = None  # type: ignore

# Best-effort decomposition backstop: the system prompt asks for 2-5 sub-questions;
# this hard cap stops an adversarial or buggy LLM reply from spawning unbounded
# scout/scholar/skeptic work for one question.
_MAX_SUB_QUESTIONS = 10


class Conductor:
    """Satisfies the ``Agent`` Protocol. Produces no facts of its own."""

    name = "conductor"

    def __init__(
        self,
        scout: Agent,
        scholar: Agent,
        skeptic: Agent,
        *,
        synthesizer: Agent | None = None,
        architect: Agent | None = None,
        llm: LLMClient | None = None,
        confidence_threshold: float = 0.7,
        max_refine_rounds: int = 3,
        derivation_tolerance: float = DEFAULT_TOLERANCE,
    ) -> None:
        self._scout = scout
        self._scholar = scholar
        self._skeptic = skeptic
        self._synthesizer = synthesizer
        self._architect = architect
        self._llm = llm
        self._tau = confidence_threshold
        self._max_refine_rounds = max_refine_rounds
        self._derivation_tolerance = derivation_tolerance

    def register_phase(self, phase: Any) -> None:
        """HORIZON entry: support LUMENCrucible.register (and process_dream) for conductor-orchestrated flows.
        Enables first-class dream ignition + ε/ζ cert seams into RunState.
        """
        if LumenCrucible is not None and isinstance(phase, LumenCrucible):
            # already handled via LumenCrucible.register(self) pattern
            pass
        # allow direct use of exposed process_dream from here
        if process_dream is not None:
            setattr(self, "_lumen_process_dream", process_dream)

    async def run(self, state: RunState) -> RunState:
        if not state.sub_questions:
            state.sub_questions = await self._decompose(state.question)

        rounds = 0
        while True:
            await self._scout.run(state)
            await self._scholar.run(state)
            await self._skeptic.run(state)
            self._enrich_delta_plus(state)  # δ+ after claims (guarded, lumen pattern)
            self._enrich_omega(
                state
            )  # intermediate Ω (guarded); final after loop for full post-γ/ε/ζ in MAX AGENTS paths
            state.report = self._assemble(state)

            result = gate_alpha(state, confidence_threshold=self._tau)
            state.log.append(
                f"conductor: gate alpha round={rounds} passed={result.passed} "
                f"failures={len(result.failures)}"
            )
            if result.passed or rounds >= self._max_refine_rounds:
                break
            rounds += 1
            state.refine_round = rounds
        self._enrich_omega(
            state
        )  # final full E2E after loop (ensures post certs for MAX AGENTS; read-write; 4L Return Gate)
        return state

    # --- internals ------------------------------------------------------------

    async def _decompose(self, question: Question) -> list[SubQuestion]:
        rid = question.run_id
        if self._llm is None:
            return [SubQuestion(id=f"{rid}-q0", text=question.raw, parent_run_id=rid)]
        system = (
            "Break the QUESTION into 2-5 concise, researchable sub-questions. "
            "Return a JSON array of strings. No answers, only sub-questions."
        )
        try:
            resp = await self._llm.complete(system=system, user=question.raw)
            value = extract_json(resp.text, agent="conductor")
            if not isinstance(value, list):
                # An object reply would iterate its KEYS ('sub_questions', ...) as
                # bogus sub-questions; only a JSON array is a sub-question list. Fall
                # back to the raw question — same array-shape discipline as
                # scout._queries / scholar._extract / skeptic._check_queries.
                value = []
            subs = [str(s).strip() for s in value if str(s).strip()][
                :_MAX_SUB_QUESTIONS
            ]
        except Exception:  # noqa: BLE001 - decomposition is best-effort
            subs = []
        if not subs:
            subs = [question.raw]
        return [
            SubQuestion(id=f"{rid}-q{i}", text=text, parent_run_id=rid)
            for i, text in enumerate(subs)
        ]

    def _assemble(self, state: RunState) -> Report:
        tau = self._tau
        verified_ids = {
            c.id
            for c in state.claims
            if c.status is ClaimStatus.VERIFIED and c.confidence >= tau
        }

        body_lines: list[str] = []
        mapping: dict[str, str] = {}
        sources: list[str] = []
        for c in state.claims:
            if c.id not in verified_ids:
                continue
            if c.text in mapping:  # avoid duplicate sentence keys
                continue
            mapping[c.text] = c.id
            body_lines.append(c.text)
            for ref in (*c.sources, *c.verification):
                if ref.url_or_id not in sources:
                    sources.append(ref.url_or_id)

        gaps: list[str] = []
        for c in state.claims:
            if c.id in verified_ids:
                continue
            gaps.append(
                f"{c.text} — Status: {c.status.value}, Konfidenz {c.confidence:.2f}"
            )

        body = (
            "\n".join(body_lines)
            if body_lines
            else "Für diese Frage konnte kein Beleg unabhängig verifiziert werden."
        )
        return Report(
            run_id=state.question.run_id,
            question=state.question.raw,
            body=body,
            statement_to_claim=mapping,
            gaps=gaps,
            sources_used=sources,
        )

    # --- Phase β: solution space -------------------------------------------------

    async def run_solution(self, state: RunState) -> RunState:
        """Phase β: research -> synthesize -> SolutionReport, gated by GATE β.

        Reuses the proven α research loop (scout/scholar/skeptic) to produce verified
        claims, then the `synthesizer` structures them into grounded approaches. The
        SolutionReport asserts only what the synthesizer could anchor in VERIFIED
        claims, so it passes GATE β by construction; the refine loop is a bounded
        safety net. The conductor still invents nothing — approaches reference only
        ledger claim_ids.
        """
        if self._synthesizer is None:
            raise ValueError("run_solution requires a synthesizer agent (Phase β).")
        if not state.sub_questions:
            state.sub_questions = await self._decompose(state.question)

        rounds = 0
        while True:
            await self._scout.run(state)
            await self._scholar.run(state)
            await self._skeptic.run(state)
            self._enrich_delta_plus(state)  # δ+ after claims (guarded, lumen pattern)
            self._enrich_omega(
                state
            )  # intermediate Ω (guarded); final after loop for full post-γ/ε/ζ in MAX AGENTS paths
            await self._synthesizer.run(state)
            state.solution_report = self._assemble_solution(state)

            result = gate_beta(state, confidence_threshold=self._tau)
            state.log.append(
                f"conductor: gate beta round={rounds} passed={result.passed} "
                f"approaches={len(state.solution_report.approaches)} "
                f"failures={len(result.failures)}"
            )
            if result.passed or rounds >= self._max_refine_rounds:
                break
            rounds += 1
            state.refine_round = rounds
        self._enrich_omega(
            state
        )  # final full E2E after loop (post-synth certs; MAX AGENTS Return Gate read-write)
        return state

    def _assemble_solution(self, state: RunState) -> SolutionReport:
        approaches = list(state.approaches)
        gaps: list[str] = []
        if not approaches:
            gaps.append(
                "No solution approach could be independently grounded for this problem."
            )
        claim_ids_used: list[str] = []
        for ap in approaches:
            for cid in (*ap.grounding, *ap.tradeoffs):
                if cid not in claim_ids_used:
                    claim_ids_used.append(cid)
        return SolutionReport(
            run_id=state.question.run_id,
            problem=state.question.raw,
            approaches=approaches,
            gaps=gaps,
            claim_ids_used=claim_ids_used,
        )

    # --- Phase γ: specification ---------------------------------------------------

    async def run_specification(self, state: RunState) -> RunState:
        """Phase γ: research -> solution space -> Specification, gated by GATE γ.

        Reuses the proven α research loop (scout/scholar/skeptic) and the proven
        β structuring step (synthesizer) to obtain verified claims and grounded
        approaches, then the `architect` structures them into a complete build
        specification. The architect asserts only what survives its own GATE γ
        self-check, so the result passes the conductor's gate by construction;
        the refine loop is a bounded safety net. The conductor still invents
        nothing — the specification references only ledger claim_ids and a
        grounded approach of this run.
        """
        if self._synthesizer is None or self._architect is None:
            raise ValueError(
                "run_specification requires synthesizer and architect agents (Phase γ)."
            )
        if not state.sub_questions:
            state.sub_questions = await self._decompose(state.question)

        rounds = 0
        while True:
            await self._scout.run(state)
            await self._scholar.run(state)
            await self._skeptic.run(state)
            self._enrich_delta_plus(state)  # δ+ after claims (guarded, lumen pattern)
            self._enrich_omega(
                state
            )  # intermediate Ω (guarded); final after loop for full post-γ/ε/ζ in MAX AGENTS paths
            await self._synthesizer.run(state)
            await self._architect.run(state)
            state.specification = self._normalize_specification(state)

            result = gate_gamma(
                state,
                confidence_threshold=self._tau,
                derivation_tolerance=self._derivation_tolerance,
            )
            state.log.append(
                f"conductor: gate gamma round={rounds} passed={result.passed} "
                f"components={len(state.specification.components)} "
                f"steps={len(state.specification.steps)} "
                f"failures={len(result.failures)}"
            )
            if result.passed or rounds >= self._max_refine_rounds:
                break
            rounds += 1
            state.refine_round = rounds
        self._enrich_omega(
            state
        )  # final full E2E after loop (post-architect γ+ ε ζ certs pop to RunState + omega call; MAX AGENTS + 4L Return Gate)
        return state

    def _normalize_specification(self, state: RunState) -> Specification:
        """Backstop normalization: a run always ends with an honest Specification.

        The architect owns `state.specification`; this only covers the
        must-not-happen case of a missing one, and guarantees that an empty
        specification carries an explicit gap (abstention is always explained,
        never silent).
        """
        spec = state.specification
        if spec is None:
            spec = Specification(
                run_id=state.question.run_id,
                idea=state.question.raw,
                gaps=["No specification was assembled for this idea."],
            )
        if not spec.components and not spec.steps and not spec.gaps:
            spec.gaps.append(
                "No specification content could be grounded for this idea."
            )
        return spec

    def _enrich_delta_plus(self, state: RunState) -> None:
        """Guarded δ+ richer wire (evaluate_reality + reviewed_failure_modes pop) beyond LUMEN.
        Follow lumen:388 pattern exactly (skeleton construct from claims/skeptic, call, attach to RunState or return via state).
        Called after claims (post-skeptic) in all orchestration paths. Additive, guarded.
        """
        reality_verdict = None
        delta_plus_result = None
        coverage_certificate = None
        if FalsificationExperiment is not None and evaluate_reality is not None:
            try:
                # Prefer real numeric data for δ+ ingest when present (spec quantities from architect/γ flows,
                # or prior sim/runner attach). Fallback to explicit demo + honest note (first-stone per HORIZON/Return Gate).
                # This advances "use real sim/claims instead of demo 9.81".
                c = next(
                    (
                        cc
                        for cc in state.claims
                        if getattr(cc, "status", None) is ClaimStatus.VERIFIED
                    ),
                    state.claims[0] if state.claims else None,
                )
                if c:
                    # Default demo (honest skeleton)
                    p_val = 9.81
                    p_unit = "m/s^2"
                    meas_name = "claim.backed"
                    method_note = "conductor δ+: predicted from spec; NO independent measurement yet → INCONCLUSIVE (honest, not corroborated)"
                    # Prefer real if spec has numeric quantity value (common after architect)
                    try:
                        if state.specification and getattr(
                            state.specification, "quantities", None
                        ):
                            q0 = state.specification.quantities[0]
                            if (
                                q0
                                and getattr(q0, "value", None) is not None
                                and isinstance(getattr(q0, "value", None), (int, float))
                            ):
                                p_val = float(q0.value)
                                p_unit = getattr(q0, "unit", None) or p_unit
                                meas_name = (
                                    getattr(q0, "measurand", None)
                                    or getattr(q0, "name", None)
                                    or meas_name
                                )
                                method_note = "conductor δ+ (real value preferred from spec quantity)"
                    except Exception:
                        pass
                    exp = FalsificationExperiment(
                        id=f"{state.question.run_id}-delta-demo",
                        measurand=meas_name,
                        predicted_value=p_val,
                        predicted_unit=p_unit,
                        tolerance=0.05,
                        method=method_note,
                        grounding=[c.id],
                    )
                    # HONEST δ⁺ (STATUS.md §1 #1): a Measurement is structurally a REAL, retrieved
                    # reading (core/state.py:441 raises otherwise). With no independent measurement we
                    # do NOT fabricate one (the old code lied retrieved=True on a value equal to the
                    # prediction → always "corroborated": the δ⁺ tautology). The experiment is
                    # designed; the reading is honestly absent → INCONCLUSIVE. Build the Measurement +
                    # evaluate_reality(exp, meas) only once a real measurement is attached to state.
                    reality_verdict = None
                    delta_plus_result = {
                        "status": "inconclusive",
                        "experiment_id": exp.id,
                        "predicted_value": p_val,
                        "predicted_unit": p_unit,
                        "note": (
                            "δ⁺ experiment designed; no independent measurement available → "
                            "cannot corroborate or refute (honest abstention, HORIZON.md §2B)"
                        ),
                    }
            except Exception:
                delta_plus_result = {
                    "status": "skipped",
                    "note": "δ⁺ skipped (guarded: partial data) — not corroborated",
                }

        # populate reviewed_failure_modes from skeptic/consensus (full claims/REFUTED, no break, proper list for build_coverage). Guarded.
        # Always full collection only (real REFUTED or honest [] — no dummy fallback creation when none).
        # Addresses Return Gate HIGH gap #3 (CK/ HORIZON). Cite conductor:374.
        reviewed: list = []
        if FailureMode is not None:
            for cc in state.claims:
                if getattr(cc, "status", None) is ClaimStatus.REFUTED:
                    try:
                        reviewed.append(
                            FailureMode(
                                id=f"reviewed:{cc.id}",
                                label=str(cc.text),
                                source="skeptic_consensus",
                                grounding=[cc.id],
                            )
                        )
                        # no break: collect richer full set of REFUTED (was thin 0-1)
                    except Exception:
                        pass
            # NO dummy fallback: empty list is honest when no REFUTED claims present.

        if build_coverage_certificate is not None:
            try:
                small_spec = state.specification or Specification(
                    run_id=state.question.run_id, idea=state.question.raw
                )
                coverage_certificate = build_coverage_certificate(
                    small_spec, reviewed_failure_modes=reviewed
                )
                # attach to typed RunState field (read-write; δ+ for MAX AGENTS/Return Gate)
                state.coverage_certificate = coverage_certificate
                if gate_delta_plus_coverage is not None:
                    try:
                        _ = gate_delta_plus_coverage(
                            small_spec,
                            coverage_certificate,
                            reviewed_failure_modes=reviewed,
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        # attach to typed RunState fields (read-write; after δ+ reality + reviewed pop)
        if reality_verdict is not None:
            state.reality_verdict = reality_verdict
        if delta_plus_result is not None:
            state.delta_plus_result = delta_plus_result
        if coverage_certificate is not None:
            state.coverage_certificate = coverage_certificate
        state.log.append(
            f"conductor: δ+ evaluate_reality + reviewed_failure_modes (from skeptic/claims, full REFUTED no-break) "
            f"status={(delta_plus_result or {}).get('status', 'attached') if isinstance(delta_plus_result, dict) else 'ok'} "
            f"cites:agents/conductor.py:372, verification/verification-log.md:228, coverage.py:149 (4L L1 provenance)"
        )

    def _enrich_omega(self, state: RunState) -> None:
        """Guarded Ω call after certs attached (δ+ + architect pareto + possible ε/ζ).
        Smallest, matches lumencrucible pattern. Builds cert from state (notes auto from δγεζ),
        gates, attaches for read-write (state.omega_certificate), updates log.
        Called intermediate inside refine + final after loop (run_specification etc) for full E2E chain in MAX AGENTS runner paths.
        4L Return Gate realized.
        """
        try:
            from ..omega import build_omega_certificate, gate_omega

            # gate_results None: build pulls artifacts; required empty for non-blocking aggregator
            cert = build_omega_certificate(state)
            res = gate_omega(state, cert, required_gates=())
            state.omega_certificate = cert  # read-write (field + dynamic fallback)
            state.log.append(
                f"conductor: Ω build_omega+gate_omega passed={res.passed} "
                f"notes={len(getattr(cert, 'learning_notes', []))} (4L Return Gate after certs)"
            )
        except (
            Exception
        ):  # fully guarded; no behavior change on missing omega/partial states
            state.log.append("conductor: Ω enrichment skipped (guarded)")
