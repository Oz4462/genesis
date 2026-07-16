"""gcode — real, verified G-code generation for a 2.5D outside profile (Stein 5).

The Fertigungs layer carried a prose "datei_stub" ("…FDM_tether_anchor.gcode
(stub: …)") — a description, not a program. This module emits a REAL program and,
crucially, VERIFIES it: GENESIS treats verification as a gate, so a generator
without a checker is half a feature.

Scope honesty: only a 2.5D OUTSIDE-PROFILE contour of a rectangular footprint is
generated — a valid, runnable program that cuts a blank to the part's outline. The
toolpath is offset OUTWARD by the tool radius (explicit geometry, not machine
cutter-comp, so every coordinate is checkable) and stepped down in passes. What a
real part also needs — internal pockets/holes, the true 2D profile, 3D toolpaths,
and FDM print slicing — needs a CAM kernel / slicer GENESIS does not have, and is
declared as a gap, never faked. Feeds & speeds are material+tool specific; the
defaults are STATED ASSUMPTIONS, not a feeds-and-speeds calculation.

The G-code STRUCTURE is the standard (RS-274 / ISO 6983-1, 1980): G21 mm, G90
absolute, G17 XY plane, G0 rapid, G1 feed, M3/M4 spindle on, M5 off, M30 end.
Refs: ISO 6983-1; G-code (Wikipedia); RS-274 reference (PythonicGcodeMachine).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

#: Standard structural codes (RS-274 / ISO 6983) — the program's skeleton.
GCODE_SOURCE = "RS-274 / ISO 6983-1 G-code structure (2026-06-18)"

#: Stated feed/speed/geometry ASSUMPTIONS (conservative generic defaults, NOT a
#: feeds-and-speeds calculation — those are material + tool specific, a gap).
GCODE_DEFAULT_TOOL_DIAMETER_MM = 3.0
GCODE_DEFAULT_CUT_FEED_MM_MIN = 300.0
GCODE_DEFAULT_PLUNGE_FEED_MM_MIN = 100.0
GCODE_DEFAULT_STEPDOWN_MM = 1.0
GCODE_DEFAULT_SAFE_Z_MM = 5.0
GCODE_DEFAULT_SPINDLE_RPM = 10000

_WORD_RE = re.compile(r"([A-Za-z])\s*(-?\d+(?:\.\d+)?)")
_KNOWN_LETTERS = set("GMXYZFSTN")


@dataclass(frozen=True)
class GCodeProgram:
    """A generated program: its lines plus the metadata a verifier/consumer needs."""

    operation: str
    lines: list[str]
    bounds_mm: dict[str, tuple[float, float]]   # {"x": (min,max), "y": ..., "z": ...}
    safe_z_mm: float
    assumptions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    source: str | None = None

    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class GCodeCheck:
    """Verifier verdict — ok plus the concrete issues (empty when ok)."""

    ok: bool
    issues: list[str]
    n_moves: int
    bounds_mm: dict[str, tuple[float, float]]


def generate_profile_gcode(
    width_mm: float, height_mm: float, depth_mm: float, *,
    tool_diameter_mm: float = GCODE_DEFAULT_TOOL_DIAMETER_MM,
    cut_feed_mm_min: float = GCODE_DEFAULT_CUT_FEED_MM_MIN,
    plunge_feed_mm_min: float = GCODE_DEFAULT_PLUNGE_FEED_MM_MIN,
    stepdown_mm: float = GCODE_DEFAULT_STEPDOWN_MM,
    safe_z_mm: float = GCODE_DEFAULT_SAFE_Z_MM,
    spindle_rpm: int = GCODE_DEFAULT_SPINDLE_RPM,
) -> GCodeProgram:
    """Emit a 2.5D outside-profile program for a `width_mm` x `height_mm` footprint
    cut to `depth_mm`. The path is offset outward by the tool radius and stepped
    down by `stepdown_mm` per pass. Fail-loud on any non-finite / non-positive
    dimension (a guessed program is worse than an honest refusal)."""
    for name, v in (("width", width_mm), ("height", height_mm), ("depth", depth_mm),
                    ("tool_diameter", tool_diameter_mm), ("stepdown", stepdown_mm),
                    ("safe_z", safe_z_mm)):
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"generate_profile_gcode: {name} must be a finite value > 0")
    # feeds / rpm must be >= 1: a sub-1 value is physically meaningless AND would
    # round to an invalid F0 / S0 in the emitted program.
    for name, v in (("cut_feed", cut_feed_mm_min), ("plunge_feed", plunge_feed_mm_min),
                    ("spindle_rpm", spindle_rpm)):
        if not math.isfinite(v) or v < 1:
            raise ValueError(f"generate_profile_gcode: {name} must be a finite value >= 1")

    r = tool_diameter_mm / 2.0
    x0, y0 = -r, -r                       # outside-profile path: offset outward by r
    x1, y1 = width_mm + r, height_mm + r

    def fmt(v: float) -> str:
        return f"{v:.3f}".rstrip("0").rstrip(".")

    lines = [
        f"( outside-profile {fmt(width_mm)}x{fmt(height_mm)}mm, depth {fmt(depth_mm)}mm, "
        f"tool d={fmt(tool_diameter_mm)}mm; {GCODE_SOURCE} )",
        "G21 ( units: millimeters )",
        "G90 ( absolute positioning )",
        "G17 ( XY plane )",
        f"M3 S{int(spindle_rpm)} ( spindle on, clockwise )",
        f"G0 Z{fmt(safe_z_mm)} ( retract to safe height )",
        f"G0 X{fmt(x0)} Y{fmt(y0)} ( rapid to start, above stock )",
    ]

    # stepped-down passes, each cutting the full rectangle, until the target depth
    z = 0.0
    while z > -depth_mm + 1e-9:
        z = max(z - stepdown_mm, -depth_mm)
        lines.append(f"G1 Z{fmt(z)} F{fmt(plunge_feed_mm_min)} ( plunge )")
        lines.append(f"G1 X{fmt(x1)} Y{fmt(y0)} F{fmt(cut_feed_mm_min)}")
        lines.append(f"G1 X{fmt(x1)} Y{fmt(y1)}")
        lines.append(f"G1 X{fmt(x0)} Y{fmt(y1)}")
        lines.append(f"G1 X{fmt(x0)} Y{fmt(y0)} ( close the contour )")

    lines += [
        f"G0 Z{fmt(safe_z_mm)} ( retract )",
        "M5 ( spindle off )",
        "M30 ( program end )",
    ]

    return GCodeProgram(
        operation="outside_profile",
        lines=lines,
        bounds_mm={"x": (x0, x1), "y": (y0, y1), "z": (-depth_mm, safe_z_mm)},
        safe_z_mm=safe_z_mm,
        assumptions=[
            f"tool d={fmt(tool_diameter_mm)}mm, stepdown {fmt(stepdown_mm)}mm, safe Z "
            f"{fmt(safe_z_mm)}mm; feeds cut {fmt(cut_feed_mm_min)} / plunge "
            f"{fmt(plunge_feed_mm_min)} mm/min, spindle {int(spindle_rpm)} rpm — "
            f"GENERIC defaults, not a feeds-and-speeds calculation",
            f"outside profile: stock must be >= {fmt(width_mm + tool_diameter_mm)} x "
            f"{fmt(height_mm + tool_diameter_mm)}mm (part + tool clearance)",
        ],
        gaps=[
            "internal features (pockets, holes, slots) and the true 2D profile: not "
            "generated — need the real part outline + a CAM kernel",
            "feeds & speeds: material + tool specific — supply a real feeds/speeds calc",
            "3D toolpaths and FDM print slicing (per-layer paths): need a CAM kernel / slicer",
            "work-offset (G54) zeroing, tool length offset and clamping/fixturing: setup-specific",
        ],
        source=GCODE_SOURCE,
    )


def generate_rect_pocket_gcode(
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    *,
    tool_diameter_mm: float = GCODE_DEFAULT_TOOL_DIAMETER_MM,
    cut_feed_mm_min: float = GCODE_DEFAULT_CUT_FEED_MM_MIN,
    plunge_feed_mm_min: float = GCODE_DEFAULT_PLUNGE_FEED_MM_MIN,
    stepdown_mm: float = GCODE_DEFAULT_STEPDOWN_MM,
    stepover_mm: float | None = None,
    safe_z_mm: float = GCODE_DEFAULT_SAFE_Z_MM,
    spindle_rpm: int = GCODE_DEFAULT_SPINDLE_RPM,
) -> GCodeProgram:
    """Rectangular pocket: clear the interior of a ``width_mm`` × ``height_mm`` cavity
    to ``depth_mm`` with zigzag passes (tool diameter inset from walls).

    This is the real program the humanoid/AETHON pipeline expects for a joint-bore
    pocket sample (was missing → AttributeError skip). Scope honesty: rectangular
    flat-floor pocket only — not freeform 3D CAM, not drill cycles for round bores.
    """
    for name, v in (
        ("width", width_mm),
        ("height", height_mm),
        ("depth", depth_mm),
        ("tool_diameter", tool_diameter_mm),
        ("stepdown", stepdown_mm),
        ("safe_z", safe_z_mm),
    ):
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"generate_rect_pocket_gcode: {name} must be a finite value > 0")
    for name, v in (
        ("cut_feed", cut_feed_mm_min),
        ("plunge_feed", plunge_feed_mm_min),
        ("spindle_rpm", spindle_rpm),
    ):
        if not math.isfinite(v) or v < 1:
            raise ValueError(f"generate_rect_pocket_gcode: {name} must be a finite value >= 1")

    r = tool_diameter_mm / 2.0
    # usable floor after wall clearance (tool centre stays ≥ r from walls)
    floor_w = width_mm - 2.0 * r
    floor_h = height_mm - 2.0 * r
    if floor_w <= 0 or floor_h <= 0:
        raise ValueError(
            f"generate_rect_pocket_gcode: pocket {width_mm}x{height_mm} mm is smaller "
            f"than tool diameter {tool_diameter_mm} mm (no room for a pocket path)"
        )
    so = stepover_mm if stepover_mm is not None else tool_diameter_mm * 0.4
    if not math.isfinite(so) or so <= 0:
        raise ValueError("generate_rect_pocket_gcode: stepover_mm must be a finite value > 0")
    so = min(so, floor_h)  # at least one pass along Y

    def fmt(v: float) -> str:
        return f"{v:.3f}".rstrip("0").rstrip(".")

    # tool-centre limits (origin at pocket corner, Z=0 stock top)
    x0, x1 = r, width_mm - r
    y0, y1 = r, height_mm - r

    # Y-raster lines
    y_lines: list[float] = []
    y = y0
    while y < y1 - 1e-9:
        y_lines.append(y)
        y += so
    if not y_lines or abs(y_lines[-1] - y1) > 1e-6:
        y_lines.append(y1)

    lines = [
        f"( rectangular pocket {fmt(width_mm)}x{fmt(height_mm)}mm, depth {fmt(depth_mm)}mm, "
        f"tool d={fmt(tool_diameter_mm)}mm; {GCODE_SOURCE} )",
        "G21 ( units: millimeters )",
        "G90 ( absolute positioning )",
        "G17 ( XY plane )",
        f"M3 S{int(spindle_rpm)} ( spindle on, clockwise )",
        f"G0 Z{fmt(safe_z_mm)} ( retract to safe height )",
        f"G0 X{fmt(x0)} Y{fmt(y0)} ( rapid to pocket start )",
    ]

    z = 0.0
    while z > -depth_mm + 1e-9:
        z = max(z - stepdown_mm, -depth_mm)
        lines.append(f"G1 Z{fmt(z)} F{fmt(plunge_feed_mm_min)} ( plunge to pass depth )")
        # zigzag clear
        for i, y in enumerate(y_lines):
            lines.append(f"G1 Y{fmt(y)} F{fmt(cut_feed_mm_min)}")
            if i % 2 == 0:
                lines.append(f"G1 X{fmt(x1)}")
            else:
                lines.append(f"G1 X{fmt(x0)}")
        # finish contour at floor of this pass (wall cleanup)
        lines.append(f"G1 X{fmt(x0)} Y{fmt(y0)} F{fmt(cut_feed_mm_min)} ( return for wall pass )")
        lines.append(f"G1 X{fmt(x1)} Y{fmt(y0)}")
        lines.append(f"G1 X{fmt(x1)} Y{fmt(y1)}")
        lines.append(f"G1 X{fmt(x0)} Y{fmt(y1)}")
        lines.append(f"G1 X{fmt(x0)} Y{fmt(y0)} ( close wall )")

    lines += [
        f"G0 Z{fmt(safe_z_mm)} ( retract )",
        "M5 ( spindle off )",
        "M30 ( program end )",
    ]

    return GCodeProgram(
        operation="rectangular_pocket",
        lines=lines,
        # bounds = tool-centre envelope (what the verifier compares motion against)
        bounds_mm={"x": (x0, x1), "y": (y0, y1), "z": (-depth_mm, safe_z_mm)},
        safe_z_mm=safe_z_mm,
        assumptions=[
            f"tool d={fmt(tool_diameter_mm)}mm, stepover {fmt(so)}mm, stepdown {fmt(stepdown_mm)}mm; "
            f"feeds cut {fmt(cut_feed_mm_min)} / plunge {fmt(plunge_feed_mm_min)} mm/min, "
            f"spindle {int(spindle_rpm)} rpm — GENERIC defaults",
            "rectangular flat-floor pocket; tool centre inset by tool radius from walls",
            f"stock pocket envelope {fmt(width_mm)}x{fmt(height_mm)} mm (tool path inset)",
        ],
        gaps=[
            "round bore / helical drill: not generated — use a drill cycle or 3D CAM",
            "feeds & speeds: material + tool specific",
            "work-offset (G54), tool length offset, fixturing: setup-specific",
        ],
        source=GCODE_SOURCE,
    )


def generate_face_mill_gcode(
    width_mm: float,
    height_mm: float,
    *,
    face_depth_mm: float = 0.5,
    tool_diameter_mm: float = GCODE_DEFAULT_TOOL_DIAMETER_MM,
    cut_feed_mm_min: float = GCODE_DEFAULT_CUT_FEED_MM_MIN,
    plunge_feed_mm_min: float = GCODE_DEFAULT_PLUNGE_FEED_MM_MIN,
    stepover_mm: float | None = None,
    safe_z_mm: float = GCODE_DEFAULT_SAFE_Z_MM,
    spindle_rpm: int = GCODE_DEFAULT_SPINDLE_RPM,
) -> GCodeProgram:
    """C4: face-mill the top of a rectangular stock (single Z depth, raster XY).

    Removes ``face_depth_mm`` from the stock top with zig-zag passes. Scope: flat
    facing only — not 3D sculpting, not multi-axis. Feeds are stated assumptions.
    """
    for name, v in (
        ("width", width_mm),
        ("height", height_mm),
        ("face_depth", face_depth_mm),
        ("tool_diameter", tool_diameter_mm),
        ("safe_z", safe_z_mm),
    ):
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"generate_face_mill_gcode: {name} must be a finite value > 0")
    for name, v in (
        ("cut_feed", cut_feed_mm_min),
        ("plunge_feed", plunge_feed_mm_min),
        ("spindle_rpm", spindle_rpm),
    ):
        if not math.isfinite(v) or v < 1:
            raise ValueError(f"generate_face_mill_gcode: {name} must be a finite value >= 1")

    r = tool_diameter_mm / 2.0
    so = stepover_mm if stepover_mm is not None else tool_diameter_mm * 0.6
    if not math.isfinite(so) or so <= 0:
        raise ValueError("generate_face_mill_gcode: stepover_mm must be a finite value > 0")
    so = min(so, height_mm)

    def fmt(v: float) -> str:
        return f"{v:.3f}".rstrip("0").rstrip(".")

    # tool centre from 0..width, 0..height (stock XY), start at -r for edge clean
    x0, x1 = -r, width_mm + r
    y0, y1 = 0.0, height_mm

    y_lines: list[float] = []
    y = y0
    while y < y1 - 1e-9:
        y_lines.append(y)
        y += so
    if not y_lines or abs(y_lines[-1] - y1) > 1e-6:
        y_lines.append(y1)

    z_face = -face_depth_mm
    lines = [
        f"( face-mill {fmt(width_mm)}x{fmt(height_mm)}mm, depth {fmt(face_depth_mm)}mm, "
        f"tool d={fmt(tool_diameter_mm)}mm; {GCODE_SOURCE} )",
        "G21 ( units: millimeters )",
        "G90 ( absolute positioning )",
        "G17 ( XY plane )",
        f"M3 S{int(spindle_rpm)} ( spindle on, clockwise )",
        f"G0 Z{fmt(safe_z_mm)} ( retract to safe height )",
        f"G0 X{fmt(x0)} Y{fmt(y0)} ( rapid to start )",
        f"G1 Z{fmt(z_face)} F{fmt(plunge_feed_mm_min)} ( plunge to face depth )",
    ]
    for i, y in enumerate(y_lines):
        lines.append(f"G1 Y{fmt(y)} F{fmt(cut_feed_mm_min)}")
        if i % 2 == 0:
            lines.append(f"G1 X{fmt(x1)}")
        else:
            lines.append(f"G1 X{fmt(x0)}")
    lines += [
        f"G0 Z{fmt(safe_z_mm)} ( retract )",
        "M5 ( spindle off )",
        "M30 ( program end )",
    ]

    return GCodeProgram(
        operation="face_mill",
        lines=lines,
        bounds_mm={"x": (x0, x1), "y": (min(y0, y1), max(y0, y1)), "z": (z_face, safe_z_mm)},
        safe_z_mm=safe_z_mm,
        assumptions=[
            f"face depth {fmt(face_depth_mm)}mm, stepover {fmt(so)}mm, tool d={fmt(tool_diameter_mm)}mm",
            f"feeds cut {fmt(cut_feed_mm_min)} / plunge {fmt(plunge_feed_mm_min)} mm/min, "
            f"spindle {int(spindle_rpm)} rpm — GENERIC defaults",
            "flat facing only — stock top assumed Z=0",
        ],
        gaps=[
            "adaptive clearing / 3D surface facing: need a CAM kernel",
            "feeds & speeds material-specific",
            "work-offset (G54), tool length offset, fixturing: setup-specific",
        ],
        source=GCODE_SOURCE,
    )


#: Ops GENESIS can emit as verified 2.5D RS-274 (H2 inventory).
GCODE_SUPPORTED_OPS: tuple[str, ...] = (
    "outside_profile",
    "rectangular_pocket",
    "face_mill",
    "helical_bore",
)


def multi_axis_cam_capability() -> dict:
    """H2: honest multi-axis / freeform CAM status — never claims 5-axis capability.

    Returns a structured capability dict for package MANIFEST / CAM section.
    ``supported`` is always False until a real multi-axis kernel is wired.
    """
    return {
        "supported": False,
        "level": "L2",  # 2.5D ops exist and verify; multi-axis does not
        "ops_available": list(GCODE_SUPPORTED_OPS),
        "axes": "3-axis 2.5D (XY motion + stepped Z); no simultaneous multi-axis",
        "gaps": [
            "simultaneous 4/5-axis toolpaths not generated",
            "freeform 3D surface finishing / adaptive clearing needs a CAM kernel",
            "turning (lathe) programs not generated",
            "FDM per-layer slicer G-code not generated",
        ],
        "quelle": "gen.cad.gcode.multi_axis_cam_capability",
    }


def refuse_multi_axis_toolpath(*, context: str = "") -> None:
    """H2: loud refusal for multi-axis freeform requests — never emit a fake 5-axis program.

    Raises ``ValueError`` with capability summary. Call sites must not catch-and-fabricate.
    """
    cap = multi_axis_cam_capability()
    msg = (
        "multi-axis / freeform CAM is not supported by GENESIS gcode "
        f"(ops available: {', '.join(cap['ops_available'])}). "
        f"Gaps: {'; '.join(cap['gaps'][:2])}."
    )
    if context:
        msg = f"{context}: {msg}"
    raise ValueError(msg)


def generate_helical_bore_gcode(
    diameter_mm: float,
    depth_mm: float,
    *,
    center_x_mm: float = 0.0,
    center_y_mm: float = 0.0,
    tool_diameter_mm: float = GCODE_DEFAULT_TOOL_DIAMETER_MM,
    cut_feed_mm_min: float = GCODE_DEFAULT_CUT_FEED_MM_MIN,
    plunge_feed_mm_min: float = GCODE_DEFAULT_PLUNGE_FEED_MM_MIN,
    pitch_mm: float | None = None,
    safe_z_mm: float = GCODE_DEFAULT_SAFE_Z_MM,
    spindle_rpm: int = GCODE_DEFAULT_SPINDLE_RPM,
    segments_per_turn: int = 36,
) -> GCodeProgram:
    """H2: helical bore — circle while descending (G1-linearised helix), then floor clean.

    Opens a round hole of ``diameter_mm`` to ``depth_mm`` with the tool centre on a
    helix of radius ``(diameter − tool_d) / 2``. Uses G1 chord segments (not G2/G3)
    so ``verify_gcode`` can bound every coordinate without arc math.

    Scope honesty: 3-axis helical roughing only — not multi-axis freeform, not a
    canned G81/G83 drill cycle, not a reamed finish pass. Tool must fit strictly
    inside the bore (path radius > 0).
    """
    for name, v in (
        ("diameter", diameter_mm),
        ("depth", depth_mm),
        ("tool_diameter", tool_diameter_mm),
        ("safe_z", safe_z_mm),
    ):
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"generate_helical_bore_gcode: {name} must be a finite value > 0")
    for name, v in (
        ("center_x", center_x_mm),
        ("center_y", center_y_mm),
    ):
        if not math.isfinite(v):
            raise ValueError(f"generate_helical_bore_gcode: {name} must be finite")
    for name, v in (
        ("cut_feed", cut_feed_mm_min),
        ("plunge_feed", plunge_feed_mm_min),
        ("spindle_rpm", spindle_rpm),
    ):
        if not math.isfinite(v) or v < 1:
            raise ValueError(f"generate_helical_bore_gcode: {name} must be a finite value >= 1")
    if not isinstance(segments_per_turn, int) or segments_per_turn < 8:
        raise ValueError(
            "generate_helical_bore_gcode: segments_per_turn must be an int >= 8"
        )

    path_r = (diameter_mm - tool_diameter_mm) / 2.0
    if path_r <= 1e-9:
        raise ValueError(
            f"generate_helical_bore_gcode: bore diameter {diameter_mm} mm must exceed "
            f"tool diameter {tool_diameter_mm} mm (path radius would be {path_r})"
        )
    pitch = pitch_mm if pitch_mm is not None else GCODE_DEFAULT_STEPDOWN_MM
    if not math.isfinite(pitch) or pitch <= 0:
        raise ValueError("generate_helical_bore_gcode: pitch_mm must be a finite value > 0")
    # cap pitch so we always get at least one full turn of engagement for deep holes
    pitch = min(pitch, depth_mm)

    def fmt(v: float) -> str:
        return f"{v:.3f}".rstrip("0").rstrip(".")

    def q3(v: float) -> float:
        """Quantize to the same 3-decimal emission used in G-code words (bounds match)."""
        s = fmt(v)
        return float(s) if s not in ("", "-", "+") else 0.0

    n_turns = depth_mm / pitch
    total_segments = int(math.ceil(n_turns * segments_per_turn))
    # ensure we land exactly at -depth_mm on the last helix sample
    total_segments = max(total_segments, segments_per_turn)

    cx, cy = center_x_mm, center_y_mm
    # start at angle 0 on the circle at Z=safe, then plunge to Z=0 at entry point
    x_entry = q3(cx + path_r)
    y_entry = q3(cy)
    z_safe = q3(safe_z_mm)
    z_floor = q3(-depth_mm)

    lines = [
        f"( helical-bore d={fmt(diameter_mm)}mm depth={fmt(depth_mm)}mm "
        f"center=({fmt(cx)},{fmt(cy)}) tool d={fmt(tool_diameter_mm)}mm; {GCODE_SOURCE} )",
        "G21 ( units: millimeters )",
        "G90 ( absolute positioning )",
        "G17 ( XY plane )",
        f"M3 S{int(spindle_rpm)} ( spindle on, clockwise )",
        f"G0 Z{fmt(z_safe)} ( retract to safe height )",
        f"G0 X{fmt(x_entry)} Y{fmt(y_entry)} ( rapid to helix entry )",
        f"G1 Z0 F{fmt(plunge_feed_mm_min)} ( approach stock top )",
    ]

    xs: list[float] = [x_entry]
    ys: list[float] = [y_entry]
    zs: list[float] = [z_safe, 0.0]

    for i in range(1, total_segments + 1):
        t_turns = (i / segments_per_turn)
        angle = 2.0 * math.pi * t_turns
        z = max(-depth_mm, -pitch * t_turns)
        if i == total_segments:
            z = -depth_mm
        x = q3(cx + path_r * math.cos(angle))
        y = q3(cy + path_r * math.sin(angle))
        z = q3(z)
        lines.append(
            f"G1 X{fmt(x)} Y{fmt(y)} Z{fmt(z)} F{fmt(cut_feed_mm_min)}"
        )
        xs.append(x)
        ys.append(y)
        zs.append(z)

    # one full cleanup circle at floor depth (constant Z)
    for i in range(1, segments_per_turn + 1):
        angle = 2.0 * math.pi * (i / segments_per_turn)
        x = q3(cx + path_r * math.cos(angle))
        y = q3(cy + path_r * math.sin(angle))
        lines.append(
            f"G1 X{fmt(x)} Y{fmt(y)} Z{fmt(z_floor)} F{fmt(cut_feed_mm_min)}"
        )
        xs.append(x)
        ys.append(y)
        zs.append(z_floor)

    lines += [
        f"G0 Z{fmt(z_safe)} ( retract )",
        "M5 ( spindle off )",
        "M30 ( program end )",
    ]
    zs.append(z_safe)

    # bounds from quantized coordinates so verify_gcode declared==actual
    return GCodeProgram(
        operation="helical_bore",
        lines=lines,
        bounds_mm={
            "x": (min(xs), max(xs)),
            "y": (min(ys), max(ys)),
            "z": (min(zs), max(zs)),
        },
        safe_z_mm=safe_z_mm,
        assumptions=[
            f"helical bore path_r={fmt(path_r)}mm, pitch={fmt(pitch)}mm, "
            f"{segments_per_turn} G1 segments/turn",
            f"feeds cut {fmt(cut_feed_mm_min)} / approach {fmt(plunge_feed_mm_min)} mm/min, "
            f"spindle {int(spindle_rpm)} rpm — GENERIC defaults",
            "linearised helix (G1 chords) — not G2/G3 arc interpolation",
        ],
        gaps=[
            "multi-axis freeform / 5-axis: not generated (see multi_axis_cam_capability)",
            "canned drill cycles (G81/G83) and ream finish passes: not generated",
            "feeds & speeds material-specific",
            "work-offset (G54), tool length offset, fixturing: setup-specific",
        ],
        source=GCODE_SOURCE,
    )


def _parse_words(raw: str) -> dict[str, float] | None:
    """Parse one line into {letter: value}, stripping comments. Returns None for a
    blank/comment-only line, or raises nothing — unknown letters are reported by the
    caller via the returned dict containing them."""
    # strip ( … ) comments and ; trailing comments
    line = re.sub(r"\([^)]*\)", "", raw)
    line = line.split(";", 1)[0].strip()
    if not line:
        return None
    return {letter.upper(): float(num) for letter, num in _WORD_RE.findall(line)}


def verify_gcode(program: GCodeProgram | list[str] | str, *,
                 envelope_mm: dict[str, tuple[float, float]] | None = None) -> GCodeCheck:
    """Verify a program is valid RS-274, spindle-safe, bounded and gouge-free.

    Checks: units (G21) + absolute (G90) set before the first motion; spindle on
    (M3/M4) before the first feed cut and off (M5) by the end; M30 ends it; no rapid
    (G0) lateral move while below the stock top (gouge); every coordinate inside the
    declared bounds (and `envelope_mm` if given). Non-vacuous: a broken program
    fails. Accepts a GCodeProgram, a list of lines, or raw text."""
    if isinstance(program, GCodeProgram):
        raw_lines = program.lines
        declared = program.bounds_mm
    else:
        raw_lines = program.splitlines() if isinstance(program, str) else list(program)
        declared = None

    issues: list[str] = []
    units_set = abs_set = spindle_on = spindle_off = ended = False
    first_motion_seen = False
    cur = {"X": 0.0, "Y": 0.0, "Z": 0.0}
    seen: dict[str, list[float]] = {"X": [], "Y": [], "Z": []}
    f_value: float | None = None        # modal feed rate (must be set & > 0 for a cut)
    s_value: float | None = None        # modal spindle speed (must be set for M3/M4)
    n_moves = 0

    for raw in raw_lines:
        words = _parse_words(raw)
        if words is None:
            continue
        unknown = [k for k in words if k not in _KNOWN_LETTERS]
        if unknown:
            issues.append(f"unknown word(s) {unknown} in: {raw.strip()!r}")
        if ended:
            issues.append(f"command after M30 (program end): {raw.strip()!r}")
        if "S" in words:
            s_value = words["S"]
        if "F" in words:
            f_value = words["F"]

        if "G" in words:
            g = int(words["G"])
            if g == 21:
                units_set = True
            elif g == 90:
                abs_set = True
            elif g in (0, 1):
                first_motion_seen = True
                if not (units_set and abs_set):
                    issues.append(f"motion before G21/G90 set: {raw.strip()!r}")
                lateral = any(a in words for a in ("X", "Y"))
                for a in ("X", "Y", "Z"):
                    if a in words:
                        cur[a] = words[a]
                        seen[a].append(words[a])
                n_moves += 1
                if g == 1:
                    if not spindle_on:
                        issues.append(f"feed cut (G1) before spindle on: {raw.strip()!r}")
                    if f_value is None or f_value <= 0:
                        issues.append(f"feed move (G1) with no feed rate F set: {raw.strip()!r}")
                if g == 0 and lateral and cur["Z"] < -1e-9:
                    issues.append(f"rapid (G0) lateral move below stock top — gouge: {raw.strip()!r}")
                if g == 0 and "Z" in words and words["Z"] < -1e-9:
                    issues.append(f"rapid (G0) plunge into material (Z<0) — gouge: {raw.strip()!r}")
        if "M" in words:
            mcode = int(words["M"])
            if mcode in (3, 4):
                if s_value is None or s_value <= 0:
                    issues.append(f"spindle on (M3/M4) without a spindle speed S: {raw.strip()!r}")
                else:
                    spindle_on = True
            elif mcode == 5:
                spindle_off = True
                spindle_on = False        # a cut after M5 must be caught, not pass
                if cur["Z"] < -1e-9:
                    issues.append("spindle stopped (M5) with the tool still in material — no retract")
            elif mcode == 30:
                ended = True

    if not first_motion_seen:
        issues.append("program has no motion (G0/G1)")
    # (a cut while the spindle is off is caught per-move above — whether it was never
    #  started or already stopped by M5; no end-of-program spindle_on check, which
    #  would false-fire on the correct M5-before-M30 shutdown.)
    if not spindle_off:
        issues.append("spindle never stopped (missing M5)")
    if not ended:
        issues.append("program does not end (missing M30)")
    if ended and cur["Z"] < -1e-9:
        issues.append("program ends with the tool in material (no final retract)")

    bounds: dict[str, tuple[float, float]] = {}
    for a in ("X", "Y", "Z"):
        bounds[a.lower()] = (min(seen[a]), max(seen[a])) if seen[a] else (0.0, 0.0)
    # declared bounds must match what the toolpath actually does (axes it moved)
    if declared is not None:
        for axis in ("x", "y", "z"):
            if not seen[axis.upper()]:
                continue
            dlo, dhi = declared[axis]
            alo, ahi = bounds[axis]
            if abs(dlo - alo) > 1e-6 or abs(dhi - ahi) > 1e-6:
                issues.append(f"declared {axis}-bounds {(dlo, dhi)} != actual {(alo, ahi)}")
    if envelope_mm is not None:
        for axis in ("x", "y", "z"):
            elo, ehi = envelope_mm[axis]
            alo, ahi = bounds[axis]
            if alo < elo - 1e-6 or ahi > ehi + 1e-6:
                issues.append(f"{axis}-toolpath {(alo, ahi)} outside envelope {(elo, ehi)}")

    return GCodeCheck(ok=not issues, issues=issues, n_moves=n_moves, bounds_mm=bounds)
