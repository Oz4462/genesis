"""`synthesizer` — Phase β: structure VERIFIED claims into real solution approaches.

Takes the verified claims the α pipeline produced and clusters them into distinct,
named solution Approaches (alternatives). Like the `conductor`, it INVENTS NOTHING:
an Approach only references claim_ids that exist and are VERIFIED at or above the
threshold. The LLM proposes the grouping and labels — a judgement, not a fact, like
`scout`'s query phrasing — and then this CODE validates every referenced id against
the verified set and drops anything the model invented. An approach with no surviving
VERIFIED grounding is never emitted: a fabricated approach cannot leave this agent,
the β-analogue of `scholar`'s verbatim-quote guard.

See docs/agents/synthesizer.md and PHASE_BETA.md §3.1.
"""

from __future__ import annotations

import hashlib

from ..core.errors import LLMOutputError
from ..core.state import Approach, ClaimStatus, RunState
from ..llm.base import LLMClient
from ..llm.parsing import extract_json

_SYSTEM = (
    "You group VERIFIED factual claims about a PROBLEM into distinct solution "
    "APPROACHES (alternatives). Rules: (1) use ONLY the given claims, never outside "
    "knowledge; (2) reference each claim by its EXACT id; (3) each claim id is either "
    "a grounding (it establishes the approach exists / is used for the problem) or a "
    "tradeoff (a property, pro, or con); (4) every approach needs >=1 grounding id; "
    "(5) never invent an approach you cannot tie to a claim id. "
    'Return JSON: [{"name":"...","grounding":["id",...],"tradeoffs":["id",...]}].'
)


def approach_id(run_id: str, name: str, grounding: list[str]) -> str:
    """Deterministic id from (run, name, grounding) — stable across identical runs."""
    key = name + "|" + "|".join(sorted(grounding))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{run_id}:ap:{digest}"


def _as_str_list(v: object) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()]


class Synthesizer:
    """Satisfies the ``Agent`` Protocol. Writes only ``state.approaches``.

    Produces no facts of its own; every approach is anchored in existing VERIFIED
    claims. Rebuilds ``state.approaches`` from scratch on each call so it is
    idempotent across the conductor's refine rounds.
    """

    name = "synthesizer"

    def __init__(self, llm: LLMClient, *, confidence_threshold: float = 0.7) -> None:
        self._llm = llm
        self._tau = confidence_threshold

    async def run(self, state: RunState) -> RunState:
        run_id = state.question.run_id
        verified = {
            c.id: c
            for c in state.claims
            if c.status is ClaimStatus.VERIFIED and c.confidence >= self._tau
        }
        state.approaches = []  # rebuild each round (idempotent)
        if not verified:
            state.log.append("synthesizer: no VERIFIED claims -> no approach (abstain)")
            return state

        try:
            proposed = await self._cluster(state.question.raw, verified)
        except LLMOutputError as exc:
            state.log.append(f"synthesizer: unparseable LLM output -> abstain: {exc}")
            return state

        seen: set[str] = set()
        for item in proposed:
            name = (item.get("name") or "").strip()
            # Validate every referenced id against the VERIFIED set. The model cannot
            # invent grounding: ids that are absent or not VERIFIED are dropped here.
            grounding = [cid for cid in _as_str_list(item.get("grounding")) if cid in verified]
            tradeoffs = [
                cid
                for cid in _as_str_list(item.get("tradeoffs"))
                if cid in verified and cid not in grounding
            ]
            if not name or not grounding:
                state.log.append(
                    f"synthesizer: drop approach {name!r} (no verified grounding)"
                )
                continue
            ap_id = approach_id(run_id, name, grounding)
            if ap_id in seen:
                continue
            seen.add(ap_id)
            state.approaches.append(
                Approach(
                    id=ap_id,
                    name=name,
                    grounding=grounding,
                    tradeoffs=tradeoffs,
                    produced_by=self.name,
                    model=self._llm.model,
                )
            )
        if not state.approaches:
            state.log.append("synthesizer: no approach survived grounding validation (abstain)")
        return state

    async def _cluster(self, problem: str, verified: dict) -> list[dict]:
        claim_lines = "\n".join(f"{cid}: {c.text}" for cid, c in verified.items())
        user = f"PROBLEM:\n{problem}\n\nVERIFIED CLAIMS:\n{claim_lines}"
        resp = await self._llm.complete(system=_SYSTEM, user=user)
        value = extract_json(resp.text, agent="synthesizer")
        if not isinstance(value, list):
            raise LLMOutputError("synthesizer", "expected a JSON array of approaches")
        return [v for v in value if isinstance(v, dict)]
