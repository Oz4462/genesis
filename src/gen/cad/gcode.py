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
