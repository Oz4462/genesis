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


# === CNC machining (subtractive) DFM reference data ===
# Subtractive milling has a DIFFERENT rule set than FDM: a tool must reach and
# remove material, so thin walls chatter under cutting load, internal corners
# cannot be sharper than the end-mill radius, and deep narrow features need
# long fragile tools. As with FDM, only the rules expressible from the
# quantities the spec carries (wall thickness, overall envelope) are evaluated;
# the geometric rules that need cavity/pocket/hole geometry the CSG spec does
# NOT carry are declared as gaps (see cnc_geometric_gaps) — never silently
# passed. A passed CNC check is necessary, not sufficient.
#
# Sources (CNC milling, verified 2026-06-17):
#   * Min wall — metal 0.8 mm recommended (0.5 mm vendor minimum feature, below
#     which the wall flexes/breaks under tool load); plastic 1.5 mm recommended
#     (thermal distortion). Refs: Protolabs "DFM for CNC"; Xometry CNC design
#     tips; fsfab CNC wall-thickness guide.
#   * General tolerance — ISO 2768-1 "m" (medium) is the default for linear/
#     angular dims left unspecified on a CNC drawing. Ref: Fictiv ISO 2768.
#   * Internal corner radius ≥ tool radius and ≥ 1/3 cavity depth — needs cavity
#     geometry (gap). Refs: MakerStage; uneed CNC internal corner radius.
#   * Pocket depth:width ≤ 3:1 with standard end mills (≤ 6:1 extended reach,
#     added cost / worse finish) — needs pocket geometry (gap). Refs: MakerStage;
#     Protolabs.
#   * Hole depth:diameter ≤ 4:1 ideal (≤ 10:1 max) for chip evacuation — needs
#     hole geometry (gap). Refs: Jiga CNC design guide; Manufyn.

#: Recommended minimum machinable wall in metal [mm] (0.5 mm is the hard floor).
CNC_MIN_WALL_METAL_MM = 0.8
#: Hard floor below which a metal wall is unmachinable without EDM [mm].
CNC_MIN_WALL_METAL_FLOOR_MM = 0.5
#: Recommended minimum machinable wall in plastic [mm].
#: Used to flag the material ambiguity when a wall passes metal but not plastic.
CNC_MIN_WALL_PLASTIC_MM = 1.5
#: Default general tolerance for unspecified CNC dimensions.
CNC_GENERAL_TOLERANCE_ISO2768 = "ISO 2768-1 m (medium)"
#: Reliable pocket depth-to-width ratio with standard end mills.
CNC_POCKET_ASPECT_RATIO_STD = 3.0
#: Pocket depth-to-width ratio reachable with extended-reach tooling (added cost).
CNC_POCKET_ASPECT_RATIO_EXTENDED = 6.0
#: Ideal hole depth-to-diameter ratio for chip evacuation.
CNC_HOLE_DEPTH_DIAMETER_IDEAL = 4.0
#: Practical maximum hole depth-to-diameter ratio (chip evacuation / accuracy).
CNC_HOLE_DEPTH_DIAMETER_MAX = 10.0
#: Max 3-axis milling DEPTH per side [mm] — Protolabs caps this at 2 in (50.8 mm).
#: Envelope fit is per-axis and machine/material-specific, so it is NOT reducible
#: to one bounding-box threshold; the check surfaces envelope fit as a gap, not a
#: blocker. Ref: Protolabs "Maximum Milling & Turning Extents".
CNC_MAX_MILL_DEPTH_MM = 50.8

#: Provenance string for the CNC reference data above.
CNC_DFM_SOURCE = "Protolabs / Xometry / Fictiv / MakerStage CNC DFM (2026-06-17)"


def cnc_geometric_gaps() -> list[str]:
    """The CNC DFM rules a real tool runs but that need cavity/pocket/hole
    geometry the CSG spec does NOT carry. Declared as gaps so the verdict is
    honestly provisional — never silently passed (necessary, not sufficient)."""
    return [
        f"CNC: internal corner radius (≥ end-mill radius and ≥ 1/3 cavity depth) "
        f"not evaluable — spec carries no cavity geometry ({CNC_DFM_SOURCE})",
        f"CNC: pocket depth:width ratio (≤ {CNC_POCKET_ASPECT_RATIO_STD:.0f}:1 standard, "
        f"≤ {CNC_POCKET_ASPECT_RATIO_EXTENDED:.0f}:1 extended reach at added cost) not "
        f"evaluable — spec carries no pocket geometry",
        f"CNC: hole depth:diameter ratio (≤ {CNC_HOLE_DEPTH_DIAMETER_IDEAL:.0f}:1 ideal, "
        f"≤ {CNC_HOLE_DEPTH_DIAMETER_MAX:.0f}:1 max) not evaluable — spec carries no "
        f"hole geometry",
    ]


# === Laser / sheet cutting DFM reference data ===
# Laser cutting is a 2D SHEET process: it cuts a flat profile from constant-
# thickness stock. The governing quantity is the sheet thickness (the part's
# smallest extent). Only thickness-vs-max is evaluable from the spec; the in-
# plane form (is it a flat cuttable profile at all?), feature/hole sizes vs
# thickness, bridging and kerf need the 2D geometry the spec does NOT carry and
# are declared as gaps, never silently passed (necessary, not sufficient).
#
# Max cuttable thickness is EQUIPMENT- and material-specific, not one universal
# number: a typical online job-shop caps lower than a high-power industrial fiber,
# so a single hard threshold would be dishonest (the same lesson as the CNC
# envelope). Two anchors are used: the industrial high-power fiber upper bound
# (beyond it -> waterjet/plasma, a determinate blocker) and the typical online-
# shop cap (above it -> an equipment gap, not a pass).
#
# Sources (laser / sheet, verified 2026-06-17):
#   * Industrial high-power fiber upper bound: mild steel ~25 mm, stainless ~15 mm,
#     aluminum ~12 mm; beyond -> waterjet / plasma. Refs: Wurth plasma/laser/
#     waterjet; Xometry "Laser Cutting Rules"; TechniWaterjet.
#   * Typical online job-shop cap: mild steel & 5052 aluminum 0.500 in = 12.7 mm
#     (±0.005 in). Ref: SendCutSend material min/max.
#   * Min hole / interior feature: floor ~0.5x thickness (the pierce diameter),
#     recommended >= 1x thickness. Refs: SendCutSend small-geometry; Xometry.
#   * Bridging / web between features >= 1x-1.5x thickness. Ref: SendCutSend
#     cut-feature relationships.
#   * Kerf 0.1-1.0 mm, material/power/speed dependent. Ref: SendCutSend; Xometry.

#: Industrial high-power fiber laser upper bound, mild steel [mm] — beyond this
#: NO laser cuts (waterjet/plasma territory). Most generous laser case.
LASER_MAX_THICKNESS_STEEL_MM = 25.0
#: Industrial high-power fiber upper bound, stainless steel [mm].
LASER_MAX_THICKNESS_STAINLESS_MM = 15.0
#: Industrial high-power fiber upper bound, aluminum [mm].
LASER_MAX_THICKNESS_ALUMINUM_MM = 12.0
#: Typical online job-shop laser cap [mm] (SendCutSend mild steel & 5052 = 0.5 in).
LASER_TYPICAL_SHOP_MAX_MM = 12.7
#: Absolute floor for a hole/interior feature as a multiple of thickness (pierce).
LASER_MIN_FEATURE_FLOOR_RATIO = 0.5
#: Recommended minimum hole/feature as a multiple of thickness.
LASER_MIN_FEATURE_RECOMMENDED_RATIO = 1.0
#: Bridging / web between features as a multiple of thickness (min..max).
LASER_BRIDGE_MIN_RATIO = 1.0
LASER_BRIDGE_MAX_RATIO = 1.5
#: Typical kerf width range [mm] (material / power / speed dependent — not fixed).
LASER_KERF_MIN_MM = 0.1
LASER_KERF_MAX_MM = 1.0

#: Provenance string for the laser/sheet reference data above.
LASER_DFM_SOURCE = "SendCutSend / Xometry / Wurth laser & sheet DFM (2026-06-17)"


def laser_sheet_gaps(thickness_mm: float) -> list[str]:
    """Laser/sheet DFM rules that need the 2D profile + feature geometry the spec
    does NOT carry. Declared as gaps so the verdict is honestly provisional."""
    return [
        f"Laser: in-plane form not verifiable — stock thickness taken as the bounding-"
        f"box minimum (~{thickness_mm:g}mm, the plate thickness, may differ from "
        f"min_wall); laser needs a flat 2D-cuttable profile, which the bounding box "
        f"cannot confirm a solid/3D part would fail ({LASER_DFM_SOURCE})",
        f"Laser: min hole/feature (floor ~{LASER_MIN_FEATURE_FLOOR_RATIO:g}× thickness, "
        f"recommended ≥ {LASER_MIN_FEATURE_RECOMMENDED_RATIO:g}× ~{thickness_mm:g}mm) "
        f"not evaluable — spec carries no feature geometry",
        f"Laser: bridging/web ≥ {LASER_BRIDGE_MIN_RATIO:g}–{LASER_BRIDGE_MAX_RATIO:g}× "
        f"thickness not evaluable — spec carries no feature spacing",
        f"Laser: kerf {LASER_KERF_MIN_MM}–{LASER_KERF_MAX_MM}mm is material/power "
        f"dependent, not a fixed value — confirm against the cutter",
    ]


# === PCB (printed circuit board) fab DFM reference data ===
# A PCB is a 2D COPPER layout (traces, pads, vias on copper layers), NOT a
# mechanical solid. The mechanical CAD artifact carries no copper geometry, so
# NONE of the fab rules below are evaluable from it — they are reference
# capabilities, and a real PCB DRC needs a routed layout (Gerber / KiCad), the
# electronics-layer seam. Declared via pcb_dfm_gaps() — never silently passed.
#
# Sources (PCB fab, verified 2026-06-18):
#   * Standard tier (2-layer, 1 oz Cu): min trace width & spacing 0.127 mm (5 mil).
#     Heavier copper / more layers shift these — this is the cheap tier, not universal.
#   * Via: technical min drill 0.15 mm (any layer), recommended >= 0.3 mm for cost;
#     pad >= drill + 0.3 mm (annular ring ~0.15 mm/side); aspect ratio <= 10:1.
#     Refs: JLCPCB capabilities; JLCPCB via-design guide.
#   * Trace width from current (IPC-2221): I = k · ΔT^0.44 · A^0.725, A in mil²,
#     k = 0.048 external / 0.024 internal; 1 oz copper = 1.378 mil thick.
#     Refs: IPC-2221; tracewidthcalculator.com; HilElectronic.

#: Standard-tier (2-layer, 1 oz Cu) minimum trace width / spacing [mm] (5 mil).
PCB_MIN_TRACE_MM = 0.127
PCB_MIN_SPACING_MM = 0.127
#: Technical minimum drilled via diameter [mm] (any layer count).
PCB_MIN_VIA_DRILL_MM = 0.15
#: Recommended via drill [mm] for cost-effective processing (avoids surcharge).
PCB_RECOMMENDED_VIA_DRILL_MM = 0.3
#: Minimum annular ring per side [mm] (pad >= drill + 0.3 mm).
PCB_MIN_ANNULAR_RING_MM = 0.15
#: Minimum copper-to-board-edge clearance [mm] (pad/general; trace-to-edge ~0.2 mm).
#: Distinct from conductor spacing — a milled edge needs a safety margin. Ref: JLCPCB.
PCB_MIN_COPPER_TO_EDGE_MM = 0.3
#: Maximum via aspect ratio (board thickness : drill diameter) for reliable plating.
PCB_MAX_VIA_ASPECT_RATIO = 10.0
#: The fab tier the trace/spacing minimums above assume (NOT universal).
PCB_CAPABILITY_TIER = "2-layer, 1 oz Cu (standard fab tier)"
#: Thickness of 1 oz copper [mil] (for the IPC-2221 area→width conversion).
PCB_COPPER_MIL_PER_OZ = 1.378
#: IPC-2221 current constant — external layers (cool better, narrower traces).
IPC2221_K_EXTERNAL = 0.048
#: IPC-2221 current constant — internal layers (hotter, wider traces).
IPC2221_K_INTERNAL = 0.024

#: Provenance string for the PCB reference data above.
PCB_DFM_SOURCE = "JLCPCB capabilities + IPC-2221 trace formula (2026-06-18)"


def ipc2221_trace_width_mm(current_a: float, temp_rise_c: float = 10.0,
                           copper_oz: float = 1.0, *, external: bool = True) -> float:
    """Minimum PCB trace width [mm] for a current, per IPC-2221.

    Inverts ``I = k·ΔT^0.44·A^0.725`` to ``A = (I/(k·ΔT^0.44))^(1/0.725)`` [mil²],
    then ``width = A / (copper_oz · 1.378 mil)``. External layers cool better
    (k=0.048) and need less width than internal (k=0.024). Fail-loud on
    non-positive inputs — a guessed width would be a sourceless fact."""
    if current_a <= 0 or temp_rise_c <= 0 or copper_oz <= 0:
        raise ValueError("ipc2221_trace_width_mm: current_a, temp_rise_c, copper_oz must be > 0")
    k = IPC2221_K_EXTERNAL if external else IPC2221_K_INTERNAL
    area_mil2 = (current_a / (k * temp_rise_c ** 0.44)) ** (1.0 / 0.725)
    width_mil = area_mil2 / (copper_oz * PCB_COPPER_MIL_PER_OZ)
    return width_mil * 0.0254   # mil → mm


def pcb_dfm_gaps() -> list[str]:
    """PCB fab DFM rules that need a routed copper layout the mechanical spec does
    NOT carry. Declared as gaps so the verdict is honestly provisional."""
    return [
        f"PCB: no copper layout in a mechanical solid — the ENTIRE PCB DRC is "
        f"un-evaluable here; the items below are representative ({PCB_DFM_SOURCE})",
        f"PCB: trace width / spacing (fab min {PCB_MIN_TRACE_MM}mm = 5mil at "
        f"{PCB_CAPABILITY_TIER}; shifts with layers & copper weight) not evaluable "
        f"— no copper layout",
        f"PCB: via drill / annular ring (min drill {PCB_MIN_VIA_DRILL_MM}mm, "
        f"recommended {PCB_RECOMMENDED_VIA_DRILL_MM}mm, annular ≥ "
        f"{PCB_MIN_ANNULAR_RING_MM}mm/side, aspect ≤ {PCB_MAX_VIA_ASPECT_RATIO:.0f}:1) "
        f"not evaluable — no via geometry",
        f"PCB: conductor spacing (fab min {PCB_MIN_SPACING_MM}mm; IPC-2221 raises it "
        f"with voltage) not evaluable — no routed geometry",
        f"PCB: copper-to-edge clearance (fab min ~0.2mm trace / {PCB_MIN_COPPER_TO_EDGE_MM}mm "
        f"pad to a milled edge) not evaluable — no board outline vs copper geometry",
        "PCB: trace width from current (IPC-2221) not evaluable — spec carries no "
        "net currents; real DRC needs a Gerber/KiCad layout (electronics-layer seam)",
    ]
