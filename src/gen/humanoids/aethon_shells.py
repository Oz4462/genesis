"""aethon_shells — generate AETHON's HARD-SURFACE per-segment exo-shell meshes with CadQuery.

This module is the geometry generator for AETHON's *visual* skin. It builds GENUINE designed-robot
covers — per-segment, hard-surface SHELLED parts (NOT smooth merged tubes): each limb member is a
profiled, non-round (slab / D-section) cover with panel parting seams, a framed front panel and
RECESSED end-cuffs where the real actuators seat; the torso is a real chest+back cuirass (sternum +
spine channels, shoulder yokes, pectoral panel split); the head is a faceted cranium with a FLUSH
visor band and side sensor pods. The INDUSTRIAL mechanics (the real off-the-shelf joint actuators
— CubeMars AK80-64 / AK70-10, MyActuator RMD-X10 / X6, Jetson, OAK-D) stay EXPOSED at the joints,
mounted by the URDF as separate visuals BETWEEN these covers — exposed actuators between shelled
segments is the defining "real designed robot" cue (the Booster T1 / Apollo look).

The shells are VISUAL ONLY: the URDF collision geometry, masses and inertias are untouched, so the
validated physics (mass / DOF / actuators / FEM / the 5 s stand / GATE γ + δ) are byte-identical to
the unstyled robot — exactly as the earlier smooth shells were visual-only.

CadQuery (OCCT B-rep: ``loft``/``intersect``/``cut``/``fillet``/``union``) is NOT installed in the
Genesis main venv (numpy-incompatible). It lives in a SEPARATE venv ``/home/genesis/.venv-cad``.
Therefore this file is executed as a SUBPROCESS by that interpreter (``genesis_humanoid.build_shells``),
never imported into the main venv. It writes one binary STL per shell into ``out_dir`` and prints a
JSON manifest.

Run standalone:  /home/genesis/.venv-cad/bin/python -m gen.humanoids.aethon_shells <out_dir>
  (or)           /home/genesis/.venv-cad/bin/python aethon_shells.py <out_dir>

KEY HARD-SURFACE TECHNIQUE (vetted on this box):
  * A clean ``.ellipse()`` loft gives the muscle TAPER and a clean tessellation; INTERSECTING it with a
    filleted ``box`` (depth < width) carves it into a FLAT-FACETED slab/D cross-section — a hard-surface
    cover, not a tube. (A raw superellipse ``polyline`` loft tessellates with sliver non-manifold edges;
    the ellipse∩box keeps the part WATERTIGHT.)
  * Panel parting seams, front-panel border grooves and end-cuff rebates are booleaned IN with ``.cut``
    (they stay inside the solid → watertight); raised ribs use ``.union`` (never opens the solid).
    NOTHING is floated beside the body (the earlier greeble glitch); all detail is part of the solid.
  * Fillets on a boolean result can make OCCT refuse — ``_safe_fillet`` backs the radius off then skips
    (a missing fillet is cosmetic, never a crash).

Units are MILLIMETRES (matching the spec geometry); the URDF scales by 0.001 to SI. Limb covers run
along local -Z (URDF limbs extend down -Z) with the cover TOP at z=0, so the URDF mounts each with a
simple z-offset and the exposed actuator shows through the recessed end-cuff. The face/front of the
torso, head and foot is +X (the side the toes point), matching the URDF eye/camera/foot placement.
Deterministic: same inputs → identical meshes.
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys

#: Documented minimum wall thickness for any AETHON exo-shell that is hollowed [mm]. Most VISUAL shells
#: are left SOLID (a visual mesh has no print-hollow requirement; a solid is trivially watertight and
#: avoids fragile/expensive OCCT ``.shell()`` over boolean-cut solids), but this floor is honoured wherever
#: a shell IS hollowed and is exported for the printable-bundle contract.
MIN_WALL_MM: float = 1.2

#: STL export tessellation tolerance (mm) / angular tolerance (rad). Finer than the OCCT default so the
#: flat facets and panel seams read crisply in the render without exploding triangle counts.
_STL_TOL: float = 0.04
_STL_ANG: float = 0.08

# CadQuery lives in the isolated .venv-cad only (numpy conflict in the main genesis venv). We do NOT
# SystemExit at import time so pure constants (MIN_WALL_MM) and SHELLS keys can be inspected without the
# kernel; build fns fail loud on use when cad is unavailable (no silent bad geometry).
_CAD_AVAILABLE = False
try:
    import cadquery as cq
    from cadquery import exporters
    _CAD_AVAILABLE = True
except Exception:  # pragma: no cover - only meaningful inside .venv-cad
    pass


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────

def _need():
    if not _CAD_AVAILABLE:
        raise RuntimeError("cadquery unavailable — run with the .venv-cad interpreter")


def _safe_fillet(wp, selector, radius):
    """Fillet the selected edges, backing the radius off if OCCT rejects it (robustness over bravado).
    Returns the original solid if even a small fillet fails — a missing fillet is cosmetic, not a crash."""
    for r in (radius, radius * 0.6, radius * 0.35):
        try:
            return wp.edges(selector).fillet(r)
        except Exception:
            continue
    return wp


def _safe_chamfer(wp, selector, length):
    for c in (length, length * 0.6, length * 0.35):
        try:
            return wp.edges(selector).chamfer(c)
        except Exception:
            continue
    return wp


def _cut(solid, tool):
    """Boolean-difference, swallowing OCCT hiccups (a missing cosmetic groove must never kill a part)."""
    try:
        return solid.cut(tool)
    except Exception:
        return solid


def _union(solid, tool):
    try:
        return solid.union(tool)
    except Exception:
        return solid


def _export(solid, path):
    """Export a solid to a fine-tessellated binary STL; return its triangle count (non-empty proof)."""
    exporters.export(solid, path, tolerance=_STL_TOL, angularTolerance=_STL_ANG)
    with open(path, "rb") as fh:
        fh.seek(80)
        n = struct.unpack("<I", fh.read(4))[0]
    return n


# ── the shared HARD-SURFACE limb cover ────────────────────────────────────────────────────────────

def _hard_limb(*, depth_top: float, width_top: float, depth_bot: float, width_bot: float, length: float,
               edge_r: float = 16.0, end_r: float = 7.0, seam: bool = True, front_panel: bool = True,
               rib_z: float | None = None, cuff_top: bool = True, cuff_bot: bool = True):
    """Build one hard-surface limb cover (a designed segment, NOT a tube).

    The cover is a SLAB cross-section (``depth`` along X = front/back, ``width`` along Y = sideways) so
    ``width > depth`` reads as a flat-fronted limb plate. The taper is a clean ellipse loft; the flat
    facets come from intersecting it with a filleted box. Detail is booleaned IN (watertight):
      * ``seam``        — a parting groove down each Y flank (the front/back half-cover split).
      * ``front_panel`` — two vertical border grooves framing a raised central front panel.
      * ``rib_z``       — (optional) a raised structural cross-rib band at this absolute z (union).
      * ``cuff_top``/``cuff_bot`` — a recessed machined end-collar so the exposed actuator seats in it.

    Local frame: TOP rim at z=0, the cover extends to z=-``length``. x = front (+X = toward the toes).
    Returns a CadQuery solid in mm. Watertight by construction (ellipse∩box + interior cuts/unions)."""
    _need()
    dt, wt, db, wb = depth_top, width_top, depth_bot, width_bot
    # clean ellipse loft slightly larger than the clip box so the box defines the flat facets
    oval = (cq.Workplane("XY").ellipse(dt + 6, wt + 6)
            .workplane(offset=-length).ellipse(db + 6, wb + 6)
            .loft(combine=True))
    # the clip box: constant section sized to the TOP (so the top is the full slab; the loft taper trims
    # the lower part). Filleted vertical edges keep it hard-but-not-razor.
    box = (cq.Workplane("XY").box(2 * dt, 2 * wt, length + 30).translate((0, 0, -length / 2.0))
           .edges("|Z").fillet(edge_r))
    s = oval.intersect(box)
    s = _safe_fillet(s, ">Z", end_r)
    s = _safe_fillet(s, "<Z", end_r * 0.85)

    fx = dt  # the front face x (approx; the box front facet sits near x=+dt)
    if front_panel:
        # two vertical border grooves framing a raised central front panel (the defining cover detail)
        zc = -length * 0.5
        zh = length * 0.60
        ph = wt * 0.62  # half the panel width
        for yy in (ph, -ph):
            groove = (cq.Workplane("XY").workplane(offset=zc + zh / 2.0)
                      .center(fx, yy).rect(6.0, 3.0).extrude(-zh))
            s = _cut(s, groove)
    if seam:
        # a parting groove down each Y flank — the front/back half-cover split line
        for sy in (1, -1):
            g = (cq.Workplane("XY").workplane(offset=-10.0)
                 .center(0, sy * wt).rect(8.0, 4.0).extrude(-(length - 20.0)))
            s = _cut(s, g)
    if rib_z is not None:
        # a raised structural cross-rib band across the front (union — never opens the solid)
        rib = (cq.Workplane("XY").workplane(offset=rib_z)
               .center(fx - 1.0, 0).rect(7.0, 2 * wt - 16.0).extrude(-11.0).translate((3.0, 0, 0)))
        s = _union(s, rib)
    if cuff_top:
        # recessed machined end-collar at the top (the exposed actuator hub seats into this rebate).
        # WHY explicit outer-extrude then cut(inner-extrude): produces a true annular/holed rebate
        # (frame cut) rather than relying on the chained .rect(outer).rect(inner).extrude() profile rule.
        # The latter is a CadQuery idiom with no other use in src/; explicit cut makes the hole
        # intention obvious, robust, and self-documenting. Watertight + mesh_integrity still guard
        # the result but the construction itself now proves the topology.
        off = -1.0
        h = 11.0
        outer = (cq.Workplane("XY").workplane(offset=off)
                 .rect(2 * dt + 4, 2 * wt + 4).extrude(h))
        inner = (cq.Workplane("XY").workplane(offset=off)
                 .rect(2 * dt - 16, 2 * wt - 16).extrude(h))
        ring = outer.cut(inner)
        s = _cut(s, ring)
    if cuff_bot:
        off = -(length - 10.0)
        h = 11.0
        outer = (cq.Workplane("XY").workplane(offset=off)
                 .rect(2 * db + 8, 2 * wb + 8).extrude(h))
        inner = (cq.Workplane("XY").workplane(offset=off)
                 .rect(2 * db - 12, 2 * wb - 12).extrude(h))
        ring = outer.cut(inner)
        s = _cut(s, ring)
    return s


# ── per-segment limb shells (same SHELLS keys + local frames as before → URDF mounts them unchanged) ──
# Lengths MATCH the URDF limb lengths (m→mm): thigh 300, shank 300, upper arm 240, forearm 220 mm. A small
# inset is left at each end (the cuff) so the exposed actuator hub shows through (industrial mechanics).

def thigh_shell():
    """Thigh cover: a powerful slab — broad flat front quad-panel at the hip, tapering toward the knee,
    a strong side parting seam and a structural cross-rib. The hip RMD-X10 and knee AK80-64 actuators
    stay EXPOSED in the recessed end-collars above and below it."""
    return _hard_limb(depth_top=30, width_top=48, depth_bot=24, width_bot=38, length=288,
                      edge_r=16, rib_z=-86)


def shank_shell():
    """Shank cover: a flat-shinned slab — calf swell flat-fronted near the knee tapering to a slim ankle,
    side seam + a low cross-rib. Knee AK80-64 above, ankle RMD-X6 below stay exposed in the cuffs."""
    return _hard_limb(depth_top=27, width_top=42, depth_bot=21, width_bot=30, length=288,
                      edge_r=14, rib_z=-60)


def upper_arm_shell():
    """Upper-arm cover: a substantial deltoid slab tapering to the elbow, flat front panel + side seam.
    The shoulder and elbow AK70-10 actuators stay exposed in the end-collars (the shoulder also wears the
    pauldron). Beefed vs a thin tube so it reads as a real powered arm member."""
    return _hard_limb(depth_top=30, width_top=42, depth_bot=24, width_bot=34, length=230,
                      edge_r=15, rib_z=-70)


def forearm_shell():
    """Forearm cover: houses the finger servos — a substantial flat-fronted slab below the elbow tapering
    to the wrist, side seam + a wrist cross-rib. The elbow AK70-10 stays exposed in the top cuff."""
    return _hard_limb(depth_top=26, width_top=37, depth_bot=20, width_bot=28, length=210,
                      edge_r=13, rib_z=-150)


# ── torso: a real chest + back CUIRASS ────────────────────────────────────────────────────────────

def torso_shell():
    """The chest/back exo-shell: a hard-surface CUIRASS, NOT a slab. Broad flat-faceted shoulders over a
    tapered waist (deep oval clipped to a flat chest + back), with a raised STERNUM ridge and pectoral
    panel split on the FRONT (+X), a SPINE channel + scapula yokes on the BACK (−X), and raised SHOULDER
    YOKES at the top corners where the arms mount. Spans z=0 (waist joint) to ~225 mm (shoulder line) so
    the head + neck stay clearly above it. The Jetson + spine members stay exposed behind/within it."""
    _need()
    # clean lofted trunk (deep in Y = broad shoulders, shallower in X) — DELTAS place sections at
    # ABSOLUTE z = 6, 95, 175, 222, 262, 292 mm. The last two sections are a NECK/COLLAR RISER that climbs
    # from the shoulder line up toward the neck joint (torso link is 300 mm tall) so the chest flows into a
    # collar instead of leaving a bare-torso gap below the head (the neck hub + head sit just above 292 mm).
    oval = (cq.Workplane("XY")
            .workplane(offset=6).ellipse(64, 98)        # z=6   waist
            .workplane(offset=89).ellipse(78, 124)       # z=95  belly / lower chest
            .workplane(offset=80).ellipse(84, 132)       # z=175 mid-chest (broadest)
            .workplane(offset=47).ellipse(70, 116)       # z=222 shoulder line (still broad)
            .workplane(offset=40).ellipse(52, 80)        # z=262 upper-chest / clavicle (narrowing)
            .workplane(offset=30).ellipse(34, 46)        # z=292 collar base (the neck emerges from here)
            .loft(combine=True))
    # clip box → flat chest (front +X) + flat back (−X) + flat-ish shoulder sides, hard vertical edges.
    # Taller now (to 300 mm) so the collar riser is included in the facet clip.
    box = (cq.Workplane("XY").box(150, 250, 320).translate((0, 0, 150)).edges("|Z").fillet(30))
    s = oval.intersect(box)
    s = _safe_fillet(s, ">Z", 16)
    s = _safe_fillet(s, "<Z", 10)

    # FRONT (+X): a raised sternum ridge + a chest panel split + a lower-chest seam.
    fx = 70.0  # approx front facet x at the chest
    sternum = (cq.Workplane("XY").workplane(offset=40).center(fx - 2, 0).rect(8.0, 170.0)
               .extrude(-1).translate((0, 0, 0)))  # placeholder height set below by union of a bar
    # the sternum as a raised vertical bar (union, watertight): a thin proud spine down the chest centre
    sternum_bar = (cq.Workplane("XZ").workplane(offset=0).center(0, 120).rect(2.6, 175.0).extrude(-(fx + 6)))
    s = _union(s, sternum_bar)
    _ = sternum
    # pectoral panel split: two vertical grooves framing the two pec panels on the chest
    for yy in (52, -52):
        s = _cut(s, (cq.Workplane("XY").workplane(offset=150).center(fx, yy).rect(6.0, 3.0).extrude(-120)))
    # a horizontal lower-chest / abdominal seam (groove across the front)
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-fx).center(0, 96).rect(3.0, 210.0).extrude(6.0)))

    # BACK (−X): a recessed spine channel + two scapula panel grooves.
    bx = -70.0
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-bx).center(0, 120).rect(4.0, 185.0).extrude(-6.0)))
    for yy in (60, -60):
        s = _cut(s, (cq.Workplane("XY").workplane(offset=150).center(bx, yy).rect(6.0, 3.0).extrude(-110)))

    # SHOULDER YOKES: raised flat-topped pads at the two top corners (±Y) where the arms mount —
    # a stepped boss (union) so the arm joint emerges from a structured shoulder, not a bare slab edge.
    for sy in (1, -1):
        yoke = (cq.Workplane("XY").workplane(offset=185)
                .center(0, sy * 118).box(70, 46, 60).edges("|Z").fillet(12))
        s = _union(s, yoke)
    # soften the collar so the neck emerges cleanly
    s = _safe_fillet(s, ">Z", 8)
    return s


# ── pelvis: hip girdle ─────────────────────────────────────────────────────────────────────────────

def pelvis_shell():
    """The hip girdle: a wide hard-surface block with FLAT front/back panels, chamfered top/bottom, a
    front pelvic panel split and recessed SIDE hip-actuator wells (the big RMD-X10 hip pancakes seat into
    them, exposed). Centred on the pelvis origin."""
    _need()
    s = (cq.Workplane("XY").box(90, 172, 100)
         .edges("|Z").fillet(26).edges(">Z or <Z").fillet(12))
    # recessed circular hip-actuator wells on each side (±Y) so the exposed hip pancake seats in a collar
    for sy in (1, -1):
        well = (cq.Workplane("XZ").workplane(offset=sy * 86)
                .center(0, 0).circle(42).extrude(-sy * 9))
        s = _cut(s, well)
    # a front pelvic panel split (vertical groove pair) + a centre belt groove
    for yy in (44, -44):
        s = _cut(s, (cq.Workplane("XY").workplane(offset=44).center(45, yy).rect(5.0, 3.0).extrude(-72)))
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-45).center(0, 0).rect(3.0, 150.0).extrude(5.0)))
    s = _safe_chamfer(s, "<Z", 1.5)
    return s


# ── head: faceted cranium with a FLUSH visor ───────────────────────────────────────────────────────

def head_shell():
    """A hard-surface robot HEAD: a faceted cranium (lofted ovoid clipped to flat cheeks/temples) with a
    FLUSH recessed VISOR band across the FACE (+X) at eye height, a defined brow above and a jaw step
    below, plus two side SENSOR PODS at the temples. The real OAK-D stereo camera + the copper eye-lenses
    (mounted by the URDF on the +X face) sit IN the visor recess.

    The visor is CUT into the cheek band (booleaned IN — never floated): its inner face sits a controlled
    depth below the actual front cheek surface, so it reads as a flush sensor band, not a stuck-on plate.
    z is up; face is +X. Centred so the URDF places it at the head origin."""
    _need()
    # DELTAS → ABSOLUTE z = -58, -20, 20, 58, 84 mm (a ~142 mm head). Oversize then clip to facet.
    oval = (cq.Workplane("XY")
            .workplane(offset=-58).ellipse(46, 42)        # chin
            .workplane(offset=38).ellipse(60, 54)         # jaw
            .workplane(offset=40).ellipse(70, 64)         # cheek / widest
            .workplane(offset=38).ellipse(66, 60)         # cranium
            .workplane(offset=26).ellipse(40, 36)         # crown
            .loft(combine=True))
    # clip box → flat cheeks/temples + a flat-ish face plane, hard-but-rounded vertical edges
    box = (cq.Workplane("XY").box(120, 116, 168).translate((0, 0, 13)).edges("|Z").fillet(26))
    s = oval.intersect(box)
    s = _safe_fillet(s, ">Z", 14)
    s = _safe_fillet(s, "<Z", 9)

    # FLUSH VISOR: the clip box flattened the face to ~x=+60 across the eye band; cut a recessed band a
    # controlled depth INTO that face (booleaned IN). The band spans the cheeks (Y) at eye height (z≈12).
    # cut from a box whose OUTER face is flush with the cheek and that bites ~9 mm in.
    face_x = 60.0
    visor = (cq.Workplane("XY").workplane(offset=12.0)
             .moveTo(face_x, 0).rect(18.0, 96.0).extrude(40.0, both=True))
    # move it so it bites 9 mm into the face (inner wall at x = face_x - 9), outer flush with cheek
    visor = visor.translate((-9.0, 0, 0))
    s = _cut(s, visor)
    # BROW ridge above + a CHIN/jaw step below (raised unions — frame the visor so the camera looks
    # purposeful, not like a dent)
    brow = (cq.Workplane("XY").workplane(offset=34.0).moveTo(face_x - 2, 0).rect(9.0, 90.0).extrude(8.0))
    s = _union(s, brow)
    chin = (cq.Workplane("XY").workplane(offset=-30.0).moveTo(face_x - 6, 0).rect(12.0, 72.0).extrude(9.0))
    s = _union(s, chin)
    # SIDE SENSOR PODS at the temples (±Y) — small raised faceted bosses (union, watertight)
    for sy in (1, -1):
        pod = (cq.Workplane("XY").workplane(offset=22.0)
               .center(8.0, sy * 58.0).box(34, 22, 30).edges("|Z").fillet(7))
        s = _union(s, pod)
    s = _safe_fillet(s, ">X", 2.0)
    # left SOLID (a visual mesh; a solid head is trivially watertight and avoids fragile .shell()).
    return s


# ── shoulder pauldron: a faceted cap ───────────────────────────────────────────────────────────────

def shoulder_pauldron():
    """An industrial shoulder pauldron: a faceted domed cap (a clean ellipse-loft dome with a flat-ish
    front facet) that caps the shoulder actuator while leaving the joint axis visible below it. A raised
    armour-seam lip gives it a layered look. Mounts at the shoulder. The dome loft is watertight on its
    own (no box intersect — the earlier oversize clip box added nothing but a non-manifold sliver)."""
    _need()
    # a slightly squared dome: the wider lower ellipses give it a shouldered (less hemispherical) read.
    s = (cq.Workplane("XY")
         .workplane(offset=0).ellipse(52, 50)
         .workplane(offset=18).ellipse(49, 47)
         .workplane(offset=22).ellipse(33, 32)
         .workplane(offset=16).ellipse(11, 11)
         .loft(combine=True))
    s = _safe_fillet(s, "<Z", 3)
    # a layered armour-seam ridge around the cap (raised ring via union — watertight, never opens the
    # solid the way an annular cut can). A thin proud lip at the mid-height of the cap.
    lip = (cq.Workplane("XY").workplane(offset=13).ellipse(47, 47)
           .workplane(offset=4).ellipse(45, 45).loft(combine=True))
    s = _union(s, lip)
    return s


# ── foot: a hard-surface boot over the flat sole ───────────────────────────────────────────────────

def foot_shell():
    """The foot: a hard-surface BOOT over the flat 240 mm box sole. The SOLE (collision) is unchanged and
    flat (ZMP-stable); this is a faceted upper — a defined TOE CAP (split from the mid-foot by a groove),
    an ANKLE COLLAR where the RMD-X6 ankle actuator seats, a heel counter and a sole-edge bevel. x =
    forward (toe +X), z = up; the flat underside sits at z=0 so the visual sole stays coincident with the
    collision sole top."""
    _need()
    base = (cq.Workplane("XY").box(240, 110, 30).translate((0, 0, 15)).edges("|Z").fillet(20))
    base = _safe_fillet(base, ">Z", 9)
    # ankle collar / instep hump (faceted): a clipped lofted hump where the ankle actuator seats
    hump = (cq.Workplane("XY")
            .workplane(offset=20).ellipse(80, 52)
            .workplane(offset=24).ellipse(66, 44)
            .workplane(offset=20).ellipse(32, 24)
            .loft(combine=True).translate((-12, 0, 0)))
    humpbox = (cq.Workplane("XY").box(150, 96, 90).translate((-12, 0, 40)).edges("|Z").fillet(20))
    hump = hump.intersect(humpbox)
    foot = _union(base, hump)
    foot = _safe_fillet(foot, ">Z", 7)
    # TOE-CAP split: a transverse groove across the forefoot separating the toe cap from the mid-foot
    foot = _cut(foot, (cq.Workplane("YZ").workplane(offset=58).center(0, 16).rect(34, 4.0).extrude(112)))
    # a heel counter groove (transverse, at the back)
    foot = _cut(foot, (cq.Workplane("YZ").workplane(offset=-92).center(0, 16).rect(28, 3.0).extrude(108)))
    # sole-edge bevel
    foot = _safe_chamfer(foot, "<Z", 2.0)
    return foot


SHELLS = {
    "head": head_shell,
    "torso": torso_shell,
    "pelvis": pelvis_shell,
    "thigh": thigh_shell,
    "shank": shank_shell,
    "uarm": upper_arm_shell,
    "farm": forearm_shell,
    "pauldron": shoulder_pauldron,
    "foot": foot_shell,
}


def build_all(out_dir: str) -> dict:
    """Generate every shell STL into ``out_dir``; return a ``{name: {path, triangles}}`` manifest.

    Every successful entry is guaranteed triangles > 0 (an empty mesh is turned into an error entry, the
    file removed). The solids are watertight by construction (ellipse∩box + interior cuts/unions); the
    STL triangle count + the consuming pipeline's mesh_integrity prove it for the written file. A single
    shell failing must not kill the rest (resilience contract)."""
    manifest = {}
    # makedirs once, outside per-shell loop: avoids redundant calls (was inside loop on every shell).
    # If dir creation itself fails we populate the full manifest with the root cause (no partial
    # success, no files written) while still returning a manifest so callers see consistent error shape.
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as exc:
        for name in SHELLS:
            manifest[name] = {"path": None, "error": f"mkdir {type(exc).__name__}: {exc}"}
        return manifest

    for name, fn in SHELLS.items():
        try:
            path = os.path.join(out_dir, f"aethon_{name}_shell.stl")
            solid = fn()
            n = _export(solid, path)
            if n < 1:
                try:
                    os.unlink(path)
                except Exception:
                    pass
                manifest[name] = {"path": None, "error": "empty mesh (0 triangles)"}
            else:
                manifest[name] = {"path": path, "triangles": n}
        except Exception as exc:  # a single shell failing must not kill the rest
            manifest[name] = {"path": None, "error": f"{type(exc).__name__}: {exc}"}
    return manifest


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/home/genesis/humanoid_assets/aethon/shells"
    print(json.dumps(build_all(out), indent=2))
