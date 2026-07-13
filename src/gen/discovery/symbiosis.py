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

On the cross-model discipline: the proposer is the xAI family (``model_family('grok-4.5') ==
'xai'``) and the verifier is the DETERMINISTIC gate — a model-free checker. That is a stronger
separation than the usual LLM-vs-LLM family split (`verification.cross_model`): the thing that
judges cannot share a failure mode with the thing that proposes, because it is not a model at
all. The proposer's family is recorded in provenance for the audit.

The proposer sits behind the mockable ``LLMClient`` seam (``llm.base``), so the protocol is
fully testable offline with a scripted client; live runs use ``GrokCLI(model='grok-4.5')``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..llm.base import LLMClient
from ..llm.schemas import parse_proposals
from .canonical import dedupe_by_exponents
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
    """Breadth via a Grok model (default ``GrokCLI(model='grok-4.5')``, overridable for tests
    with any ``LLMClient``). It ONLY produces ``Proposal``s — the gate disposes."""

    def __init__(self, client: LLMClient | None = None, *, model: str = "grok-4.5") -> None:
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
        # Validated parse (llm.schemas): the whole payload unparseable -> []; a shape-invalid item is
        # skipped (honest abstention), never trusted. Canonical dedup (canonical.py) drops a model's own
        # repeated forms so the gate never judges the same law twice. The gate still judges the rest.
        proposals = [
            Proposal(exponents=dict(m.exponents), rationale=m.rationale, source=self.model)
            for m in parse_proposals(resp.text, agent="grok-proposer")
        ]
        return dedupe_by_exponents(proposals, key=lambda p: p.exponents)


def _gate_proposals(problem: DiscoveryProblem, proposals: list[Proposal], *,
                    known_laws, r2_threshold) -> list[JudgedProposal]:
    judged: list[JudgedProposal] = []
    for p in proposals:
        try:
            cand: Candidate = candidate_from_exponents(problem, p.exponents)
        except Exception:  # noqa: BLE001 — unbuildable proposal: abstain (skip), never trust
            # Intentional: unknown/malformed sources are not candidates for the gate.
            continue
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


# ---------------------------------------------------------------------------------------------------
# Cross-model COUNCIL — grok AND Claude live in GENESIS, both proposing, the gate the final authority
# ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class CouncilResult:
    """A cross-model council run: GENESIS's own dimensional discovery, every proposal from EACH model
    gated, the gate-passed union (best first), and the audit of which model families took part.

    The anti-hallucination law is unchanged: a model — grok OR Claude — only ever WIDENS the candidate
    space; ``judge_candidate`` (deterministic, model-free) is the sole authority on what is true.
    ``cross_model`` is True when ≥ 2 distinct model families proposed (a genuine second family, the
    skeptic discipline), so no single model's blind spot can carry a candidate through."""

    own: DiscoveryResult
    judged_by_model: dict[str, tuple[JudgedProposal, ...]]
    validated: tuple[DiscoveryVerdict, ...]
    families: tuple[str, ...]
    cross_model: bool


def council_discover(
    problem: DiscoveryProblem,
    *,
    proposers: list[GrokProposer],
    n_proposals: int = 4,
    known_laws: dict[str, dict[str, float]] | None = None,
    r2_threshold: float = DEFAULT_R2_THRESHOLD,
) -> CouncilResult:
    """Run the cross-model council: GENESIS's own discovery ALWAYS runs (it works with no model at
    all), then EACH proposer (grok, Claude, …) widens the candidate space, and EVERY proposal — from
    whichever model — is gated by ``judge_candidate``. The validated set is the union of all
    gate-passed verdicts, deduped, best fit first. Provenance records, per model, what it proposed and
    how the gate judged it. Deterministic GIVEN the proposers (live CLIs are non-deterministic; pass
    ``ScriptedLLM``-backed proposers for a reproducible run).

    This is how grok and Claude live INSIDE GENESIS: they contribute formulas GENESIS may not have
    found on its own, and the deterministic gate — never a model — decides what survives."""
    own = discover_new_formulas(problem, known_laws=known_laws, r2_threshold=r2_threshold)
    judged_by_model: dict[str, tuple[JudgedProposal, ...]] = {}
    all_judged: list[JudgedProposal] = []
    families: list[str] = []
    for pr in proposers:
        families.append(model_family(pr.model))
        props = asyncio.run(pr.propose(problem, n=n_proposals))
        judged = _gate_proposals(problem, props, known_laws=known_laws, r2_threshold=r2_threshold)
        judged_by_model[pr.model] = tuple(judged)
        all_judged.extend(judged)

    validated = list(own.validated) + [j.verdict for j in all_judged if j.verdict.passed]
    seen: set[str] = set()
    unique: list[DiscoveryVerdict] = []
    for v in sorted(validated, key=lambda v: (-v.candidate.r_squared, v.candidate.complexity)):
        if v.candidate.expression not in seen:
            seen.add(v.candidate.expression)
            unique.append(v)

    fam_set = tuple(sorted(set(families)))
    return CouncilResult(own=own, judged_by_model=judged_by_model, validated=tuple(unique),
                         families=fam_set, cross_model=len(fam_set) >= 2)


def default_council(*, grok_model: str = "grok-4.5",
                    claude_model: str = "claude-opus-4-8") -> list[GrokProposer]:
    """Build the LIVE cross-model council: a grok proposer (xAI family) AND a Claude proposer
    (anthropic family), each a real CLI. Opt-in and non-deterministic (it shells out to the
    installed ``grok`` and ``claude`` CLIs); for offline/reproducible runs use ``scripted_council``
    (the default everywhere) instead.

    Default ``grok_model`` is ``grok-4.5`` (the only current Grok CLI id). Legacy ``grok-build``
    is accepted via ``GrokCLI`` alias → ``grok-4.5``. Offline ``CAPTURED_PROPOSALS`` keys may still
    say ``grok-build`` as the historical capture label for scripted replay.
    """
    from ..llm.claude_cli import ClaudeCLI
    from ..llm.grok_cli import GrokCLI

    return [
        GrokProposer(client=GrokCLI(model=grok_model), model=grok_model),
        GrokProposer(client=ClaudeCLI(model=claude_model), model=claude_model),
    ]


# Real proposals captured LIVE from the grok and claude CLIs (2026-06-19), verbatim. Replaying them
# lets the OFFLINE council demonstrate the gate on genuinely model-authored hypotheses — reproducibly
# and with no network — which is exactly why it is the default: the grok + claude CLIs are always
# implemented as the live runtime brain, but the suite and the default council run offline (owner
# directive). Keyed by benchmark-case name -> {model_id: proposals_json}. Each model offers the
# correct law plus dimensionally-wrong rivals, so the gate visibly rejects bad breadth.
CAPTURED_PROPOSALS: dict[str, dict[str, str]] = {
    "Pendulum period": {
        "grok-build": '[{"exponents":{"L":0.5,"g":-0.5},"rationale":"T=2pi sqrt(L/g)"},'
                      '{"exponents":{"L":1,"g":-0.5},"rationale":"falsche lineare L-Abhaengigkeit"},'
                      '{"exponents":{"L":1,"g":-1},"rationale":"falsch"}]',
        "claude-opus-4-8": '[{"exponents":{"L":0.5,"g":-0.5},"rationale":"Dimensionsanalyse T=2pi sqrt(L/g)"},'
                           '{"exponents":{"L":1.0,"g":-0.5},"rationale":"dimensional inkonsistent, Rivale"},'
                           '{"exponents":{"L":0.5,"g":-1.0},"rationale":"dimensional inkonsistent, Kontrast"}]',
    },
    "Kepler III": {
        "grok-build": '[{"exponents":{"a":1.5,"mu":-0.5},"rationale":"Kepler III T=2pi sqrt(a^3/mu)"},'
                      '{"exponents":{"a":1.5},"rationale":"mu konstant, in C absorbiert"},'
                      '{"exponents":{"a":3,"mu":-1},"rationale":"Fehler: gilt fuer T^2"}]',
        "claude-opus-4-8": '[{"exponents":{"a":1.5,"mu":-0.5},"rationale":"Kepler 3 exakt, Dimension s"},'
                           '{"exponents":{"a":1.5,"mu":0},"rationale":"ohne mu, dimensional unvollstaendig"},'
                           '{"exponents":{"a":2.0,"mu":-0.5},"rationale":"steilere Bahnabhaengigkeit, Rivale"}]',
    },
}


def scripted_council(proposals: dict[str, str]) -> list[GrokProposer]:
    """Build an OFFLINE, deterministic council from already-captured proposals: one ``GrokProposer``
    per ``{model_id: proposals_json}`` entry, each backed by a ``ScriptedLLM`` (no network, no live
    CLI). Same gate, same cross-model audit as the live path — only the breadth source is replayed,
    so the run is fully reproducible. This is the default for ``gen --mode council`` and the council
    tests; ``default_council()`` (``--live``) swaps in the real grok + claude CLIs."""
    from ..llm.base import ScriptedLLM

    return [GrokProposer(client=ScriptedLLM(model, text), model=model)
            for model, text in proposals.items()]
