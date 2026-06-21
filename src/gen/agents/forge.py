"""`forge` — Phase φ: develop a Spark into grounded Possibilities (HORIZON.md).

The model-shaped layer of the "workshop for the spark". Takes the human's raw Spark
plus the VERIFIED claims established by α, asks the LLM to open it into possible
directions — each CITING the exact claim_id that anchors its mechanism — and then this
CODE validates every cited id against the VERIFIED set and drops anything the model
invented. A possibility with no surviving VERIFIED grounding never leaves this agent:
a fabricated direction cannot exist, the φ-analogue of `scholar`'s verbatim-quote guard
and `synthesizer`'s grounding guard. The output is always marked as a grounded SAMPLE,
never the whole space (HORIZON.md §3) — GATE φ enforces both.

See docs/HORIZON.md §5 and verification/gates.py::gate_phi.
"""

from __future__ import annotations

import hashlib

from ..core.errors import LLMOutputError
from ..core.state import ClaimStatus, Divergence, Possibility, RunState
from ..llm.base import LLMClient
from ..llm.parsing import extract_json

# D13 (low): cap on parsed possibilities (consistent with _MAX_APPROACHES and conductor).
_MAX_POSSIBILITIES = 10

_SYSTEM = (
    "You open a SPARK (a raw idea) into distinct POSSIBLE DIRECTIONS, using ONLY the "
    "given VERIFIED claims. Rules: (1) each possibility 'statement' is ONE direction the "
    "spark could take — a rough idea, never a full spec; (2) 'mechanism' names the real "
    "mechanism or precedent it leans on; (3) reference each anchor by its EXACT claim id; "
    "(4) every possibility needs >=1 grounding id from the list — never invent a direction "
    "you cannot tie to a claim id; (5) LANGUAGE: write 'statement' and 'mechanism' in "
    "GERMAN (the reader is German-speaking) — keep technical terms, proper nouns and claim "
    "ids exactly as given; (6) if nothing can be grounded, return an empty array (honest "
    "abstention beats invention). "
    'Return JSON: [{"statement":"...","mechanism":"...","grounding":["id",...]}].'
)


def possibility_id(spark_id: str, statement: str, grounding: list[str], mechanism: str | None = None) -> str:
    """Deterministic id from (spark, statement, grounding, mechanism) — includes secondary
    (D13(a)) so approaches/poss differing only in mechanism/tradeoffs no longer collide+drop."""
    key = statement + "|" + "|".join(sorted(grounding))
    if mechanism:
        key += "|m:" + mechanism.strip()
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{spark_id}:poss:{digest}"


def _as_str_list(v: object) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()]


class Forge:
    """Satisfies the ``Agent`` Protocol. Writes only ``state.divergence``.

    Produces no facts of its own; every possibility is anchored in existing VERIFIED
    claims and the divergence is always a declared grounded sample. Rebuilds
    ``state.divergence`` from scratch on each call, so it is idempotent across the
    conductor's refine rounds (same discipline as ``synthesizer``).
    D13 notes (low): secondary (mech) in id; grounding deduped; cap; non-dict note only.
    """

    name = "forge"

    def __init__(self, llm: LLMClient, *, confidence_threshold: float = 0.7) -> None:
        self._llm = llm
        self._tau = confidence_threshold

    async def run(self, state: RunState) -> RunState:
        spark = state.spark
        if spark is None:
            state.log.append("forge: no spark in state -> no divergence (skip)")
            state.divergence = None
            return state

        verified = {
            c.id: c
            for c in state.claims
            if c.status is ClaimStatus.VERIFIED and c.confidence >= self._tau
        }
        # rebuild each round (idempotent); always a declared grounded sample
        state.divergence = Divergence(spark=spark, possibilities=[], grounded_sample=True)
        if not verified:
            state.log.append("forge: no VERIFIED claims -> no possibility (abstain)")
            return state

        try:
            proposed = await self._open(spark.raw, verified)
        except LLMOutputError as exc:
            state.log.append(f"forge: unparseable LLM output -> abstain: {exc}")
            return state

        # D13: cap + grounding dedup before id/emit
        proposed = proposed[:_MAX_POSSIBILITIES]
        seen: set[str] = set()
        for item in proposed:
            statement = str(item.get("statement") or "").strip()
            mechanism = str(item.get("mechanism") or "").strip()
            # Validate every cited id against the VERIFIED set. The model cannot invent
            # grounding: ids that are absent or not VERIFIED are dropped here.
            raw_g = _as_str_list(item.get("grounding"))
            grounding: list[str] = []
            for cid in raw_g:
                if cid in verified and cid not in grounding:
                    grounding.append(cid)
            if not statement or not mechanism or not grounding:
                state.log.append(
                    f"forge: drop possibility {statement!r} (no verified grounding)"
                )
                continue
            pid = possibility_id(spark.id, statement, grounding, mechanism)
            if pid in seen:
                state.log.append(f"forge: drop duplicate possibility {statement!r}")
                continue
            seen.add(pid)
            state.divergence.possibilities.append(
                Possibility(
                    id=pid,
                    statement=statement,
                    mechanism=mechanism,
                    grounding=grounding,
                    produced_by=self.name,
                    model=self._llm.model,
                )
            )
        if not state.divergence.possibilities:
            state.log.append("forge: no possibility survived grounding validation (abstain)")
        return state

    async def _open(self, spark_raw: str, verified: dict) -> list[dict]:
        # Sort by claim id so the prompt is byte-identical for the same verified set,
        # independent of state.claims insertion order (reproducibility — CLAUDE.md §5).
        claim_lines = "\n".join(f"{cid}: {c.text}" for cid, c in sorted(verified.items()))
        user = f"SPARK:\n{spark_raw}\n\nVERIFIED CLAIMS:\n{claim_lines}"
        resp = await self._llm.complete(system=_SYSTEM, user=user)
        value = extract_json(resp.text, agent="forge")
        if not isinstance(value, list):
            raise LLMOutputError("forge", "expected a JSON array of possibilities")
        # D13(d): non-dict filtered (stateless _open); count-log omitted per honest note.
        return [v for v in value if isinstance(v, dict)]
