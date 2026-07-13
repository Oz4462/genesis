"""`conductor` — orchestration + honest report assembly (PHASE_ALPHA §3.1).

Drives the run (decompose -> scout -> scholar -> skeptic), then assembles the
report ONLY from ledger claims. It invents nothing: it asserts a claim as fact
only if the claim is VERIFIED and meets the confidence threshold; everything else
(refuted, unsupported, under-confident) is surfaced as an explicit gap, never as
truth. Because assembly is conservative, the report passes GATE α by construction;
the refine loop is a bounded safety net, not the normal path.
"""

from __future__ import annotations

from ..core.interfaces import Agent
from ..core.state import Question, Report, RunState, SolutionReport, Specification, SubQuestion
from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..core.state import ClaimStatus
from ..verification.derivation import DEFAULT_TOLERANCE
from ..verification.gates import gate_alpha, gate_beta, gate_gamma

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

    async def run(self, state: RunState) -> RunState:
        if not state.sub_questions:
            state.sub_questions = await self._decompose(state.question)
            state.log.append(
                f"conductor: decomposed into {len(state.sub_questions)} sub-question(s)"
            )

        rounds = 0
        while True:
            state.log.append(f"conductor: α round={rounds} scout…")
            await self._scout.run(state)
            state.log.append(
                f"conductor: α round={rounds} scholar… "
                f"candidates={len(state.candidates)}"
            )
            await self._scholar.run(state)
            state.log.append(
                f"conductor: α round={rounds} skeptic… claims={len(state.claims)}"
            )
            await self._skeptic.run(state)
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
            subs = [str(s).strip() for s in value if str(s).strip()][:_MAX_SUB_QUESTIONS]
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
