"""`scholar` — depth: extract atomic, quote-checked facts (PHASE_ALPHA §3.3).

Reads the *actually fetched* text of each candidate and extracts atomic Claims
that answer the question. The decisive anti-hallucination guard lives here and is
CODE, not trust: every claim's supporting quote must appear verbatim in the
fetched source (whitespace-normalized). If it does not, the model invented it and
the claim is dropped. Claims from sources that could not be fetched are never
created.
"""

from __future__ import annotations

import hashlib

from ..core.errors import LLMOutputError
from ..core.interfaces import LedgerStore
from ..core.state import Claim, ClaimStatus, RunState
from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..tools.fetch import WebFetchTool, readable_text

_SYSTEM = (
    "You extract ATOMIC factual claims from a SOURCE TEXT that help answer a "
    "QUESTION. Rules: (1) use ONLY the source text, never outside knowledge; "
    "(2) each claim is a single, independently checkable statement; (3) for each "
    "claim include a quote that is COPIED CHARACTER-FOR-CHARACTER from the source "
    "as one contiguous span — it must be findable with Ctrl+F in the source. Do "
    "NOT paraphrase, reorder, abbreviate, or reconstruct the quote; if you cannot "
    "copy an exact span, omit the claim. (4) if the source has nothing relevant, "
    'return an empty array. Return JSON: [{"text": "...", "quote": "..."}].'
)

# readable_text is re-exported (moved to tools.fetch as a neutral home shared with
# the skeptic); kept importable from here for callers and tests.
__all__ = ["Scholar", "claim_id", "readable_text"]


def _normalize(s: str) -> str:
    return " ".join(s.split()).lower()


def claim_id(run_id: str, source: str, text: str) -> str:
    """Deterministic id from (run, source, text) — stable across identical runs."""
    digest = hashlib.sha1(f"{source}|{text}".encode("utf-8")).hexdigest()[:12]
    return f"{run_id}:{digest}"


class Scholar:
    """Satisfies the ``Agent`` Protocol. Creates ``UNVERIFIED`` claims only."""

    name = "scholar"

    def __init__(
        self,
        fetch: WebFetchTool,
        llm: LLMClient,
        ledger: LedgerStore,
        *,
        max_sources: int = 8,
        min_quote_len: int = 4,
    ) -> None:
        self._fetch = fetch
        self._llm = llm
        self._ledger = ledger
        self._max_sources = max_sources
        self._min_quote_len = min_quote_len

    async def run(self, state: RunState) -> RunState:
        run_id = state.question.run_id
        existing_ids = {c.id for c in state.claims}
        batch: list[Claim] = []
        batch_ids: set[str] = set()

        for cand in state.candidates[: self._max_sources]:
            result = await self._fetch(url=cand.url_or_id)
            if not result.ok or result.content is None:
                state.log.append(
                    f"scholar: skip (fetch not ok) {cand.url_or_id}: {result.reason}"
                )
                continue

            # Clean prose once; the model and the quote guard must see the SAME text.
            content = readable_text(result.content)

            try:
                items = await self._extract(state.question.raw, content)
            except LLMOutputError as exc:
                state.log.append(f"scholar: skip (unparseable LLM) {cand.url_or_id}: {exc}")
                continue

            for item in items:
                text = (item.get("text") or "").strip()
                quote = (item.get("quote") or "").strip()
                if not text or not quote:
                    state.log.append(f"scholar: drop (missing text/quote) from {cand.url_or_id}")
                    continue
                if not self._quote_supported(quote, content):
                    # The model fabricated the quote — refuse the claim outright.
                    state.log.append(
                        f"scholar: DROP hallucinated quote not in source {cand.url_or_id}: {quote[:60]!r}"
                    )
                    continue
                cid = claim_id(run_id, cand.url_or_id, text)
                if cid in existing_ids or cid in batch_ids:
                    continue
                batch_ids.add(cid)
                batch.append(
                    Claim(
                        id=cid,
                        text=text,
                        sources=[result.to_source_ref(span=cand.url_or_id)],
                        quote=quote,
                        status=ClaimStatus.UNVERIFIED,
                        produced_by=self.name,
                        model=self._llm.model,
                    )
                )

        if batch:
            await self._ledger.add_claims(run_id, batch)
            state.claims.extend(batch)
        return state

    def _quote_supported(self, quote: str, content: str) -> bool:
        q = _normalize(quote)
        if len(q) < self._min_quote_len:
            return False  # too short to be meaningful evidence
        return q in _normalize(content)

    async def _extract(self, question: str, content: str) -> list[dict]:
        user = f"QUESTION:\n{question}\n\nSOURCE TEXT:\n{content}"
        resp = await self._llm.complete(system=_SYSTEM, user=user)
        value = extract_json(resp.text, agent="scholar")
        if not isinstance(value, list):
            raise LLMOutputError("scholar", "expected a JSON array of claims")
        return [v for v in value if isinstance(v, dict)]
