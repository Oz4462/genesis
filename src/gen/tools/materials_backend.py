"""Materials registry search backend — discovery of grounded handbook materials.

Self-improve loop 2026-07-13: live α density questions needed a second, offline
provenance path alongside Wikipedia. This backend does DISCOVERY only: it returns
``SourceCandidate``s whose ``url_or_id`` is a stable ``gen-materials://`` token
that the scholar's materials path turns into UNVERIFIED claims with registry
provenance. It never invents numeric values outside ``materials.MATERIALS``.
"""

from __future__ import annotations

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
        ("iron", "IRON"),
        ("eisen", "IRON"),
        ("steel", "STEEL"),
        ("stahl", "STEEL"),
        ("pla", "PLA"),
        ("petg", "PETG"),
        ("abs", "ABS"),
    )

    def __init__(self, http_get=None) -> None:
        self._http_get = http_get

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        if limit <= 0:
            return []
        q = (query or "").lower()
        if not q.strip():
            return []
        # Only surface for property/material-ish questions (avoid noise on CAD kernels).
        # Metal names included so invent/thermal prior-art novelty queries hit the registry
        # (self-improve 2026-07-14: "copper cold plate" was silent without copper in gate).
        property_hit = any(
            t in q
            for t in (
                "density",
                "dichte",
                "yield",
                "streck",
                "modulus",
                "young",
                "thermal",
                "conductivity",
                "wärmeleit",
                "waermeleit",
                "heat",
                "material",
                "steel",
                "stahl",
                "aluminum",
                "aluminium",
                "copper",
                "kupfer",
                "titanium",
                "titan",
                "iron",
                "eisen",
                "pla",
                "petg",
                "abs",
                "kg/m",
                "g/cm",
            )
        )
        if not property_hit:
            return []

        found: list[str] = []
        seen: set[str] = set()
        for phrase, key in self._ALIASES:
            if phrase not in q or key not in MATERIALS or key in seen:
                continue
            # Primary keys only for generic queries — aliases when explicitly named
            if key == "MILD_STEEL" and "mild" not in q:
                continue
            if key == "ALUMINIUM" and "aluminium" not in q:
                continue
            seen.add(key)
            found.append(key)
        if not found:
            return []

        out: list[SourceCandidate] = []
        for key in found[:limit]:
            mat = MATERIALS[key]
            k_note = (
                f"; k={mat.thermal_conductivity_w_mk:g} W/m·K"
                if mat.thermal_conductivity_w_mk is not None
                else ""
            )
            out.append(
                SourceCandidate(
                    url_or_id=f"gen-materials://{key}",
                    title=f"GENESIS materials registry: {mat.name}",
                    backend=self.name,
                    relevance_note=(
                        f"Grounded handbook entry for {mat.name} "
                        f"(ρ={mat.density_g_cm3} g/cm³{k_note}); {mat.source[:80]}"
                    ),
                    fetched_ok=False,
                )
            )
        return out


def materials_claim_text(key: str, *, language: str = "en") -> tuple[str, str]:
    """Return (claim_text, quote) for a registry material — density-focused (compat).

    Prefer :func:`materials_claims` when the scholar wants separate ρ/k claims.
    """
    claims = materials_claims(key, language=language)
    # density claim is always first
    text, quote, _span = claims[0]
    return text, quote


def materials_claims(
    key: str, *, language: str = "en"
) -> list[tuple[str, str, str]]:
    """Return grounded registry claims as ``(text, quote, span_tag)``.

    Self-improve 2026-07-14: density and thermal conductivity are **separate** claims
    so α can verify ρ and k independently (a single blob mixed both properties and
    made skeptic evidence windows noisier). Each claim is UNVERIFIED handbook band
    until an independent source corroborates.
    """
    mat = MATERIALS[key]
    rho_kg = mat.density_g_cm3 * 1000.0
    quote = mat.source.strip()
    if len(quote) < 12:
        quote = f"{mat.name} density_g_cm3={mat.density_g_cm3} source={mat.source}"
    quote = quote[:200]
    out: list[tuple[str, str, str]] = []
    if language == "de":
        out.append(
            (
                f"Die nominelle Dichte von {mat.name} im GENESIS-Materialregister "
                f"beträgt {rho_kg:.0f} kg/m³ ({mat.density_g_cm3} g/cm³); "
                f"Quelle: Registereintrag (nicht messwert-spezifisch).",
                quote,
                f"{key}/density",
            )
        )
        if mat.thermal_conductivity_w_mk is not None:
            out.append(
                (
                    f"Die nominelle Wärmeleitfähigkeit von {mat.name} im GENESIS-Materialregister "
                    f"beträgt {mat.thermal_conductivity_w_mk:g} W/(m·K); "
                    f"Quelle: Registereintrag (Handbuchband, nicht messwert-spezifisch).",
                    quote,
                    f"{key}/thermal_conductivity",
                )
            )
    else:
        out.append(
            (
                f"The nominal density of {mat.name} in the GENESIS materials registry "
                f"is {rho_kg:.0f} kg/m³ ({mat.density_g_cm3} g/cm³); "
                f"source: registry entry (handbook band, not part-specific).",
                quote,
                f"{key}/density",
            )
        )
        if mat.thermal_conductivity_w_mk is not None:
            out.append(
                (
                    f"The nominal thermal conductivity of {mat.name} in the GENESIS materials registry "
                    f"is {mat.thermal_conductivity_w_mk:g} W/(m·K); "
                    f"source: registry entry (handbook band, not part-specific).",
                    quote,
                    f"{key}/thermal_conductivity",
                )
            )
    return out
