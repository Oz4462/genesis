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
    "(5) never invent an approach you cannot tie to a claim id; (6) LANGUAGE: "
    "each approach 'name' is written in GERMAN (the reader is German-speaking) — "
    "keep established technical terms and proper nouns as they are; claim ids "
    "stay exactly as given. "
    'Return JSON: [{"name":"...","grounding":["id",...],"tradeoffs":["id",...]}].'
)

# Cap on parsed approaches per round — same bound as the conductor's
# _MAX_SUB_QUESTIONS (LLM output is token-bounded, but the cap makes the limit
# explicit and the overflow auditable instead of implicit).
_MAX_APPROACHES = 10


def approach_id(run_id: str, name: str, grounding: list[str]) -> str:
    """Deterministic id from (run, name, grounding) — stable across identical runs.

    `tradeoffs` is deliberately NOT part of the key: two proposals that differ only
    in tradeoffs are the SAME approach and are merged into one entry (see ``run``).
    Keeping the key unchanged preserves ids across existing checkpoints (Prinzip 5).
    """
    key = name + "|" + "|".join(sorted(grounding))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{run_id}:ap:{digest}"


def _as_str_list(v: object) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()]


def _dedup(ids: list[str]) -> list[str]:
    """Order-preserving de-duplication (first occurrence wins — deterministic)."""
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


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
            raw = await self._cluster(state.question.raw, verified)
        except LLMOutputError as exc:
            state.log.append(f"synthesizer: unparseable LLM output -> abstain: {exc}")
            return state

        # Non-dict array elements are filtered with a count log (audit trail),
        # never silently.
        proposed = [v for v in raw if isinstance(v, dict)]
        skipped = len(raw) - len(proposed)
        if skipped:
            state.log.append(
                f"synthesizer: skipped {skipped} non-dict array element(s) in LLM output"
            )
        if len(proposed) > _MAX_APPROACHES:
            state.log.append(
                f"synthesizer: capping {len(proposed)} proposed approaches "
                f"to {_MAX_APPROACHES}"
            )
            proposed = proposed[:_MAX_APPROACHES]

        emitted: dict[str, Approach] = {}
        for item in proposed:
            name = str(item.get("name") or "").strip()
            # Validate every referenced id against the VERIFIED set. The model cannot
            # invent grounding: ids that are absent or not VERIFIED are dropped here.
            # De-duplicate id lists BEFORE id derivation so `c1|c1` == `c1`.
            grounding = _dedup(
                [cid for cid in _as_str_list(item.get("grounding")) if cid in verified]
            )
            tradeoffs = _dedup(
                [
                    cid
                    for cid in _as_str_list(item.get("tradeoffs"))
                    if cid in verified and cid not in grounding
                ]
            )
            if not name or not grounding:
                state.log.append(
                    f"synthesizer: drop approach {name!r} (no verified grounding)"
                )
                continue
            ap_id = approach_id(run_id, name, grounding)
            if ap_id in emitted:
                # Same approach proposed twice: merge the secondary field into the
                # survivor instead of losing it (tradeoffs are not part of the id).
                survivor = emitted[ap_id]
                merged = [
                    cid
                    for cid in tradeoffs
                    if cid not in survivor.tradeoffs and cid not in survivor.grounding
                ]
                survivor.tradeoffs.extend(merged)
                state.log.append(
                    f"synthesizer: merge duplicate approach {name!r} -> {survivor.id} "
                    f"(+{len(merged)} tradeoff id(s))"
                )
                continue
            approach = Approach(
                id=ap_id,
                name=name,
                grounding=grounding,
                tradeoffs=tradeoffs,
                produced_by=self.name,
                model=self._llm.model,
            )
            emitted[ap_id] = approach
            state.approaches.append(approach)
        if not state.approaches:
            state.log.append("synthesizer: no approach survived grounding validation (abstain)")
        return state

    async def _cluster(self, problem: str, verified: dict) -> list[object]:
        """Return the raw parsed array; ``run`` filters non-dict elements WITH a
        count log (audit trail) — filtering here would be silent."""
        claim_lines = "\n".join(f"{cid}: {c.text}" for cid, c in sorted(verified.items()))
        user = f"PROBLEM:\n{problem}\n\nVERIFIED CLAIMS:\n{claim_lines}"
        resp = await self._llm.complete(system=_SYSTEM, user=user)
        value = extract_json(resp.text, agent="synthesizer")
        if not isinstance(value, list):
            raise LLMOutputError("synthesizer", "expected a JSON array of approaches")
        return value
