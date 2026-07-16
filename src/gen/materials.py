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
from typing import Optional


@dataclass(frozen=True)
class Material:
    """A material's nominal engineering properties WITH provenance. ``source`` is mandatory — a material
    property without a citation is exactly the kind of anonymous constant this registry replaces.

    ``thermal_conductivity_w_mk`` is optional (None = not claimed). When set, it is a nominal handbook
    band for pure/typical grades — alloy and temperature dependence require a TDS (self-improve 2026-07-14).
    """

    name: str
    youngs_modulus_mpa: float
    density_g_cm3: float
    yield_strength_mpa: float
    source: str
    note: str = "typical FDM value; confirm against the filament TDS for the actual print profile"
    thermal_conductivity_w_mk: Optional[float] = None
    cte_per_k: Optional[float] = None
    fatigue_basquin_a_pa: Optional[float] = None
    fatigue_basquin_b: Optional[float] = None
    property_source_extra: str = ""


_TDS = "typical FDM datasheet range (printed-plastics references); nominal, not part-specific"
_K_NOTE = "nominal handbook k (W/m·K) at ~room temp; alloy/temperature TDS required"

#: Curated registry of common FDM materials. Values are widely-published typical ranges, each sourced.
_CTE_SRC = (
    "nominal CTE α (1/K) room-temp handbook band; confirm against grade TDS "
    "(ASM Handbook / manufacturer expansion tables as orientation)"
)
_FAT_SRC = (
    "nominal Basquin-like SN parameters (A, b) for first-stone screening only — "
    "NOT a certified SN test; replace with coupon data for release"
)

_FDM: dict[str, Material] = {
    "PLA": Material(
        "PLA", 3500.0, 1.24, 50.0, _TDS,
        thermal_conductivity_w_mk=0.13,
        cte_per_k=70e-6,
        fatigue_basquin_a_pa=5e15,
        fatigue_basquin_b=6.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "PETG": Material(
        "PETG", 2100.0, 1.27, 50.0, _TDS,
        thermal_conductivity_w_mk=0.20,
        cte_per_k=65e-6,
        fatigue_basquin_a_pa=4e15,
        fatigue_basquin_b=5.5,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "ABS": Material(
        "ABS", 2300.0, 1.04, 40.0, _TDS,
        thermal_conductivity_w_mk=0.17,
        cte_per_k=90e-6,
        fatigue_basquin_a_pa=3e15,
        fatigue_basquin_b=5.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "PA": Material(
        "PA", 2000.0, 1.14, 50.0, _TDS,
        thermal_conductivity_w_mk=0.25,
        cte_per_k=80e-6,
        fatigue_basquin_a_pa=6e15,
        fatigue_basquin_b=5.5,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "TPU": Material(
        "TPU", 80.0, 1.21, 8.0, _TDS,
        thermal_conductivity_w_mk=0.19,
        cte_per_k=150e-6,
        fatigue_basquin_a_pa=1e14,
        fatigue_basquin_b=4.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
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
        thermal_conductivity_w_mk=50.0,  # carbon steel ~45–60
        cte_per_k=12e-6,  # carbon steel ~11–13e-6 /K
        fatigue_basquin_a_pa=1e20,
        fatigue_basquin_b=3.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "MILD_STEEL": Material(
        "MILD_STEEL",
        youngs_modulus_mpa=210_000.0,
        density_g_cm3=7.85,
        yield_strength_mpa=250.0,
        source=_METAL_SRC,
        note="alias of STEEL (mild/structural)",
        thermal_conductivity_w_mk=50.0,
        cte_per_k=12e-6,
        fatigue_basquin_a_pa=1e20,
        fatigue_basquin_b=3.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "ALUMINUM": Material(
        "ALUMINUM",
        youngs_modulus_mpa=70_000.0,
        density_g_cm3=2.70,
        yield_strength_mpa=95.0,  # 6061-T6 order of magnitude; TDS required
        source="nominal Al alloy handbook band (ρ≈2.70 g/cm³; E≈70 GPa); alloy TDS required",
        note="nominal aluminum alloy; grade-specific TDS required",
        thermal_conductivity_w_mk=205.0,  # 6000-series order; pure Al higher
        cte_per_k=23e-6,  # Al alloys ~22–24e-6 /K
        fatigue_basquin_a_pa=5e18,
        fatigue_basquin_b=4.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "ALUMINIUM": Material(  # spelling alias
        "ALUMINIUM",
        youngs_modulus_mpa=70_000.0,
        density_g_cm3=2.70,
        yield_strength_mpa=95.0,
        source="nominal Al alloy handbook band (ρ≈2.70 g/cm³; E≈70 GPa); alloy TDS required",
        note="alias of ALUMINUM",
        thermal_conductivity_w_mk=205.0,
        cte_per_k=23e-6,
        fatigue_basquin_a_pa=5e18,
        fatigue_basquin_b=4.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "COPPER": Material(
        "COPPER",
        youngs_modulus_mpa=110_000.0,
        density_g_cm3=8.96,
        yield_strength_mpa=70.0,  # annealed order; hard-drawn much higher — TDS required
        source="nominal pure copper handbook band (ρ≈8.96 g/cm³; E≈110 GPa); temper TDS required",
        note="nominal copper; temper-specific TDS required",
        thermal_conductivity_w_mk=401.0,  # pure Cu ~400 W/m·K
        cte_per_k=17e-6,
        fatigue_basquin_a_pa=2e18,
        fatigue_basquin_b=3.5,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "TITANIUM": Material(
        "TITANIUM",
        youngs_modulus_mpa=116_000.0,
        density_g_cm3=4.51,
        yield_strength_mpa=140.0,  # commercially pure order; Ti-6Al-4V much higher
        source="nominal commercially pure Ti handbook band (ρ≈4.51 g/cm³); alloy TDS required",
        note="nominal CP titanium; alloy grade TDS required",
        thermal_conductivity_w_mk=22.0,  # CP Ti low k
        cte_per_k=8.6e-6,
        fatigue_basquin_a_pa=1e19,
        fatigue_basquin_b=3.5,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
    ),
    "IRON": Material(
        "IRON",
        youngs_modulus_mpa=200_000.0,
        density_g_cm3=7.87,
        yield_strength_mpa=50.0,  # pure iron soft; structural uses steel grades
        source="nominal pure iron handbook band (ρ≈7.87 g/cm³; E≈200 GPa); grade TDS required",
        note="nominal pure iron — prefer STEEL for structural design",
        thermal_conductivity_w_mk=80.0,
        cte_per_k=12e-6,
        fatigue_basquin_a_pa=5e19,
        fatigue_basquin_b=3.0,
        property_source_extra=f"{_CTE_SRC}; {_FAT_SRC}",
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


def thermal_conductivity_w_mk(material_name: str) -> float:
    """Thermal conductivity in W/(m·K) from the registry. Raises if the material has no grounded k."""
    mat = get_material(material_name)
    if mat.thermal_conductivity_w_mk is None:
        raise ValueError(
            f"material {material_name!r} has no grounded thermal_conductivity_w_mk in the registry"
        )
    return float(mat.thermal_conductivity_w_mk)


def cte_per_k(material_name: str) -> float:
    """Linear CTE α (1/K) from the registry. Raises if not grounded for this material."""
    mat = get_material(material_name)
    if mat.cte_per_k is None:
        raise ValueError(f"material {material_name!r} has no grounded cte_per_k")
    return float(mat.cte_per_k)


def fatigue_basquin_params(material_name: str) -> tuple[float, float]:
    """Return (A_pa, b) Basquin parameters. Raises if not grounded."""
    mat = get_material(material_name)
    if mat.fatigue_basquin_a_pa is None or mat.fatigue_basquin_b is None:
        raise ValueError(
            f"material {material_name!r} has no grounded fatigue Basquin parameters"
        )
    return float(mat.fatigue_basquin_a_pa), float(mat.fatigue_basquin_b)


def material_sim_bundle(material_name: str) -> dict:
    """Bundle E, ρ, fy, k, CTE, fatigue for multi-physics with full provenance."""
    mat = get_material(material_name)
    return {
        "name": mat.name,
        "youngs_modulus_mpa": mat.youngs_modulus_mpa,
        "density_g_cm3": mat.density_g_cm3,
        "yield_strength_mpa": mat.yield_strength_mpa,
        "thermal_conductivity_w_mk": mat.thermal_conductivity_w_mk,
        "cte_per_k": mat.cte_per_k,
        "fatigue_basquin_a_pa": mat.fatigue_basquin_a_pa,
        "fatigue_basquin_b": mat.fatigue_basquin_b,
        "source": mat.source,
        "property_source_extra": mat.property_source_extra,
        "note": mat.note,
        "quelle": "gen.materials.material_sim_bundle",
    }
