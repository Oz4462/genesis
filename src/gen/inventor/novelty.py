"""novelty — the second axis of honesty: measured distance to prior art, never an LLM's opinion.

Validity is a hard gate (the δ-physics flow); NOVELTY is a measured distance to REAL prior art (INVENTOR §12):
the concept is embedded and compared to what the prior-art connectors (OpenAlex literature + PatentsView
patents) actually return, and the verdict is a function of that distance plus the nearest-prior-art evidence —
not a model saying "this is new". Three honest stages, with the owner's bar (a NEW MECHANISM counts as novel):

  * ``nicht_neu``         — a near-duplicate of retrieved prior art (distance below the duplicate threshold).
  * ``neuer_mechanismus`` — the same problem area, but a DIFFERENT mechanism (goal close, mechanism far).
  * ``neu``               — far from all retrieved prior art (or none was found — an honest, evidenced "neu").

HONEST BOUNDARY: the offline default embedding is character-n-gram (lexical) — it catches near-VERBATIM
duplicates, not deep semantic ones. A dense embedder (Ollama) is the opt-in upgrade injected via ``embed``; the
verdict always carries the embedder used and the nearest prior-art id so the basis is auditable. Deterministic
given the connectors and embedder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import numpy as np

from ..core.interfaces import SearchBackend
from ..core.state import Possibility, SourceCandidate
from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..tools.rag_backend import char_ngram_embed

Embed = Callable[[str], np.ndarray]

NICHT_NEU = "nicht_neu"
NEUER_MECHANISMUS = "neuer_mechanismus"
NEU = "neu"


@dataclass(frozen=True)
class NoveltyVerdict:
    """The measured novelty verdict + its evidence. ``distance`` is the nearest retrieved prior-art distance
    (lower = more similar); ``nearest_prior_art`` / ``nearest_title`` are that evidence; ``checked_sources``
    are all prior-art ids compared; ``embedder`` records the basis (lexical vs dense)."""

    verdict: str
    distance: float
    nearest_prior_art: Optional[str]
    nearest_title: Optional[str]
    checked_sources: tuple[str, ...]
    embedder: str

    @property
    def is_novel(self) -> bool:
        """The owner bar: a new mechanism counts as novel, so anything that is not ``nicht_neu`` is novel."""
        return self.verdict != NICHT_NEU


def _cos_dist(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
    return 1.0 - float(np.dot(a, b) / denom)


def _text(candidate: SourceCandidate) -> str:
    return f"{candidate.title or ''} {candidate.relevance_note}".strip()


async def assess_novelty(
    concept: Possibility,
    backends: Sequence[SearchBackend],
    *,
    embed: Embed = char_ngram_embed,
    limit: int = 5,
    duplicate_threshold: float = 0.25,
    goal_threshold: float = 0.6,
) -> NoveltyVerdict:
    """Measure ``concept``'s distance to the prior art the ``backends`` return and classify it. A backend that
    errors is skipped (a failed search never fabricates novelty). If NO prior art is retrieved, the verdict is
    ``neu`` with distance 1.0 and no evidence — honest, not a hidden assumption. The embedder is injectable
    (offline char-n-gram default; dense Ollama opt-in)."""
    query = f"{concept.statement} {concept.mechanism}".strip()
    candidates: list[SourceCandidate] = []
    for backend in backends:
        try:
            candidates.extend(await backend.search(query, limit))
        except Exception:
            continue

    embedder_name = getattr(embed, "__name__", "embed")
    if not candidates:
        return NoveltyVerdict(NEU, 1.0, None, None, (), embedder_name)

    full_vec = embed(query)
    nearest: Optional[SourceCandidate] = None
    best = 2.0
    for candidate in candidates:
        d = _cos_dist(full_vec, embed(_text(candidate)))
        if d < best:
            best, nearest = d, candidate

    if best <= duplicate_threshold:
        verdict = NICHT_NEU
    else:
        near_text = _text(nearest) if nearest else ""
        goal_dist = _cos_dist(embed(concept.statement), embed(near_text))
        mech_dist = _cos_dist(embed(concept.mechanism), embed(near_text))
        verdict = NEUER_MECHANISMUS if (goal_dist <= goal_threshold and mech_dist > goal_threshold) else NEU

    return NoveltyVerdict(
        verdict=verdict, distance=best,
        nearest_prior_art=nearest.url_or_id if nearest else None,
        nearest_title=nearest.title if nearest else None,
        checked_sources=tuple(c.url_or_id for c in candidates), embedder=embedder_name)


_OBVIOUS_SYSTEM = (
    "You judge whether an invention concept is OBVIOUS to a domain expert (a trivial combination of known "
    'art). Reply ONLY with JSON: {"obvious": true|false, "reason": "..."}.'
)


async def obviousness_flag(concept: Possibility, judges: Sequence[LLMClient]) -> bool:
    """Cross-model obviousness check (TN2): ask each injectable judge whether the concept is obvious; flag it
    only if EVERY judge says obvious (a single dissent clears it). A judge whose reply does not parse is
    treated as 'not obvious' (it does not get to flag by failing). Returns True = flagged obvious."""
    if not judges:
        return False
    user = f"Concept: {concept.statement}\nMechanism: {concept.mechanism}"
    for judge in judges:
        response = await judge.complete(system=_OBVIOUS_SYSTEM, user=user)
        try:
            data = extract_json(response.text, agent="inventor.obviousness")
        except Exception:
            return False
        if not (isinstance(data, dict) and data.get("obvious") is True):
            return False
    return True


def build_novelty_gate(
    backends: Sequence[SearchBackend],
    *,
    embed: Embed = char_ngram_embed,
    limit: int = 5,
    duplicate_threshold: float = 0.25,
    goal_threshold: float = 0.6,
):
    """A per-concept novelty gate the loop runs BEFORE grounding (TN3): returns an async
    ``concept -> NoveltyVerdict`` bound to these ``backends``/``embed``. A ``nicht_neu`` concept is then never
    grounded — known prior art does not consume the gate's budget."""
    async def gate(concept: Possibility) -> NoveltyVerdict:
        return await assess_novelty(concept, backends, embed=embed, limit=limit,
                                    duplicate_threshold=duplicate_threshold, goal_threshold=goal_threshold)
    return gate


__all__ = ["NoveltyVerdict", "assess_novelty", "obviousness_flag", "build_novelty_gate",
           "NICHT_NEU", "NEUER_MECHANISMUS", "NEU"]
