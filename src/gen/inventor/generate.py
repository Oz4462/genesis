"""generate — the concept-level council: a PROPOSER that widens to bold but grounded invention concepts.

The proposer's only job is to WIDEN (INVENTOR §3): from an :class:`InventionBrief` it returns candidate
concepts. It is the non-deterministic, fallible half of the loop — so everything it produces is a PROPOSAL
that the deterministic gate (grounding / novelty / safety, later phases) must still pass. This module is
injectable: the offline default is a ``ScriptedLLM`` (deterministic, no network), and any live council
(Claude/Grok/Ollama via the ``LLMClient`` seam) drops in unchanged.

Two honesty rules enforced here, before grounding even starts:
  * a concept with no grounding ANCHOR is dropped (core ``Possibility`` would refuse it anyway — concept-level
    anti-hallucination), and so is malformed JSON or an empty mechanism/statement;
  * duplicates (by normalized statement) are removed, so a council that repeats itself does not inflate the
    candidate set. A malformed council reply yields an empty list (honest), never a crash or a fabricated concept.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, Sequence

from ..core.errors import GenesisError, LLMOutputError
from ..core.state import Possibility, now_utc
from ..llm.base import LLMClient, ScriptedLLM
from ..llm.parsing import extract_json
from .brief import InventionBrief

_SYSTEM = (
    "You are a concept council for an anti-hallucination invention engine. Propose BOLD but PHYSICALLY "
    "PLAUSIBLE invention concepts for the given field. Each concept MUST cite at least one grounding anchor "
    "(a known principle, prior work, or material). You only PROPOSE; a deterministic gate verifies physics, "
    "novelty, and safety afterwards. Reply ONLY with JSON: "
    '{"concepts":[{"statement":"...","mechanism":"...","grounding":["..."]}]}'
)


def _concept_prompt(brief: InventionBrief) -> str:
    parts = [f"Field: {brief.field}"]
    if brief.goal:
        parts.append(f"Goal: {brief.goal}")
    if brief.constraints:
        parts.append("Hard constraints: " + "; ".join(brief.constraints))
    parts.append(f"Propose up to {brief.max_concepts} distinct concepts, each with a grounding anchor.")
    return "\n".join(parts)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _concepts_from(data: object) -> list[dict]:
    """Accept either a bare list or a ``{"concepts":[...]}`` object; anything else -> no concepts."""
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict) and isinstance(data.get("concepts"), list):
        return [d for d in data["concepts"] if isinstance(d, dict)]
    return []


async def generate_concepts(brief: InventionBrief, client: LLMClient, *,
                            now: Optional[datetime] = None) -> list[Possibility]:
    """Ask the proposer for up to ``brief.max_concepts`` grounded concepts and parse them into
    ``Possibility`` objects. Malformed JSON, an empty statement/mechanism, or a missing grounding anchor are
    SKIPPED (never invented); duplicates by normalized statement are removed. Deterministic given a
    deterministic ``client``. Returns an empty list on an unparseable reply — an honest miss, not a crash."""
    stamp = now or now_utc()
    response = await client.complete(system=_SYSTEM, user=_concept_prompt(brief))
    try:
        data = extract_json(response.text, agent="inventor.council")
    except LLMOutputError:
        return []

    out: list[Possibility] = []
    seen: set[str] = set()
    for item in _concepts_from(data):
        statement = str(item.get("statement", "")).strip()
        mechanism = str(item.get("mechanism", "")).strip()
        grounding = [str(g).strip() for g in (item.get("grounding") or []) if str(g).strip()]
        if not (statement and mechanism and grounding):
            continue  # concept-level honesty: a bold idea with no anchor is junk, not a concept
        key = _normalize(statement)
        if key in seen:
            continue
        seen.add(key)
        try:
            out.append(Possibility(
                id=f"{brief.run_id}-c{len(out) + 1}", statement=statement, mechanism=mechanism,
                grounding=grounding, produced_by="inventor.council", model=response.model, created_at=stamp))
        except GenesisError:
            continue  # core grounding guard is the final backstop; skip, never fabricate
        if len(out) >= brief.max_concepts:
            break
    return out


def scripted_council(concepts: Sequence[dict], *, model: str = "scripted-council") -> ScriptedLLM:
    """The OFFLINE council default: a deterministic ``ScriptedLLM`` whose reply is the JSON for a fixed list
    of concept dicts ``{"statement","mechanism","grounding":[...]}`` — the test/demo backbone. Pass its output
    straight to :func:`generate_concepts`."""
    payload = json.dumps({"concepts": list(concepts)})
    return ScriptedLLM(model, payload)


__all__ = ["generate_concepts", "scripted_council"]
