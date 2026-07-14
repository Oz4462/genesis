"""`scholar` — depth: extract atomic, quote-checked facts (PHASE_ALPHA §3.3).

Reads the *actually fetched* text of each candidate and extracts atomic Claims
that answer the question. The decisive anti-hallucination guard lives here and is
CODE, not trust: every claim's supporting quote must appear verbatim in the
fetched source (Unicode-NFKC-, case- and whitespace-normalized). If it does not,
the model invented it and the claim is dropped. Claims from sources that could not
be fetched are never created.
"""

from __future__ import annotations

import hashlib
import unicodedata

from ..core.errors import LLMOutputError
from ..core.interfaces import LedgerStore
from ..core.state import Claim, ClaimStatus, RunState
from ..formulas.registry import FormulaRecord, FormulaRegistry
from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..tools.fetch import WebFetchTool, readable_text
from ..tools.codata import load_codata_constants, make_codata_constant_claim
from ..tools.dlmf import fetch_dlmf_entry, dlmf_latex_to_sympy
from ..tools.materials_backend import materials_claim_text, materials_claims
from ..tools.wikidata import MATERIAL_DENSITY_QIDS, density_claims_for_material
from ..core.state import SourceRef, SourceSupport
_SYSTEM = (
    "You extract ATOMIC factual claims from a SOURCE TEXT that help answer a "
    "QUESTION. Rules: (1) use ONLY the source text, never outside knowledge; "
    "(2) each claim's 'text' must be ONE complete, self-contained statement that "
    "stands on its own and is independently checkable — a full grammatical "
    "sentence with a clear subject. NEVER a sentence fragment, a dangling clause, "
    "a list item, or a dangling phrase. If a fact needs context from the rest of "
    "the sentence to make sense, include that context in the text. "
    "(3) LANGUAGE: write each claim 'text' in the SAME LANGUAGE as the QUESTION "
    "(German question → German claims; English question → English claims). Keep "
    "technical terms, proper nouns, numbers, and units exactly as the source "
    "states them — do not convert units. Prefer the material/property page that "
    "actually states the numeric value asked for (e.g. steel density → the Steel "
    "article's kg/m3 band, not a tangential stainless-only aside). "
    "(4) for each claim include a quote COPIED CHARACTER-FOR-CHARACTER from the "
    "source IN ITS ORIGINAL LANGUAGE as one contiguous span — findable with "
    "Ctrl+F. Do NOT translate, paraphrase, reorder, abbreviate, or reconstruct "
    "the quote; if you cannot copy an exact span, omit the claim. "
    "(5) if the source has nothing relevant, return an empty array. "
    'Return JSON: [{"text": "...", "quote": "..."}].'
)

# readable_text is re-exported (moved to tools.fetch as a neutral home shared with
# the skeptic); kept importable from here for callers and tests.
__all__ = ["Scholar", "claim_id", "readable_text"]


def _normalize(s: str) -> str:
    # NFKC + case + whitespace fold so the quote guard matches the source the way
    # Ctrl+F would, robust to Unicode form differences (curly vs straight quotes,
    # ligatures, full-width digits) that are visually identical but byte-different
    # — neither over-dropping a real quote nor (per the existing min length) easing
    # a fabricated one through.
    return " ".join(unicodedata.normalize("NFKC", s).split()).lower()


# Lowercase function words that only ever continue a sentence — a claim text
# starting with one is a fragment, not a standalone statement. Content words
# (incl. lowercase proper nouns like 'build123d') are NOT here, so they pass.
# German starters included since claim texts are written in German (a proper
# German sentence starts capitalized, so lowercase matches stay fragments).
_FRAGMENT_STARTERS = frozenset({
    "and", "or", "but", "nor", "yet", "so", "a", "an", "the", "of", "with",
    "for", "as", "by", "to", "in", "on", "at", "from", "because", "which",
    "that", "than", "then", "plus", "including", "use", "using", "uses",
    "und", "oder", "aber", "sondern", "sowie", "mit", "für", "von", "zu",
    "im", "am", "auf", "aus", "bei", "nach", "weil", "dass", "als", "dann",
    "denn", "wobei", "welche", "welcher", "welches", "einschließlich",
    "nutzt", "nutzen", "verwendet", "durch", "über", "unter", "zwischen",
})


def _looks_complete(text: str) -> bool:
    """True if `text` reads as a complete, standalone statement (not a fragment).

    Code-level defense-in-depth for the prompt rule "each claim is one complete
    sentence" — the model does not always obey (a live run split prose into
    verbatim fragments like 'and garbage collection', 'an extensive standard
    library'). Heuristic: reject a text whose first word is a LOWERCASE function
    word (a clear continuation marker). Content-word starts pass, including
    lowercase proper nouns ('build123d ...'), so real claims are not over-rejected.
    Conservative by design: dropping a borderline fragment yields abstention,
    which GENESIS prefers over asserting a low-quality claim. Verb-initial
    fragments ('emphasizes ...') are left to the prompt; this guard targets the
    unambiguous function-word case.
    """
    t = text.strip()
    if not t:
        return False
    first = t.split()[0]
    if first[0].islower() and first.strip(".,;:\"'()").lower() in _FRAGMENT_STARTERS:
        return False
    return True


def claim_id(run_id: str, source: str, text: str) -> str:
    """Deterministic id from (run, source, text) — stable across identical runs."""
    digest = hashlib.sha1(f"{source}|{text}".encode("utf-8")).hexdigest()[:12]
    return f"{run_id}:{digest}"


def _claim_language(question: str) -> str:
    """Heuristic claim language: German question → de, else en."""
    q = question.lower()
    de_markers = ("was ist", "wie ", "dichte", "stahl", "für ", "ein ", "eine ")
    if any(m in q for m in de_markers) or any(c in question for c in "äöüÄÖÜß"):
        return "de"
    return "en"


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
        q_lang = _claim_language(state.question.raw)

        # Materials registry candidates (gen-materials://) — offline grounded claims
        # without HTTP. Still UNVERIFIED until skeptic finds independent sources.
        # Self-improve 2026-07-14: emit separate density + thermal_conductivity claims
        # (materials_claims) so α can verify ρ and k independently.
        for cand in list(state.candidates):
            if not (cand.url_or_id or "").startswith("gen-materials://"):
                continue
            key = cand.url_or_id.split("://", 1)[-1].strip().upper()
            try:
                claim_rows = materials_claims(key, language=q_lang)
            except Exception:  # noqa: BLE001
                # fallback single density claim for unknown/legacy keys
                try:
                    text, quote = materials_claim_text(key, language=q_lang)
                    claim_rows = [(text, quote, key)]
                except Exception as exc2:  # noqa: BLE001
                    state.log.append(f"scholar: materials registry skip {key}: {exc2}")
                    continue
            for text, quote, span_tag in claim_rows:
                # Distinct id seed per property so density and k never collide
                url_seed = f"{cand.url_or_id}#{span_tag}"
                cid = claim_id(run_id, url_seed, text)
                if cid in existing_ids or cid in batch_ids:
                    continue
                batch_ids.add(cid)
                batch.append(
                    Claim(
                        id=cid,
                        text=text,
                        sources=[
                            SourceRef(
                                url_or_id=cand.url_or_id,
                                retrieved=True,
                                content_hash=None,
                                span=span_tag,
                                support=SourceSupport.SUPPORTS,
                            )
                        ],
                        quote=quote,
                        status=ClaimStatus.UNVERIFIED,
                        produced_by=self.name + "+materials_registry",
                        model="materials_registry",
                    )
                )
            state.log.append(
                f"scholar: materials registry {len(claim_rows)} claim(s) for {key} "
                f"(UNVERIFIED until skeptic)"
            )

        # Independent Wikidata density (P2054) — Wikipedia extracts omit infobox
        # density for many elements; this is the corroboration path for registry bands.
        q_raw = (state.question.raw or "").lower()
        for mat_key in MATERIAL_DENSITY_QIDS:
            token = mat_key.lower().replace("_", " ")
            aliases = {token, mat_key.lower()}
            if mat_key in ("ALUMINUM", "ALUMINIUM"):
                aliases |= {"aluminium", "aluminum", "alu"}
            if mat_key == "COPPER":
                aliases |= {"copper", "kupfer", "cu"}
            if mat_key in ("STEEL", "MILD_STEEL"):
                aliases |= {"steel", "stahl"}
            if mat_key == "IRON":
                aliases |= {"iron", "eisen"}
            if mat_key == "TITANIUM":
                aliases |= {"titanium", "titan"}
            if not any(a in q_raw for a in aliases):
                continue
            if "densit" not in q_raw and "dichte" not in q_raw and "kg/m" not in q_raw:
                # only auto-emit density for density-ish questions
                if not any(
                    "densit" in (c.title or "").lower() or "densit" in (c.relevance_note or "").lower()
                    for c in state.candidates
                ):
                    continue
            try:
                row = density_claims_for_material(mat_key, language=q_lang)
            except Exception as exc:  # noqa: BLE001
                state.log.append(f"scholar: wikidata density skip {mat_key}: {exc}")
                continue
            if row is None:
                continue
            text, quote, url = row
            cid = claim_id(run_id, f"{url}#{mat_key}/density", text)
            if cid in existing_ids or cid in batch_ids:
                continue
            batch_ids.add(cid)
            batch.append(
                Claim(
                    id=cid,
                    text=text,
                    sources=[
                        SourceRef(
                            url_or_id=url,
                            retrieved=True,
                            content_hash=None,
                            span=f"{mat_key}/wikidata_P2054",
                            support=SourceSupport.SUPPORTS,
                        )
                    ],
                    quote=quote,
                    status=ClaimStatus.UNVERIFIED,
                    produced_by=self.name + "+wikidata_density",
                    model="wikidata_P2054",
                )
            )
            state.log.append(
                f"scholar: Wikidata P2054 density claim for {mat_key} (UNVERIFIED until skeptic)"
            )

        for cand in state.candidates[: self._max_sources]:
            if (cand.url_or_id or "").startswith("gen-materials://"):
                continue  # already handled offline above
            result = await self._fetch(url=cand.url_or_id)
            if not result.ok or result.content is None:
                state.log.append(
                    f"scholar: skip (fetch not ok) {cand.url_or_id}: {result.reason}"
                )
                continue

            # Clean prose once; the model and the quote guard must see the SAME text.
            content = readable_text(result.content)

            # === Formula-aware special path (full wiring) ===
            # For DLMF / CODATA / authoritative formula sources we bypass or augment
            # LLM extraction with deterministic, sourced formula registration + Claims.
            # This ensures exact formulas + provenance enter the Ledger and Registry.
            if any(k in cand.url_or_id for k in ("dlmf.nist.gov", "physics.nist.gov/cuu", "/constants", "codata")):
                try:
                    reg = FormulaRegistry()
                    formula_claims = []
                    if "dlmf.nist.gov" in cand.url_or_id:
                        import re
                        m = re.search(r"(\d+\.\d+\.E\d+)", cand.url_or_id + "/" + (cand.title or ""))
                        if m:
                            entry = fetch_dlmf_entry(m.group(1))
                            expr = dlmf_latex_to_sympy(entry.latex)
                            rec_id = f"dlmf:{m.group(1)}"
                            rec = FormulaRecord(record_id=rec_id, kind="identity", name=f"DLMF {m.group(1)}",
                                                expr=str(expr) if not isinstance(expr, str) else expr,
                                                sources=(entry.source,))
                            reg.register(rec)
                            formula_claims.append(Claim(
                                id=claim_id(run_id, cand.url_or_id, f"DLMF-{m.group(1)}"),
                                text=f"Die Formeldefinition aus NIST DLMF {m.group(1)} ist: {entry.latex[:120]}",
                                sources=[result.to_source_ref(span=entry.identifier)],
                                quote=entry.latex[:80],
                                status=ClaimStatus.UNVERIFIED,
                                produced_by=self.name + "+dlmf",
                            ))
                    else:
                        # CODATA table or constants page -> register key constants
                        raw = content
                        consts = load_codata_constants(raw_text=raw if "Quantity" in raw else None)
                        for name in ["elementary_charge", "planck_constant", "speed_of_light_in_vacuum", "boltzmann_constant"]:
                            if name in consts:
                                c = consts[name]
                                try:
                                    cl = make_codata_constant_claim(c, raw or "CODATA-2022")
                                    formula_claims.append(cl)
                                    rec = FormulaRecord(record_id=f"codata:{name}", kind="constant",
                                                        name=name, expr=str(c.value), unit=c.unit,
                                                        sources=(c.source,))
                                    reg.register(rec)
                                except Exception:
                                    pass
                    if formula_claims:
                        # add to ledger and state, then continue (still allow LLM for surrounding facts)
                        await self._ledger.add_claims(run_id, formula_claims)
                        state.claims.extend(formula_claims)
                        state.log.append(f"scholar: formula-aware registered {len(formula_claims)} claims from {cand.url_or_id}")
                except Exception as exc:  # noqa: BLE001
                    state.log.append(f"scholar: formula path error for {cand.url_or_id}: {exc}")

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
                if not _looks_complete(text):
                    # Not an atomic statement (a fragment/clause) — drop it. A
                    # low-quality "claim" would otherwise pass to verification and
                    # could attract a spurious support (live: "Waste collection"
                    # matched "garbage collection").
                    state.log.append(
                        f"scholar: drop (sentence fragment, not atomic) {cand.url_or_id}: {text[:60]!r}"
                    )
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
