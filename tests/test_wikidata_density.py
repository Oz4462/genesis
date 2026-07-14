"""Wikidata P2054 density — independent of materials registry (network, keyless)."""

from __future__ import annotations

import asyncio
import math

from gen.tools.wikidata import (
    MATERIAL_DENSITY_QIDS,
    density_claims_for_material,
    get_density_kg_m3,
)
from gen.tools.wikidata_density_backend import WikidataDensityBackend


def test_wikidata_copper_density_near_handbook():
    hit = get_density_kg_m3("Q753")
    assert hit is not None
    # Wikidata ~8.94 g/cm³ → ~8940 kg/m³ (near registry 8960)
    assert 8800.0 <= hit.density_kg_m3 <= 9100.0
    assert math.isclose(hit.density_g_cm3 * 1000.0, hit.density_kg_m3, rel_tol=1e-9)


def test_density_claim_text_for_copper():
    row = density_claims_for_material("COPPER")
    assert row is not None
    text, quote, url = row
    assert "kg/m" in text or "kg/m³" in text
    assert "Q753" in text or "Q753" in url
    assert "P2054" in quote or "P2054" in text
    assert url.startswith("https://www.wikidata.org/")


def test_wikidata_density_backend_surfaces_copper():
    be = WikidataDensityBackend()
    hits = asyncio.run(be.search("What is the density of copper in kg/m3?", 3))
    assert hits
    assert any("Q753" in h.url_or_id or "copper" in h.title.lower() for h in hits)


def test_backend_silent_without_density_keyword():
    be = WikidataDensityBackend()
    assert asyncio.run(be.search("copper alloys in aerospace", 5)) == []


def test_material_qid_map_covers_core_metals():
    for key in ("COPPER", "ALUMINUM", "STEEL", "IRON"):
        assert key in MATERIAL_DENSITY_QIDS


def test_skeptic_auto_verifies_registry_density_against_wikidata():
    """Registry density + Wikidata P2054 within 2% → VERIFIED without LLM judges."""
    from gen.agents.skeptic import Skeptic
    from gen.core.state import Claim, ClaimStatus, Question, RunState, SourceRef, SourceSupport
    from gen.ledger.store import InMemoryLedgerStore
    from gen.llm.base import ScriptedLLM
    from gen.tools.fetch import FetchResult

    class Dummy:
        name = "dummy"

        async def search(self, q, limit):
            return []

    async def fake_fetch(**kwargs):
        return FetchResult(ok=False, content=None, reason="unused")

    claim = Claim(
        id="c1",
        text=(
            "The nominal density of COPPER in the GENESIS materials registry is "
            "8960 kg/m³ (8.96 g/cm³); source: registry entry."
        ),
        sources=[
            SourceRef(
                url_or_id="gen-materials://COPPER",
                retrieved=True,
                support=SourceSupport.SUPPORTS,
            )
        ],
        quote="nominal pure copper",
        status=ClaimStatus.UNVERIFIED,
        produced_by="scholar+materials_registry",
        model="materials_registry",
    )
    state = RunState(question=Question(raw="density of copper", run_id="t"))
    state.claims = [claim]
    sk = Skeptic(
        backends=[Dummy()],
        fetch=fake_fetch,
        verifier=ScriptedLLM("claude-fake", '{"relation":"irrelevant","confidence":0}'),
        ledger=InMemoryLedgerStore(),
        generator_model="materials_registry",
        min_sources_for_verified=1,
    )
    ok = asyncio.run(sk._try_registry_wikidata_density(claim, state))
    assert ok is True
    assert claim.status is ClaimStatus.VERIFIED
    assert claim.confidence >= 0.8
    assert claim.verification and "wikidata.org" in claim.verification[0].url_or_id
