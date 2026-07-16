"""Wikidata density discovery backend — independent of GENESIS materials registry.

Wikipedia plain extracts omit infobox density for many elements (Copper 2026-07-14
live α). This backend discovers Wikidata P2054 mass-density for known engineering
materials so scholar can emit an independent UNVERIFIED claim the skeptic can
corroborate against gen-materials:// (or vice versa).
"""

from __future__ import annotations

from ..core.state import SourceCandidate
from .wikidata import MATERIAL_DENSITY_QIDS, WikidataError, density_claims_for_material


class WikidataDensityBackend:
    """Keyless discovery: density questions → Wikidata P2054 candidates."""

    name = "wikidata_density"

    def __init__(self, http_get=None) -> None:
        self._http_get = http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        if limit <= 0:
            return []
        q = (query or "").lower()
        if not any(t in q for t in ("density", "dichte", "kg/m", "g/cm")):
            return []
        out: list[SourceCandidate] = []
        # Match material tokens (longer names first)
        keys = sorted(MATERIAL_DENSITY_QIDS.keys(), key=len, reverse=True)
        seen: set[str] = set()
        for key in keys:
            token = key.lower().replace("_", " ")
            aliases = {token, key.lower()}
            if key == "ALUMINUM":
                aliases |= {"aluminium", "aluminum", "alu"}
            if key == "COPPER":
                aliases |= {"copper", "kupfer", "cu"}
            if key == "STEEL" or key == "MILD_STEEL":
                aliases |= {"steel", "stahl"}
            if key == "IRON":
                aliases |= {"iron", "eisen"}
            if key == "TITANIUM":
                aliases |= {"titanium", "titan", "ti"}
            if not any(a in q for a in aliases):
                continue
            if key in seen:
                continue
            seen.add(key)
            try:
                row = density_claims_for_material(key)
            except WikidataError:
                continue
            if row is None:
                continue
            _text, _quote, url = row
            out.append(
                SourceCandidate(
                    url_or_id=url,
                    title=f"Wikidata density (P2054): {key}",
                    backend=self.name,
                    relevance_note=f"Independent Wikidata mass density for {key}",
                    fetched_ok=False,
                )
            )
            if len(out) >= limit:
                break
        return out


__all__ = ["WikidataDensityBackend"]
