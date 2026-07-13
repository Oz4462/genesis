"""`skeptic` — independent, cross-model verification (PHASE_ALPHA §3.4, skeptic.md).

The heart of GENESIS. For each UNVERIFIED claim it:
  1. enforces the cross-model rule (verifier — and any second judge — must be a
     different family than the generator) — hard failure if violated, never silent;
  2. searches for NEW, independent sources (scholar's sources do not count);
  3. fetches each independent source ONCE, then judges it as supports / contradicts
     / irrelevant using a different-family model. If a second judge is configured,
     it ISSUES ITS OWN judgments on the same evidence with a different model — a
     genuine second opinion, not a relabel of the first;
  4. decides a status conservatively: a credible contradiction -> REFUTED; enough
     independent support -> VERIFIED; otherwise UNSUPPORTED. Never VERIFIED under
     doubt, and cross-model disagreement lowers confidence / forces abstention.

It adds no new facts. It only sets status, confidence and the independent
verification sources on existing claims. The verification sources are the
URL-deduped UNION over ALL judges (primary + second + extra) so the audit trail
shows every judge's evidence (D11); judges must be pairwise different families
among themselves, not only vs. the generator (D12). Best-effort steps (query
reformulation, per-source judging) never crash the run, but every swallowed
LLM/parse error is logged to ``state.log`` (D11 — visible degradation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import reduce
from typing import Sequence

from ..core.errors import SearchBackendError
from ..core.interfaces import LedgerStore, SearchBackend
from ..core.state import ClaimStatus, RunState, SourceRef, SourceSupport
from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..tools.fetch import WebFetchTool, readable_text
from ..verification.consensus import consensus_verdict
from ..verification.cross_model import (
    Judgment,
    assert_different_families,
    assert_pairwise_different_families,
    corroborated_confidence,
    verify_confidence,
)

_SYSTEM = (
    "You are a scientific verifier. Given a CLAIM and an INDEPENDENT SOURCE TEXT, "
    "decide whether the source SUPPORTS, CONTRADICTS, or is IRRELEVANT to the "
    "claim. Use ONLY the source text. Actively look for contradiction. If unsure, "
    'answer irrelevant. Return JSON {"relation":"supports|contradicts|irrelevant",'
    '"confidence":0..1,"reason":"short"}.'
)

_QUERY_SYSTEM = (
    "You generate search queries to find INDEPENDENT evidence that could confirm or "
    "refute a CLAIM. Return ONLY a JSON array of 2-4 short keyword queries (no prose, "
    "no questions). Prefer authoritative phrasings a source would actually use. "
    "When the claim is in German, emit ENGLISH keyword queries (Wikipedia/scholarly "
    "indexes are English-primary)."
)

# Deterministic DE→EN search keywords only (never values). Matched case-insensitively
# against the claim text; combined into short English query phrases for retrieval.
_DE_EN_SEARCH_TERMS: tuple[tuple[str, str], ...] = (
    ("stahl", "steel"),
    ("dichte", "density"),
    ("aluminium", "aluminum"),
    ("aluminum", "aluminum"),
    ("kupfer", "copper"),
    ("eisen", "iron"),
    ("festigkeit", "strength"),
    ("streckgrenze", "yield strength"),
    ("elastizitätsmodul", "young modulus"),
    ("young", "young modulus"),
    ("wärmeleit", "thermal conductivity"),
    ("schmelzpunkt", "melting point"),
)


def _english_search_boosts(claim_text: str) -> list[str]:
    """Fact-free English keyword boosts for DE (or mixed) claim text.

    Returns zero or more short search strings. Never invents numeric values —
    only maps known material/property words so English-indexed backends can
    retrieve corroborating pages for German claim prose.
    """
    low = claim_text.lower()
    en_terms: list[str] = []
    seen: set[str] = set()
    for de, en in _DE_EN_SEARCH_TERMS:
        if de in low and en not in seen:
            seen.add(en)
            en_terms.append(en)
    if not en_terms:
        return []
    boosts = [" ".join(en_terms)]
    if len(en_terms) >= 2:
        # alternate order often ranks better on Wikipedia ("steel density")
        boosts.append(" ".join(reversed(en_terms)))
    return boosts


@dataclass(frozen=True)
class _Verdict:
    relation: str  # 'supports' | 'contradicts' | 'irrelevant'
    confidence: float
    url: str


class Skeptic:
    """Satisfies the ``Agent`` Protocol. Updates claims; creates no facts."""

    name = "skeptic"

    def __init__(
        self,
        backends: Sequence[SearchBackend],
        fetch: WebFetchTool,
        verifier: LLMClient,
        ledger: LedgerStore,
        *,
        generator_model: str = "",
        second_judge: LLMClient | None = None,
        extra_judges: Sequence[LLMClient] = (),
        min_sources_for_verified: int = 2,
        per_query_limit: int = 5,
        max_verify_sources: int = 4,
    ) -> None:
        if not backends:
            raise ValueError("Skeptic needs at least one search backend.")
        self._backends = list(backends)
        self._fetch = fetch
        self._verifier = verifier
        self._second = second_judge
        # Phase 3 wiring: additional independent cross-model judges. With >= 3 total
        # judges the conservative N-judge consensus replaces the 2-judge fold (PoV-3).
        self._extra = list(extra_judges)
        self._ledger = ledger
        self._generator_model = generator_model
        self._min_sources = min_sources_for_verified
        self._per_query_limit = per_query_limit
        self._max_verify_sources = max_verify_sources

    async def run(self, state: RunState) -> RunState:
        # D12: judges must ALSO be pairwise different families among THEMSELVES
        # (verifier != second != extra) — two same-family judges share blind spots
        # and would corroborate as if they were independent opinions. This is a
        # claim-independent configuration error, checked once and loudly.
        judge_models = [self._verifier.model]
        if self._second is not None:
            judge_models.append(self._second.model)
        judge_models.extend(ex.model for ex in self._extra)
        assert_pairwise_different_families(judge_models)

        for claim in state.claims:
            if claim.status is not ClaimStatus.UNVERIFIED:
                continue

            gen_model = claim.model or self._generator_model
            # Cross-model is mandatory and checked up front for every judge: same
            # family is a configuration error, not something to silently work around.
            assert_different_families(gen_model, self._verifier.model)
            if self._second is not None:
                assert_different_families(gen_model, self._second.model)
            for ex in self._extra:
                assert_different_families(gen_model, ex.model)

            scholar_urls = {s.url_or_id for s in claim.sources}
            candidates = await self._independent_candidates(claim.text, scholar_urls, state)

            # Fetch each independent source exactly once; both judges see the same
            # evidence so any disagreement is genuinely model-driven.
            evidence: list[tuple[str, str]] = []
            for cand in candidates[: self._max_verify_sources]:
                result = await self._fetch(url=cand.url_or_id)
                if not result.ok or result.content is None:
                    state.log.append(
                        f"skeptic: skip (fetch not ok) {cand.url_or_id}: {result.reason}"
                    )
                    continue
                # Judge clean prose, not a JSON envelope (same helper the scholar uses).
                evidence.append((cand.url_or_id, readable_text(result.content)))

            verifier_verdicts = [
                await self._judge(self._verifier, claim.text, content, url, state)
                for url, content in evidence
            ]
            primary = self._aggregate(verifier_verdicts, self._verifier.model)
            # Audit trail across ALL judges (D11): collect every verdict so the
            # verification sources are not just the primary verifier's view.
            all_verdicts: list[_Verdict] = list(verifier_verdicts)

            second_judgment = None
            if self._second is not None:
                # A REAL second opinion: the second model judges the same evidence.
                second_verdicts = [
                    await self._judge(self._second, claim.text, content, url, state)
                    for url, content in evidence
                ]
                all_verdicts.extend(second_verdicts)
                second_judgment = self._aggregate(second_verdicts, self._second.model)

            if self._extra:
                # N-judge panel: each extra model judges the same evidence; the
                # conservative weighted consensus decides (PoV-3). Cross-model is
                # re-checked inside consensus_verdict.
                judgments = [primary]
                if second_judgment is not None:
                    judgments.append(second_judgment)
                for ex in self._extra:
                    verdicts = [
                        await self._judge(ex, claim.text, content, url, state)
                        for url, content in evidence
                    ]
                    all_verdicts.extend(verdicts)
                    judgments.append(self._aggregate(verdicts, ex.model))
                cv = consensus_verdict(generator_model=gen_model, judgments=judgments)
                claim.status = cv.status
                claim.confidence = cv.confidence
            else:
                final = verify_confidence(
                    generator_model=gen_model,
                    verifier=primary,
                    second_judge=second_judgment,
                )
                claim.status = final.status
                claim.confidence = final.confidence
            claim.verification = self._verification_refs(all_verdicts)
            await self._ledger.update_claim(claim)
        return state

    # --- internals ------------------------------------------------------------

    async def _independent_candidates(self, claim_text, scholar_urls, state):
        seen: set[str] = set()
        out = []
        for query in await self._check_queries(claim_text, state):
            for backend in self._backends:
                try:
                    cands = await backend.search(query, self._per_query_limit)
                except SearchBackendError as exc:
                    state.log.append(f"skeptic: backend {backend.name!r} failed: {exc}")
                    continue
                for c in cands:
                    if c.url_or_id in scholar_urls:
                        continue  # independence rule: scholar's sources don't count
                    if c.url_or_id in seen:
                        continue
                    seen.add(c.url_or_id)
                    out.append(c)
        return out

    async def _check_queries(self, claim_text: str, state: RunState) -> list[str]:
        # Model-driven reformulation for stronger INDEPENDENT retrieval: the verifier
        # proposes a few keyword queries that could confirm or refute the claim. The
        # verbatim claim is always kept as a baseline, and any failure falls back to
        # it alone — never an empty query, never a fabricated one, and never silent:
        # the swallowed error is logged to state.log (D11). (Recall tuning: verbatim
        # claim text alone often misses corroborating sources.)
        #
        # Additionally: scholar writes claim *text* in German while Wikipedia (and
        # most free backends) index English. A German claim as the only query
        # under-retrieves (live 2026-07-13: density-of-steel stayed UNSUPPORTED
        # until English keyword boosts were added). Deterministic DE→EN term
        # expansion is fact-free (search keywords only, never asserted values).
        queries: list[str] = []
        try:
            resp = await self._verifier.complete(
                system=_QUERY_SYSTEM, user=f"CLAIM:\n{claim_text}"
            )
            parsed = extract_json(resp.text, agent="skeptic")
            if isinstance(parsed, list):
                queries = [str(q).strip() for q in parsed if str(q).strip()][:4]
            else:
                state.log.append(
                    "skeptic: query reformulation returned non-array JSON; "
                    "falling back to verbatim claim text"
                )
        except Exception as exc:  # noqa: BLE001 - reformulation is best-effort, never fatal
            state.log.append(
                f"skeptic: query reformulation failed "
                f"({type(exc).__name__}: {exc}); falling back to verbatim claim text"
            )
            queries = []
        for boost in _english_search_boosts(claim_text):
            if boost not in queries:
                queries.insert(0, boost)
        if claim_text not in queries:
            queries.append(claim_text)
        return queries
    async def _judge(
        self, llm: LLMClient, claim_text: str, content: str, url: str, state: RunState
    ) -> _Verdict:
        user = f"CLAIM:\n{claim_text}\n\nINDEPENDENT SOURCE TEXT:\n{content}"
        try:
            resp = await llm.complete(system=_SYSTEM, user=user)
            value = extract_json(resp.text, agent="skeptic")
            relation = str(value.get("relation", "irrelevant")).lower()  # type: ignore[union-attr]
            if relation not in {"supports", "contradicts", "irrelevant"}:
                relation = "irrelevant"
            conf = float(value.get("confidence", 0.0))  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - never fabricate support on error
            # Degrading to 'irrelevant' is the honest verdict, but the failure
            # itself must stay auditable (D11) — an unlogged judge outage would
            # make an UNSUPPORTED run irreproducible in hindsight.
            state.log.append(
                f"skeptic: judge {llm.model!r} failed on {url} "
                f"({type(exc).__name__}: {exc}); treating source as irrelevant"
            )
            relation, conf = "irrelevant", 0.0
        return _Verdict(relation=relation, confidence=_clamp01(conf), url=url)

    def _aggregate(self, verdicts: list[_Verdict], model: str) -> Judgment:
        supports = [v.confidence for v in verdicts if v.relation == "supports"]
        contradicts = [v.confidence for v in verdicts if v.relation == "contradicts"]
        if contradicts:
            return Judgment(ClaimStatus.REFUTED, max(contradicts), model)
        if len(supports) >= self._min_sources:
            conf = reduce(corroborated_confidence, supports)
            return Judgment(ClaimStatus.VERIFIED, conf, model)
        # Not enough independent corroboration -> honest UNSUPPORTED, never VERIFIED.
        return Judgment(ClaimStatus.UNSUPPORTED, max(supports) if supports else 0.0, model)

    def _verification_refs(self, verdicts: Sequence[_Verdict]) -> list[SourceRef]:
        """Audit refs from ALL judges' verdicts: union, deduped by URL (D11).

        Every non-irrelevant verdict — primary, second AND extra judges — enters
        the audit trail, in first-seen order. Per URL the CONSERVATIVE relation
        wins: if any judge saw a contradiction there, the ref is CONTRADICTS
        (mirroring the REFUTED veto), never papered over by another judge's
        SUPPORTS. Deterministic (A5): same verdicts -> same refs.
        """
        relation_by_url: dict[str, str] = {}
        order: list[str] = []
        for v in verdicts:
            if v.relation == "irrelevant":
                continue
            if v.url not in relation_by_url:
                relation_by_url[v.url] = v.relation
                order.append(v.url)
            elif v.relation == "contradicts":
                relation_by_url[v.url] = "contradicts"
        return [
            SourceRef(
                url_or_id=url,
                retrieved=True,
                support=(
                    SourceSupport.CONTRADICTS
                    if relation_by_url[url] == "contradicts"
                    else SourceSupport.SUPPORTS
                ),
            )
            for url in order
        ]


def _clamp01(x: float) -> float:
    # NaN / ±inf must never escape into a confidence: NaN passes both `< 0` and
    # `> 1` (every NaN comparison is False) and would later slip past a
    # `confidence < tau` gate. A non-finite confidence is no signal -> 0.0. The
    # JSON boundary (llm.parsing) already rejects non-finite literals; this also
    # covers `float("nan")`/`float("inf")` coerced from a quoted "NaN"/"inf".
    if not math.isfinite(x):
        return 0.0
    return 0.0 if x < 0 else 1.0 if x > 1 else x
