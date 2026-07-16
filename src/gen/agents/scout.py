"""`scout` — breadth-first source discovery (PHASE_ALPHA §3.2).

Finds candidate sources for each sub-question across the configured search
backends. It produces NO facts and invents NO sources: every candidate comes
from a backend response. A failing backend degrades visibly (logged) instead of
silently returning nothing or fabricating results.
"""

from __future__ import annotations

from typing import Sequence

from ..core.errors import SearchBackendError
from ..core.interfaces import SearchBackend
from ..core.state import RunState, SubQuestion
from ..llm.base import LLMClient
from ..llm.parsing import extract_json


class Scout:
    """Satisfies the ``Agent`` Protocol. Writes only ``state.candidates``."""

    name = "scout"

    def __init__(
        self,
        backends: Sequence[SearchBackend],
        *,
        llm: LLMClient | None = None,
        per_query_limit: int = 5,
        max_queries: int = 3,
    ) -> None:
        if not backends:
            raise ValueError("Scout needs at least one search backend.")
        self._backends = list(backends)
        self._llm = llm
        self._per_query_limit = per_query_limit
        self._max_queries = max_queries

    async def run(self, state: RunState) -> RunState:
        focuses = state.sub_questions or [
            SubQuestion(
                id=f"{state.question.run_id}-q0",
                text=state.question.raw,
                parent_run_id=state.question.run_id,
            )
        ]
        seen = {c.url_or_id for c in state.candidates}
        for sq in focuses:
            for query in await self._queries(sq.text, state):
                for backend in self._backends:
                    try:
                        candidates = await backend.search(query, self._per_query_limit)
                    except SearchBackendError as exc:
                        state.log.append(
                            f"scout: backend {backend.name!r} failed for {query!r}: {exc}"
                        )
                        continue
                    for cand in candidates:
                        if cand.url_or_id not in seen:
                            seen.add(cand.url_or_id)
                            state.candidates.append(cand)
        return state

    async def _queries(self, focus: str, state: RunState) -> list[str]:
        """Return search queries for a focus. LLM is optional and fact-free.

        The focus text is ALWAYS the first query: it is the highest-precision
        discovery signal and (after per-backend normalization, e.g. Wikipedia's
        keyword form) the most likely to surface the directly relevant source.
        LLM-elaborated queries are added after it for breadth, deduped, and
        capped at ``max_queries`` — so an off-target elaboration can never crowd
        out the direct query.

        Query generation is best-effort and never fatal, but every degradation
        (LLM/parse error, non-array reply) is logged to ``state.log`` so a
        breadth-poor run stays reproducible/diagnosable (D11) instead of
        failing silently.
        """
        queries = [focus]
        if self._llm is None:
            return queries
        system = (
            "You produce short keyword SEARCH QUERIES (not answers, not facts, "
            "not full sentences) for a research question — the way you would type "
            "into a search box. Return a JSON array of short query strings, most "
            "important first."
        )
        try:
            resp = await self._llm.complete(system=system, user=focus)
            value = extract_json(resp.text, agent="scout")
        except Exception as exc:
            state.log.append(
                f"scout: query generation failed for {focus!r} "
                f"({type(exc).__name__}: {exc}); using focus query only"
            )
            return queries
        if not isinstance(value, list):
            # An object reply would iterate its KEYS ('queries', ...) as bogus
            # queries; only a JSON array is a query list. Keep focus alone —
            # same array-shape discipline as scholar._extract / skeptic._check_queries.
            state.log.append(
                f"scout: query generation returned non-array JSON for {focus!r}; "
                "using focus query only"
            )
            return queries
        extra = [str(q).strip() for q in value if str(q).strip()]
        for q in extra[: self._max_queries]:
            if q != focus and q not in queries:
                queries.append(q)
        return queries
