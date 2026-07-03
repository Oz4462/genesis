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
MATERIALS: dict[str, Material] = {
    "PLA": Material("PLA", 3500.0, 1.24, 50.0, _TDS),
    "PETG": Material("PETG", 2100.0, 1.27, 50.0, _TDS),
    "ABS": Material("ABS", 2300.0, 1.04, 40.0, _TDS),
    "PA": Material("PA", 2000.0, 1.14, 50.0, _TDS),         # nylon
    "TPU": Material("TPU", 80.0, 1.21, 8.0, _TDS),          # flexible
}


def get_material(name: str) -> Material:
    """Look up a grounded material by name (case-insensitive). Raises ``ValueError`` for an unknown
    material — GENESIS never returns a guessed property."""
    material = MATERIALS.get(name.strip().upper())
    if material is None:
        known = ", ".join(sorted(MATERIALS))
        raise ValueError(f"unknown material {name!r}; no grounded properties available (known: {known})")
    return material
