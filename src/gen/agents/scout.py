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
from ..core.state import RunState, SourceCandidate, SubQuestion
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
            for query in await self._queries(sq.text):
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

    async def _queries(self, focus: str) -> list[str]:
        """Return search queries for a focus. LLM is optional and fact-free."""
        if self._llm is None:
            return [focus]
        system = (
            "You produce concise web/academic SEARCH QUERIES (not answers, not "
            "facts) for a research question. Return a JSON array of short query "
            "strings, most important first."
        )
        try:
            resp = await self._llm.complete(system=system, user=focus)
            value = extract_json(resp.text, agent="scout")
            queries = [str(q).strip() for q in value if str(q).strip()]  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 - query gen is best-effort, never fatal
            return [focus]
        queries = queries[: self._max_queries] if queries else [focus]
        return queries
