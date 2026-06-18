"""symbiosis — the Human-Grok-GENESIS Symbiosis Protocol (build doc 4.4, Phase 3).

The division of labour the doc fixes: **Grok = breadth** (it proposes candidate formula
hypotheses — which exponents, which groupings — over its broad world knowledge), **GENESIS =
verification** (every proposal runs through the SAME gates as everything else). The hard law,
not negotiable: *Grok output is a proposal, never truth.* Grok widens the search space; it
never delivers the verdict.

Two honesty guarantees are built in:

  * EVERY proposal is gated. A `Proposal` is only ever turned into a `Candidate` and judged by
    `engine.judge_candidate` — there is no path in which a Grok hypothesis is accepted on
    Grok's say-so. A dimensionally impossible proposal comes back ``widerlegt`` like any other.
  * GENESIS runs WITHOUT Grok. With no proposer the protocol falls back to the engine's own
    dimensional discovery, so the system never depends on the external model.

On the cross-model discipline: the proposer is the xAI family (``model_family('grok-build') ==
'xai'``) and the verifier is the DETERMINISTIC gate — a model-free checker. That is a stronger
separation than the usual LLM-vs-LLM family split (`verification.cross_model`): the thing that
judges cannot share a failure mode with the thing that proposes, because it is not a model at
all. The proposer's family is recorded in provenance for the audit.

The proposer sits behind the mockable ``LLMClient`` seam (``llm.base``), so the protocol is
fully testable offline with a scripted client; live runs use ``GrokCLI(model='grok-build')``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..verification.cross_model import model_family
from .engine import (
    Candidate,
    DiscoveryProblem,
    DiscoveryResult,
    DiscoveryVerdict,
    candidate_from_exponents,
    discover_new_formulas,
    judge_candidate,
    DEFAULT_R2_THRESHOLD,
)


@dataclass(frozen=True)
class Proposal:
    """A breadth proposal: a candidate power-law exponent hypothesis + a rationale + its source
    (e.g. ``grok-build``). A proposal asserts NOTHING until the gate judges it."""

    exponents: dict[str, float]
    rationale: str
    source: str


@dataclass(frozen=True)
class JudgedProposal:
    """A proposal after the gate has spoken — the honest record of a breadth idea."""

    proposal: Proposal
    verdict: DiscoveryVerdict


@dataclass(frozen=True)
class SymbiosisResult:
    """The outcome: GENESIS's own dimensional discovery, every breadth proposal gated, and the
    union of all gate-PASSED verdicts (best first). `used_proposer` is False on the Grok-free
    fallback path."""

    own: DiscoveryResult
    judged_proposals: tuple[JudgedProposal, ...]
    validated: tuple[DiscoveryVerdict, ...]
    used_proposer: bool


class GrokProposer:
    """Breadth via a Grok model (default ``GrokCLI(model='grok-build')``, overridable for tests
    with any ``LLMClient``). It ONLY produces ``Proposal``s — the gate disposes."""

    def __init__(self, client: LLMClient | None = None, *, model: str = "grok-build") -> None:
        if client is None:
            from ..llm.grok_cli import GrokCLI
            client = GrokCLI(model=model)
        self._client = client
        self.model = client.model
        self.family = model_family(self.model)  # 'xai' for grok — recorded for the audit

    def _prompt(self, problem: DiscoveryProblem, n: int) -> tuple[str, str]:
        inputs = ", ".join(f"{v.name} [{v.unit}]" for v in problem.inputs)
        consts = ", ".join(f"{c.name} [{c.unit}]" for c in problem.constants) or "(keine)"
        system = ("Du bist ein Physik-Hypothesen-Generator. Schlage Potenzgesetz-Exponenten "
                  "(target = C * prod(quelle^exponent)) vor. Antworte AUSSCHLIESSLICH mit JSON.")
        user = (f"Ziel: {problem.target.name} [{problem.target.unit}]. "
                f"Quellen: {inputs}. Konstanten: {consts}. Idee: {problem.idea}\n"
                f"Gib {n} Hypothesen als JSON-Array, jede "
                '{"exponents": {"<quelle>": <zahl>, ...}, "rationale": "<kurz>"}.')
        return system, user

    async def propose(self, problem: DiscoveryProblem, *, n: int = 4) -> list[Proposal]:
        """Ask the model for `n` exponent hypotheses; parse them into Proposals. Tolerant to
        the usual LLM JSON noise (``llm.parsing.extract_json``); a malformed item is skipped,
        not trusted. Never raises on a bad hypothesis — the gate handles correctness."""
        system, user = self._prompt(problem, n)
        resp = await self._client.complete(system=system, user=user)
        try:
            data = extract_json(resp.text, agent="grok-proposer")
        except Exception:
            return []
        items = data if isinstance(data, list) else [data]
        out: list[Proposal] = []
        for item in items:
            if not isinstance(item, dict) or "exponents" not in item:
                continue
            try:
                exps = {str(k): float(v) for k, v in item["exponents"].items()}
            except (TypeError, ValueError):
                continue
            out.append(Proposal(exponents=exps, rationale=str(item.get("rationale", "")),
                                source=self.model))
        return out


def _gate_proposals(problem: DiscoveryProblem, proposals: list[Proposal], *,
                    known_laws, r2_threshold) -> list[JudgedProposal]:
    judged: list[JudgedProposal] = []
    for p in proposals:
        try:
            cand: Candidate = candidate_from_exponents(problem, p.exponents)
        except Exception:
            continue  # a proposal naming an unknown source is dropped, never trusted
        verdict = judge_candidate(problem, cand, known_laws=known_laws, r2_threshold=r2_threshold)
        judged.append(JudgedProposal(proposal=p, verdict=verdict))
    return judged


def symbiosis_discover(
    problem: DiscoveryProblem,
    *,
    proposals: list[Proposal] | None = None,
    proposer: GrokProposer | None = None,
    n_proposals: int = 4,
    known_laws: dict[str, dict[str, float]] | None = None,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
) -> SymbiosisResult:
    """Run the symbiosis loop: GENESIS's own dimensional discovery ALWAYS runs (so the system
    works without Grok); a proposer (or pre-fetched `proposals`) widens the candidate space,
    and EVERY proposal is gated by ``judge_candidate``. The validated set is the union of all
    gate-passed verdicts. Deterministic given the inputs.

    Grok = breadth, GENESIS = verification: a proposal is never accepted on the proposer's
    authority — only the gate's verdict counts.
    """
    own = discover_new_formulas(problem, known_laws=known_laws, r2_threshold=r2_threshold)

    props = list(proposals or [])
    used_proposer = bool(props)
    if proposer is not None and not props:
        props = asyncio.run(proposer.propose(problem, n=n_proposals))
        used_proposer = True

    judged = _gate_proposals(problem, props, known_laws=known_laws, r2_threshold=r2_threshold)

    validated = list(own.validated) + [j.verdict for j in judged if j.verdict.passed]
    # dedup by formula expression, keep best fit first
    seen: set[str] = set()
    unique: list[DiscoveryVerdict] = []
    for v in sorted(validated, key=lambda v: (-v.candidate.r_squared, v.candidate.complexity)):
        if v.candidate.expression not in seen:
            seen.add(v.candidate.expression)
            unique.append(v)

    return SymbiosisResult(own=own, judged_proposals=tuple(judged),
                           validated=tuple(unique), used_proposer=used_proposer)
