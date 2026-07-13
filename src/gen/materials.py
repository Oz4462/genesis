"""materials — a grounded, provenance-carrying material registry (replaces hard-coded constants).

Agent-B finding: GENESIS consumes material properties as hard-coded constants. The honest upgrade is to
treat a material property like any other fact — it carries a SOURCE (CLAUDE.md §1: no fact without a
source). This module is a small curated registry of common FDM materials with typical Young's modulus,
density and yield strength, each tagged with its provenance, so ``structural``/``costing`` can ground
their numbers with a citation instead of an anonymous literal.

Honesty: these are TYPICAL datasheet values — real FDM properties vary strongly with print settings
(infill, orientation, temperature), so each entry is flagged as nominal and must be confirmed against
the filament manufacturer's technical data sheet for the actual print profile (DERIVED, not measured for
a specific part). A live, citable source (the Materials Project elastic API, CC BY 4.0, material-id +
DOI provenance) is the documented opt-in for DFT-grounded crystalline data; it needs an API key + network
and is external. An unknown material RAISES — never a silently guessed property. Offline, deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    """A material's nominal engineering properties WITH provenance. ``source`` is mandatory — a material
    property without a citation is exactly the kind of anonymous constant this registry replaces."""

    name: str
    youngs_modulus_mpa: float
    density_g_cm3: float
    yield_strength_mpa: float
    source: str
    note: str = "typical FDM value; confirm against the filament TDS for the actual print profile"


_TDS = "typical FDM datasheet range (printed-plastics references); nominal, not part-specific"

#: Curated registry of common FDM materials. Values are widely-published typical ranges, each sourced.
_FDM: dict[str, Material] = {
    "PLA": Material("PLA", 3500.0, 1.24, 50.0, _TDS),
    "PETG": Material("PETG", 2100.0, 1.27, 50.0, _TDS),
    "ABS": Material("ABS", 2300.0, 1.04, 40.0, _TDS),
    "PA": Material("PA", 2000.0, 1.14, 50.0, _TDS),         # nylon
    "TPU": Material("TPU", 80.0, 1.21, 8.0, _TDS),          # flexible
}

# Structural metals — nominal engineering handbook band (not part-specific).
# Density mid-band of the Wikipedia/common handbook range 7750–8050 kg/m³ for
# carbon/structural steel (self-improve 2026-07-13: offline δ-path needs a
# grounded STEEL entry; live α still prefers Wikipedia extracts).
_METAL_SRC = (
    "nominal structural-steel handbook band (≈7850 kg/m³ density; E≈210 GPa; "
    "fy≈250 MPa mild steel); confirm against the specific alloy datasheet — "
    "Wikipedia Steel density band 7750–8050 kg/m³ as orientation only"
)
_METALS: dict[str, Material] = {
    "STEEL": Material(
        "STEEL",
        youngs_modulus_mpa=210_000.0,
        density_g_cm3=7.85,  # 7850 kg/m³
        yield_strength_mpa=250.0,
        source=_METAL_SRC,
        note="nominal mild/structural steel; alloy-specific TDS required for certified design",
    ),
    "MILD_STEEL": Material(
        "MILD_STEEL",
        youngs_modulus_mpa=210_000.0,
        density_g_cm3=7.85,
        yield_strength_mpa=250.0,
        source=_METAL_SRC,
        note="alias of STEEL (mild/structural)",
    ),
    "ALUMINUM": Material(
        "ALUMINUM",
        youngs_modulus_mpa=70_000.0,
        density_g_cm3=2.70,
        yield_strength_mpa=95.0,  # 6061-T6 order of magnitude; TDS required
        source="nominal Al alloy handbook band (ρ≈2.70 g/cm³; E≈70 GPa); alloy TDS required",
        note="nominal aluminum alloy; grade-specific TDS required",
    ),
    "ALUMINIUM": Material(  # spelling alias
        "ALUMINIUM",
        youngs_modulus_mpa=70_000.0,
        density_g_cm3=2.70,
        yield_strength_mpa=95.0,
        source="nominal Al alloy handbook band (ρ≈2.70 g/cm³; E≈70 GPa); alloy TDS required",
        note="alias of ALUMINUM",
    ),
    "COPPER": Material(
        "COPPER",
        youngs_modulus_mpa=110_000.0,
        density_g_cm3=8.96,
        yield_strength_mpa=70.0,  # annealed order; hard-drawn much higher — TDS required
        source="nominal pure copper handbook band (ρ≈8.96 g/cm³; E≈110 GPa); temper TDS required",
        note="nominal copper; temper-specific TDS required",
    ),
    "TITANIUM": Material(
        "TITANIUM",
        youngs_modulus_mpa=116_000.0,
        density_g_cm3=4.51,
        yield_strength_mpa=140.0,  # commercially pure order; Ti-6Al-4V much higher
        source="nominal commercially pure Ti handbook band (ρ≈4.51 g/cm³); alloy TDS required",
        note="nominal CP titanium; alloy grade TDS required",
    ),
    "IRON": Material(
        "IRON",
        youngs_modulus_mpa=200_000.0,
        density_g_cm3=7.87,
        yield_strength_mpa=50.0,  # pure iron soft; structural uses steel grades
        source="nominal pure iron handbook band (ρ≈7.87 g/cm³; E≈200 GPa); grade TDS required",
        note="nominal pure iron — prefer STEEL for structural design",
    ),
}

MATERIALS: dict[str, Material] = {**_FDM, **_METALS}


def get_material(name: str) -> Material:
    """Look up a grounded material by name (case-insensitive). Raises ``ValueError`` for an unknown
    material — GENESIS never returns a guessed property."""
    key = name.strip().upper().replace(" ", "_").replace("-", "_")
    # common aliases
    aliases = {
        "CARBON_STEEL": "STEEL",
        "STRUCTURAL_STEEL": "STEEL",
        "AL": "ALUMINUM",
        "ALU": "ALUMINUM",
        "CU": "COPPER",
        "TI": "TITANIUM",
    }
    key = aliases.get(key, key)
    material = MATERIALS.get(key)
    if material is None:
        known = ", ".join(sorted(MATERIALS))
        raise ValueError(f"unknown material {name!r}; no grounded properties available (known: {known})")
    return material


def density_kg_m3(material_name: str) -> float:
    """Density in SI kg/m³ from the grounded registry (g/cm³ × 1000)."""
    return get_material(material_name).density_g_cm3 * 1000.0
