"""Printability — the design errors that only show up on the print bed (δ-layer).

The DFM layer (dfm.py) covers the two rules expressible from a wall/hole quantity
(minimum wall, minimum hole); orientation.py covers the 45-degree overhang over the
actual BREP. But most parts that pass those still fail on a real FDM printer, for
reasons the CAD itself never shows: a bridge that sags because it spans too far, a
mating fit that jams because the designed clearance is below what the process can
hold, a pin that snaps because two perimeters cannot form it, a modeled thread the
nozzle cannot resolve, embossed text that fuses into a blob, and — the big one — a
load path running ACROSS the layers, where an FDM part keeps less than half of its
quoted strength. This module encodes those rules as closed-form validators in the
GATE δ-physics pattern (dict with "ok" + a margin, ValueError on nonsense inputs),
so they are auto-selectable from measurand-tagged quantities like every other
physics check.

Encoded rules (FDM/FFF, research verified 2026-06-12 — full write-up with every
failure mode in docs/research/PRINT_DESIGN_FAILURES.md):

  * Unsupported bridge span <= 10 mm prints reliably; beyond it the strands sag.
    (Hydra Research FFF design rules; Xometry FDM design tips; FacFox FDM guideline.)
  * Mating clearance: ~0.2 mm for a loose fit, ~0.1 mm for a tight fit — a designed
    clearance below this jams even when the worst-case tolerance stack is positive,
    because the process itself eats it. (Hydra Research; Xometry.)
  * Pins/bosses: >= 3 mm diameter prints reliably (conservative; Hydra's aggressive
    bound is 1.8 mm = 4 extrusion widths); below 5 mm a base fillet is recommended
    because layer-1 shear snaps unfilleted thin pins. (Forge Labs / FacFox FDM
    design guides; Hydra Research.)
  * Free-standing (unsupported) walls: >= 1.0 mm — thinner tall walls wobble with
    the nozzle and delaminate, a stricter bound than the supported-wall 0.8 mm of
    dfm.py. (FacFox / Forge Labs FDM design guides.)
  * Modeled threads work from M5 up, vertical orientation; below M5 use a heat-set
    insert or cut the thread after printing. (Hydra Research; KingStar/FacFox.)
  * Embossed detail >= 0.9 mm wide, engraved detail >= 0.5 mm wide — below one/two
    extrusion widths the nozzle fuses or skips the feature. (Hydra Research.)
  * Layer adhesion: FDM parts lose > 55 % of tensile strength across the layers
    (Z); a load path across the layers must be checked against the RETAINED
    fraction, conservatively 0.45 of the quoted strength, overridable per measured
    material. (FacFox print-orientation/strength doc; classic Ahn et al. 2002
    anisotropy result for FDM ABS.)

Reference constants that are slicer-/geometry-side knowledge rather than checks
(used by orientation.first_layer_report and the docs): base chamfer ~0.3 mm against
elephant foot; horizontal-hole sag compensation ~0.3 mm (Hydra Research).

Honest boundary: these are process DESIGN rules for standard FDM/FFF with a 0.4 mm
nozzle — necessary, not sufficient. They do not model warping (material-dependent,
no defensible universal threshold — reported as evidence by
orientation.first_layer_report, judged by the human), seam placement, ringing, or
material-specific tuning. A passed printability check means the design does not
violate a known process limit; it does not certify a perfect print.
"""

from __future__ import annotations

import math

#: Longest unsupported horizontal bridge that prints reliably [mm].
FDM_MAX_BRIDGE_MM = 10.0

#: Minimum designed clearance for mating printed parts [mm], by fit kind.
FDM_CLEARANCE_LOOSE_MM = 0.2
FDM_CLEARANCE_TIGHT_MM = 0.1

#: Minimum reliable pin/boss diameter [mm] (conservative across guides).
FDM_MIN_PIN_DIAMETER_MM = 3.0
#: Below this pin diameter a base fillet is recommended against layer-1 shear [mm].
FDM_PIN_FILLET_BELOW_MM = 5.0

#: Minimum free-standing (unsupported) wall thickness [mm] — stricter than the
#: supported-wall minimum of dfm.FDM_MIN_WALL_MM (0.8).
FDM_MIN_UNSUPPORTED_WALL_MM = 1.0

#: Smallest modeled thread that prints usably: M5 major diameter [mm].
FDM_MIN_THREAD_MAJOR_MM = 5.0

#: Minimum embossed / engraved feature width [mm].
FDM_MIN_EMBOSS_WIDTH_MM = 0.9
FDM_MIN_ENGRAVE_WIDTH_MM = 0.5

#: Fraction of the quoted (XY) tensile strength an FDM part RETAINS across the
#: layers (Z) — conservative default from the "> 55 % loss" literature figure.
FDM_Z_STRENGTH_RETENTION = 0.45

#: Recommended base chamfer against elephant-foot bulge [mm] (geometry-side).
FDM_BASE_CHAMFER_MM = 0.3

#: Designed-in diameter compensation for the sag of HORIZONTAL holes [mm]
#: (vertical holes are compensated slicer-side; documented, not a check).
FDM_HORIZONTAL_HOLE_COMPENSATION_MM = 0.3


def bridge_span_check(span: float, max_span: float = FDM_MAX_BRIDGE_MM) -> dict:
    """Unsupported horizontal bridge: does the span print without sagging?

    Returns ``{"span", "max_span", "safety_factor", "ok"}`` with
    safety_factor = max_span / span (inf for a zero span — no bridge at all) and
    ok = span <= max_span. Raises ValueError on a negative span or a non-positive
    max_span (a process limit must be a real length)."""
    if span < 0.0:
        raise ValueError("bridge span must be non-negative")
    if max_span <= 0.0:
        raise ValueError("max bridge span must be positive")
    safety_factor = math.inf if span == 0.0 else max_span / span
    return {
        "span": span,
        "max_span": max_span,
        "safety_factor": safety_factor,
        "ok": span <= max_span,
    }


def fdm_fit_clearance_check(clearance: float, fit: str = "loose") -> dict:
    """Mating-part clearance against the FDM process floor (0.2 loose / 0.1 tight).

    The tolerance layer proves the worst-case stack is positive; THIS check proves
    the designed clearance also clears what the process itself consumes. A negative
    clearance (interference) is meaningful input and simply fails — it does not
    raise. Returns ``{"clearance", "floor", "fit", "safety_factor", "ok"}`` with
    safety_factor = clearance / floor. Raises ValueError on an unknown fit kind."""
    floors = {"loose": FDM_CLEARANCE_LOOSE_MM, "tight": FDM_CLEARANCE_TIGHT_MM}
    floor = floors.get(fit)
    if floor is None:
        raise ValueError(f"unknown fit kind {fit!r} (expected 'loose' or 'tight')")
    safety_factor = clearance / floor
    return {
        "clearance": clearance,
        "floor": floor,
        "fit": fit,
        "safety_factor": safety_factor,
        "ok": clearance >= floor,
    }


def pin_diameter_check(
    diameter: float, min_diameter: float = FDM_MIN_PIN_DIAMETER_MM
) -> dict:
    """Free-standing pin/boss: is it thick enough to print and survive handling?

    Returns ``{"diameter", "min_diameter", "safety_factor", "fillet_recommended",
    "ok"}``: safety_factor = diameter / min_diameter; fillet_recommended is True
    below 5 mm (base fillet against layer-1 shear). Raises ValueError on a
    non-positive diameter or min_diameter."""
    if diameter <= 0.0:
        raise ValueError("pin diameter must be positive")
    if min_diameter <= 0.0:
        raise ValueError("minimum pin diameter must be positive")
    return {
        "diameter": diameter,
        "min_diameter": min_diameter,
        "safety_factor": diameter / min_diameter,
        "fillet_recommended": diameter < FDM_PIN_FILLET_BELOW_MM,
        "ok": diameter >= min_diameter,
    }


def thread_size_check(
    major_diameter: float, min_major: float = FDM_MIN_THREAD_MAJOR_MM
) -> dict:
    """Modeled (printed-in-place) thread: resolvable by the nozzle at all?

    Returns ``{"major_diameter", "min_major", "safety_factor",
    "use_insert_or_tap", "ok"}``: ok from M5 up; below, ``use_insert_or_tap`` is
    True — the honest alternative (heat-set insert, or tap/cut after printing)
    rather than a thread that strips on first use. Raises ValueError on a
    non-positive major diameter or limit."""
    if major_diameter <= 0.0:
        raise ValueError("thread major diameter must be positive")
    if min_major <= 0.0:
        raise ValueError("minimum thread major diameter must be positive")
    ok = major_diameter >= min_major
    return {
        "major_diameter": major_diameter,
        "min_major": min_major,
        "safety_factor": major_diameter / min_major,
        "use_insert_or_tap": not ok,
        "ok": ok,
    }


def unsupported_wall_check(
    thickness: float, min_thickness: float = FDM_MIN_UNSUPPORTED_WALL_MM
) -> dict:
    """Free-standing wall: thick enough not to wobble/delaminate while printing?

    Stricter than the supported-wall rule of dfm.py (1.0 vs 0.8 mm). Returns
    ``{"thickness", "min_thickness", "safety_factor", "ok"}``. Raises ValueError
    on a non-positive thickness or minimum."""
    if thickness <= 0.0:
        raise ValueError("wall thickness must be positive")
    if min_thickness <= 0.0:
        raise ValueError("minimum wall thickness must be positive")
    return {
        "thickness": thickness,
        "min_thickness": min_thickness,
        "safety_factor": thickness / min_thickness,
        "ok": thickness >= min_thickness,
    }


def emboss_detail_check(width: float, kind: str = "emboss") -> dict:
    """Embossed / engraved detail (text, logos): wide enough for the nozzle?

    ``kind`` is "emboss" (raised, >= 0.9 mm — two extrusion widths must fuse into
    a free-standing ridge) or "engrave" (recessed, >= 0.5 mm — the nozzle only has
    to leave a gap). Returns ``{"width", "min_width", "kind", "safety_factor",
    "ok"}``. Raises ValueError on an unknown kind or a non-positive width."""
    minimums = {"emboss": FDM_MIN_EMBOSS_WIDTH_MM, "engrave": FDM_MIN_ENGRAVE_WIDTH_MM}
    min_width = minimums.get(kind)
    if min_width is None:
        raise ValueError(f"unknown detail kind {kind!r} (expected 'emboss' or 'engrave')")
    if width <= 0.0:
        raise ValueError("detail width must be positive")
    return {
        "width": width,
        "min_width": min_width,
        "kind": kind,
        "safety_factor": width / min_width,
        "ok": width >= min_width,
    }


def layer_adhesion_check(
    stress_across_layers: float,
    base_strength: float,
    z_retention: float = FDM_Z_STRENGTH_RETENTION,
) -> dict:
    """Load ACROSS the print layers: checked against the RETAINED strength.

    The single most-missed FDM failure: every static/fatigue validator upstream
    uses the quoted (XY) material strength, but a tensile load path across the
    layers only sees the layer-adhesion strength — conservatively
    ``z_retention * base_strength`` (default 0.45, the "> 55 % loss" literature
    figure; override with a measured value for a qualified material/profile).

    ``stress_across_layers`` is the tensile stress component across the layers
    [MPa]; compression does not delaminate, so a negative value is a modelling
    error and raises (pass the tensile magnitude, not a signed convention).
    Returns ``{"stress_across_layers", "allowed_stress", "z_retention",
    "safety_factor", "ok"}``. Raises ValueError on a negative stress, a
    non-positive base strength, or a retention outside (0, 1]."""
    if stress_across_layers < 0.0:
        raise ValueError(
            "stress across layers must be the tensile magnitude (>= 0); "
            "compression does not delaminate"
        )
    if base_strength <= 0.0:
        raise ValueError("base strength must be positive")
    if not 0.0 < z_retention <= 1.0:
        raise ValueError("z_retention must be in (0, 1]")
    allowed = z_retention * base_strength
    safety_factor = (
        math.inf if stress_across_layers == 0.0 else allowed / stress_across_layers
    )
    return {
        "stress_across_layers": stress_across_layers,
        "allowed_stress": allowed,
        "z_retention": z_retention,
        "safety_factor": safety_factor,
        "ok": safety_factor >= 1.0,
    }
