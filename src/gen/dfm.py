"""Design-for-Manufacturability (DFM) reference data and rule formulas (δ-layer).

A spec can be geometrically sound and still be un-printable: a wall thinner than
the extruder can lay down, a hole too small to survive, an overhang that needs
support. Real DFM tools run dozens of such deterministic geometric rules. GENESIS
adds the ones it can prove from the existing quantities — again with NO new gate
code: the process minimums are GROUNDED/DERIVED quantities and each rule is a
numeric constraint (C-13), dimension-checked by C-15.

Scope honesty: only rules expressible from the quantities the spec already
carries are encoded (minimum wall thickness, minimum printable hole diameter).
Rules that need a build-orientation model the CSG does not carry — overhang angle
(> 45° needs support), bridge span, support generation — are NOT silently
"passed"; they are declared as gaps. A passed DFM check is necessary, not
sufficient (the same δ asymmetry as geometry and statics).

Sources (FDM / FFF, verified 2026-06-11):
  * Minimum wall ≈ 0.8 mm = two perimeter lines of a standard 0.4 mm nozzle
    (2 × 0.4). Walls thinner than this print unreliably / fragile.
  * Minimum reliably printable hole: 2.0 mm horizontal (1.0 mm vertical) — the
    conservative 2.0 mm is used.
  * Overhangs steeper than 45° from vertical need support (declared as a gap).
    Refs: UltiMaker "Design for FFF"; Hydra Research FFF design rules;
    Xometry FDM design tips; Stanford Lab64 FDM rules of thumb.
"""

from __future__ import annotations

#: Standard FDM/FFF nozzle diameter [mm].
FDM_NOZZLE_DIAMETER_MM = 0.4

#: Minimum perimeter lines that make a reliable wall (two).
FDM_WALL_PERIMETERS_MIN = 2.0

#: Minimum reliably printable wall thickness [mm] = perimeters × nozzle = 0.8.
FDM_MIN_WALL_MM = FDM_WALL_PERIMETERS_MIN * FDM_NOZZLE_DIAMETER_MM

#: Minimum reliably printable horizontal hole diameter [mm] (conservative).
FDM_MIN_HOLE_DIAMETER_MM = 2.0


def min_wall_formula(nozzle_id: str, perimeters_id: str) -> str:
    """``min_wall = perimeters · nozzle`` — the thinnest reliable FDM wall.

    Length × dimensionless = length, so the result is a length (C-15); a
    constraint ``wall_thickness >= min_wall`` is the DFM check (C-13)."""
    return f"{nozzle_id} * {perimeters_id}"
