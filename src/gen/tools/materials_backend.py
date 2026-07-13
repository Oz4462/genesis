"""Materials registry search backend — discovery of grounded handbook materials.

Self-improve loop 2026-07-13: live α density questions needed a second, offline
provenance path alongside Wikipedia. This backend does DISCOVERY only: it returns
``SourceCandidate``s whose ``url_or_id`` is a stable ``gen-materials://`` token
that the scholar's materials path turns into UNVERIFIED claims with registry
provenance. It never invents numeric values outside ``materials.MATERIALS``.
"""

from __future__ import annotations

import re

from ..core.state import SourceCandidate
from ..materials import MATERIALS


class MaterialsBackend:
    """Keyless offline discovery over the grounded materials registry."""

    name = "materials_registry"

    # Query tokens → registry key (longer phrases first)
    _ALIASES: tuple[tuple[str, str], ...] = (
        ("stainless steel", "STEEL"),  # orient toward steel; alloy nuance in note
        ("carbon steel", "STEEL"),
        ("structural steel", "STEEL"),
        ("mild steel", "MILD_STEEL"),
        ("aluminium", "ALUMINIUM"),
        ("aluminum", "ALUMINUM"),
        ("titanium", "TITANIUM"),
        ("titan", "TITANIUM"),
        ("copper", "COPPER"),
        ("kupfer", "COPPER"),
        ("steel", "STEEL"),
        ("stahl", "STEEL"),
        ("pla", "PLA"),
        ("petg", "PETG"),
        ("abs", "ABS"),
    )

    def __init__(self, http_get=None) -> None:  # noqa: ANN001 — protocol compat
        self._http_get = http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        if limit <= 0:
            return []
        q = (query or "").lower()
        if not q.strip():
            return []
        # Only surface for property/material-ish questions (avoid noise on CAD kernels)
        property_hit = any(
            t in q
            for t in (
                "density",
                "dichte",
                "yield",
                "streck",
                "modulus",
                "young",
                "material",
                "steel",
                "stahl",
                "aluminum",
                "aluminium",
                "pla",
                "petg",
                "kg/m",
                "g/cm",
            )
        )
        if not property_hit:
            return []

        found: list[str] = []
        seen: set[str] = set()
        for phrase, key in self._ALIASES:
            if phrase in q and key in MATERIALS and key not in seen:
                seen.add(key)
                found.append(key)
        if not found:
            return []

        out: list[SourceCandidate] = []
        for key in found[:limit]:
            mat = MATERIALS[key]
            out.append(
                SourceCandidate(
                    url_or_id=f"gen-materials://{key}",
                    title=f"GENESIS materials registry: {mat.name}",
                    backend=self.name,
                    relevance_note=(
                        f"Grounded handbook entry for {mat.name} "
                        f"(ρ={mat.density_g_cm3} g/cm³); {mat.source[:80]}"
                    ),
                    fetched_ok=False,
                )
            )
        return out


def materials_claim_text(key: str, *, language: str = "en") -> tuple[str, str]:
    """Return (claim_text, quote) for a registry material — density-focused.

    Quote is a contiguous span of the registry source string (provenance text),
    not a fabricated measurement. Claim states SI density from the registry.
    """
    mat = MATERIALS[key]
    rho_kg = mat.density_g_cm3 * 1000.0
    quote = mat.source.strip()
    if len(quote) < 12:
        quote = f"{mat.name} density_g_cm3={mat.density_g_cm3} source={mat.source}"
    if language == "de":
        text = (
            f"Die nominelle Dichte von {mat.name} im GENESIS-Materialregister "
            f"beträgt {rho_kg:.0f} kg/m³ ({mat.density_g_cm3} g/cm³); "
            f"Quelle: Registereintrag (nicht messwert-spezifisch)."
        )
    else:
        text = (
            f"The nominal density of {mat.name} in the GENESIS materials registry "
            f"is {rho_kg:.0f} kg/m³ ({mat.density_g_cm3} g/cm³); "
            f"source: registry entry (handbook band, not part-specific)."
        )
    return text, quote[:200]
