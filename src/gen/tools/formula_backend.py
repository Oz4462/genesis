"""Formula-aware search backend for Scout.

Returns high-quality, authoritative candidates for mathematical and physical
formulas/laws from the curated sources (DLMF, NIST CODATA, Wikidata conceptual).

This makes Scout "formula aware": when the question mentions formulas, laws,
special functions, constants, etc., these candidates surface reliably.

It never invents new sources — only known good authoritative URLs + short note.
"""

from __future__ import annotations

from ..core.state import SourceCandidate
from .http import HttpGet


class FormulaBackend:
    """Provides direct authoritative sources for formulas and laws."""

    name = "formula"

    FORMULA_SOURCES = [
        # DLMF high value
        ("https://dlmf.nist.gov/10.2", "Bessel equation and J_ν, Y_ν definitions (DLMF 10.2)"),
        ("https://dlmf.nist.gov/5.2", "Gamma function properties and recurrence (DLMF 5)"),
        ("https://dlmf.nist.gov/7.2", "Error function erf and erfc (DLMF 7)"),
        ("https://dlmf.nist.gov/9.2", "Airy functions Ai, Bi (DLMF 9)"),
        # NIST CODATA authoritative table
        ("https://physics.nist.gov/cuu/Constants/Table/allascii.txt", "NIST CODATA 2022 fundamental physical constants (exact values + uncertainties)"),
        ("https://physics.nist.gov/constants", "NIST Physical Measurement Laboratory - CODATA recommended values"),
    ]

    def __init__(self, http_get: HttpGet | None = None):
        # http_get not strictly needed for static authoritative links, kept for protocol compatibility
        self._http_get = http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        q = query.lower()
        candidates: list[SourceCandidate] = []

        keywords = {"formula", "law", "constant", "bessel", "gamma", "erf", "airy", "codata", "nist", "physical constant", "special function", "equation"}

        if any(k in q for k in keywords):
            for url, note in self.FORMULA_SOURCES:
                cand = SourceCandidate(
                    url_or_id=url,
                    title=note,
                    backend=self.name,
                    relevance_note=f"Authoritative formula/law source for query: {query}",
                    fetched_ok=False,
                )
                candidates.append(cand)
                if len(candidates) >= limit:
                    break

        return candidates[:limit]
