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
# Longer phrases first so "stainless steel" wins over bare "steel".
_DE_EN_SEARCH_TERMS: tuple[tuple[str, str], ...] = (
    ("edelstahl", "stainless steel"),
    ("rostfreier stahl", "stainless steel"),
    ("stainless steel", "stainless steel"),
    ("carbon steel", "carbon steel"),
    ("baustahl", "structural steel"),
    ("stahl", "steel"),
    ("steel", "steel"),
    ("dichte", "density"),
    ("density", "density"),
    ("aluminium", "aluminum"),
    ("aluminum", "aluminum"),
    ("kupfer", "copper"),
    ("copper", "copper"),
    ("eisen", "iron"),
    ("iron", "iron"),
    ("festigkeit", "strength"),
    ("streckgrenze", "yield strength"),
    ("yield strength", "yield strength"),
    ("elastizitätsmodul", "young modulus"),
    ("young", "young modulus"),
    ("wärmeleit", "thermal conductivity"),
    ("schmelzpunkt", "melting point"),
)

# Cap judge evidence: full Wikipedia extracts (~30k) blow CLI LLM argv/timeouts and
# produced conf=0 (judge exception → irrelevant). Window around claim keywords.
_JUDGE_MAX_CHARS = 6_000
_JUDGE_WINDOW = 900


def _english_search_boosts(claim_text: str) -> list[str]:
    """Fact-free English keyword boosts for DE (or mixed) claim text.

    Returns zero or more short search strings. Never invents numeric values —
    only maps known material/property words so English-indexed backends can
    retrieve corroborating pages for German *or* English claim prose.
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
    # Multi-word materials get a dedicated density query when density is present
    if "density" in en_terms:
        for mat in en_terms:
            if mat != "density" and " " in mat:
                boosts.insert(0, f"{mat} density")
    return boosts


def _evidence_for_judge(claim_text: str, content: str) -> str:
    """Return a bounded evidence window for the judge LLM.

    Full MediaWiki extracts are large; sending them whole caused live judge
    timeouts / transport failures that silently degraded to ``irrelevant``
    (conf=0). Prefer slices centered on shared keywords; fall back to a head
    truncate. Never invents text — only selects substrings of ``content``.
    """
    if not content:
        return content
    if len(content) <= _JUDGE_MAX_CHARS:
        return content
    low_c = content.lower()
    # Keywords from claim (length ≥ 4) plus known EN material/property terms
    raw_tokens = [t.strip(".,;:()[]\"'") for t in claim_text.split()]
    keys: list[str] = []
    for t in raw_tokens:
        if len(t) >= 4:
            keys.append(t.lower())
    for _de, en in _DE_EN_SEARCH_TERMS:
        if en in claim_text.lower() or any(p in claim_text.lower() for p in en.split()):
            keys.append(en.lower())
    # de-dupe preserving order
    seen_k: set[str] = set()
    ordered_keys: list[str] = []
    for k in keys:
        if k not in seen_k:
            seen_k.add(k)
            ordered_keys.append(k)

    spans: list[tuple[int, int]] = []
    for k in ordered_keys[:12]:
        start = 0
        hits = 0
        while hits < 3:
            i = low_c.find(k, start)
            if i < 0:
                break
            lo = max(0, i - _JUDGE_WINDOW // 3)
            hi = min(len(content), i + len(k) + (2 * _JUDGE_WINDOW // 3))
            spans.append((lo, hi))
            start = i + len(k)
            hits += 1
    if not spans:
        return content[:_JUDGE_MAX_CHARS]

    # Merge overlapping spans
    spans.sort()
    merged: list[list[int]] = [list(spans[0])]
    for lo, hi in spans[1:]:
        if lo <= merged[-1][1] + 40:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    parts = [content[lo:hi] for lo, hi in merged]
    joined = "\n…\n".join(parts)
    if len(joined) > _JUDGE_MAX_CHARS:
        return joined[:_JUDGE_MAX_CHARS]
    return joined

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

            # Registry density + Wikidata P2054: two independent handbook sources.
            # Wikipedia plain extracts often omit infobox density (Copper 2026-07-14),
            # so LLM judges never see the number. When registry and Wikidata agree
            # within 2%, accept as VERIFIED with explicit Wikidata verification ref.
            if await self._try_registry_wikidata_density(claim, state):
                await self._ledger.update_claim(claim)
                continue

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

    async def _try_registry_wikidata_density(self, claim, state: RunState) -> bool:
        """If claim is registry density and Wikidata P2054 agrees within 2%, VERIFIED.

        Returns True when the claim was decided here (caller should skip LLM judges).
        """
        import re

        from ..tools.wikidata import MATERIAL_DENSITY_QIDS, density_claims_for_material

        prod = claim.produced_by or ""
        if "materials_registry" not in prod:
            return False
        text_l = (claim.text or "").lower()
        if "densit" not in text_l and "dichte" not in text_l:
            return False
        # Extract kg/m³ from claim
        m = re.search(r"(\d+(?:\.\d+)?)\s*kg\s*/\s*m", claim.text or "", re.I)
        if not m:
            return False
        rho_claim = float(m.group(1))
        # Which material?
        mat_key = None
        for key in MATERIAL_DENSITY_QIDS:
            token = key.lower().replace("_", " ")
            if token in text_l or key.lower() in text_l:
                mat_key = key
                break
            if key == "COPPER" and ("copper" in text_l or "kupfer" in text_l):
                mat_key = key
                break
            if key in ("ALUMINUM", "ALUMINIUM") and (
                "aluminum" in text_l or "aluminium" in text_l
            ):
                mat_key = key
                break
            if key in ("STEEL", "MILD_STEEL") and ("steel" in text_l or "stahl" in text_l):
                mat_key = key
                break
        if mat_key is None:
            return False
        try:
            row = density_claims_for_material(mat_key)
        except Exception as exc:  # noqa: BLE001
            state.log.append(f"skeptic: wikidata density check failed: {exc}")
            return False
        if row is None:
            return False
        wd_text, wd_quote, wd_url = row
        m2 = re.search(r"(\d+(?:\.\d+)?)\s*kg\s*/\s*m", wd_text, re.I)
        if not m2:
            return False
        rho_wd = float(m2.group(1))
        if rho_wd <= 0:
            return False
        rel = abs(rho_claim - rho_wd) / rho_wd
        if rel > 0.02:  # >2% disagreement — leave to normal judges
            state.log.append(
                f"skeptic: registry density {rho_claim} vs Wikidata {rho_wd} "
                f"({rel:.1%}) > 2% — no auto-verify"
            )
            return False
        claim.status = ClaimStatus.VERIFIED
        claim.confidence = max(0.8, min(0.95, 0.95 - rel * 5))
        claim.verification = [
            SourceRef(
                url_or_id=wd_url,
                retrieved=True,
                content_hash=None,
                span=wd_quote[:80],
                support=SourceSupport.SUPPORTS,
            )
        ]
        state.log.append(
            f"skeptic: VERIFIED materials density via Wikidata P2054 "
            f"({rho_claim:.0f} vs {rho_wd:.0f} kg/m³, {rel:.2%} rel)"
        )
        return True

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
        boosts = _english_search_boosts(claim_text)
        # When deterministic EN boosts already give strong retrieval keywords
        # (material/property claims), skip the expensive reformulation LLM call —
        # live α spent minutes here and still timed out outer 900s budgets.
        if not boosts:
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
        else:
            state.log.append(
                f"skeptic: using deterministic EN search boosts {boosts!r} "
                "(skip LLM reformulation)"
            )
        for boost in boosts:
            if boost not in queries:
                queries.insert(0, boost)
        if claim_text not in queries:
            queries.append(claim_text)
        return queries
    async def _judge(
        self, llm: LLMClient, claim_text: str, content: str, url: str, state: RunState
    ) -> _Verdict:
        evidence = _evidence_for_judge(claim_text, content)
        if len(content) > _JUDGE_MAX_CHARS and len(evidence) < len(content):
            state.log.append(
                f"skeptic: judge evidence windowed {len(content)}→{len(evidence)} chars for {url}"
            )
        user = f"CLAIM:\n{claim_text}\n\nINDEPENDENT SOURCE TEXT:\n{evidence}"
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
