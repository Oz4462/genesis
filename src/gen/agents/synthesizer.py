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

# D13 (low): cap on parsed approaches (token-bounded LLM output, but consistent with
# conductor._MAX_SUB_QUESTIONS=10 and architect caps). Non-vacuous risk low.
_MAX_APPROACHES = 10

_SYSTEM = (
    "You group VERIFIED factual claims about a PROBLEM into distinct solution "
    "APPROACHES (alternatives). Rules: (1) use ONLY the given claims, never outside "
    "knowledge; (2) reference each claim by its EXACT id; (3) each claim id is either "
    "a grounding (it establishes the approach exists / is used for the problem) or a "
    "tradeoff (a property, pro, or con); (4) every approach needs >=1 grounding id; "
    "(5) never invent an approach you cannot tie to a claim id; (6) LANGUAGE: "
    "each approach 'name' is written in GERMAN (the reader is German-speaking) — "
    "keep established technical terms and proper nouns as they are; claim ids "
    "stay exactly as given. "
    'Return JSON: [{"name":"...","grounding":["id",...],"tradeoffs":["id",...]}].'
)


def approach_id(run_id: str, name: str, grounding: list[str], tradeoffs: list[str] | None = None) -> str:
    """Deterministic id from (run, name, grounding, tradeoffs) — includes secondary to prevent
    D13(a) collision (two approaches same name/grounding but diff tradeoffs/mech were dropped).
    Secondary folded in for id stability within run."""
    key = name + "|" + "|".join(sorted(grounding))
    if tradeoffs:
        key += "|t:" + "|".join(sorted(tradeoffs))
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
    D13 notes (low, smallest): secondary fields now in id; grounding deduped pre-emit;
    cap applied; non-dict filter count not logged (honest note only).
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

        # D13: cap + grounding dedup before id/emit (c1|c1 weakened dedup; now unique list)
        proposed = proposed[:_MAX_APPROACHES]
        seen: set[str] = set()
        for item in proposed:
            name = str(item.get("name") or "").strip()
            # Validate every referenced id against the VERIFIED set. The model cannot
            # invent grounding: ids that are absent or not VERIFIED are dropped here.
            raw_g = _as_str_list(item.get("grounding"))
            grounding: list[str] = []
            for cid in raw_g:
                if cid in verified and cid not in grounding:
                    grounding.append(cid)
            raw_t = _as_str_list(item.get("tradeoffs"))
            tradeoffs: list[str] = []
            for cid in raw_t:
                if cid in verified and cid not in grounding and cid not in tradeoffs:
                    tradeoffs.append(cid)
            if not name or not grounding:
                state.log.append(
                    f"synthesizer: drop approach {name!r} (no verified grounding)"
                )
                continue
            ap_id = approach_id(run_id, name, grounding, tradeoffs)
            if ap_id in seen:
                state.log.append(f"synthesizer: drop duplicate approach {name!r}")
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
        claim_lines = "\n".join(f"{cid}: {c.text}" for cid, c in sorted(verified.items()))
        user = f"PROBLEM:\n{problem}\n\nVERIFIED CLAIMS:\n{claim_lines}"
        resp = await self._llm.complete(system=_SYSTEM, user=user)
        value = extract_json(resp.text, agent="synthesizer")
        if not isinstance(value, list):
            raise LLMOutputError("synthesizer", "expected a JSON array of approaches")
        # D13(d): non-dict array elems filtered here (for safety); count-log omitted
        # (fn stateless, no access to state.log; token-bounded input, low audit risk).
        # See D13 honest note in class + WORK_QUEUE.
        return [v for v in value if isinstance(v, dict)]
