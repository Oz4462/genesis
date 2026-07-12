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


# ── R4 micro-detail helpers (booleaned IN → watertight; sized to read as TEXTURE, not lumps) ─────────

def _bolt_row(solid, *, plane, w_offset, points, r=1.6, depth=2.0, axis_into=-1.0):
    """Cut a row of small recessed FASTENER bolt holes into a face (the Apollo/T1 hardware cue). ``plane``
    is a CadQuery plane string ("XY"/"XZ"/"YZ"); ``points`` is a list of (u,v) centres on that workplane;
    ``axis_into`` is the extrude sign (into the solid). Tiny → reads as a fastener, not a hole."""
    for (u, v) in points:
        try:
            tool = (cq.Workplane(plane).workplane(offset=w_offset).center(u, v).circle(r)
                    .extrude(axis_into * depth))
            solid = _cut(solid, tool)
        except Exception:
            continue
    return solid


def _vent_louvres(solid, *, plane, w_offset, center, n, pitch, slot_w, slot_l, depth=2.2, axis_into=-1.0,
                  horizontal=True):
    """Cut a stack of fine VENT LOUVRE slots into a face (cooling-vent texture). ``center`` is (u,v); the
    slots stack along v (horizontal=True → long axis = u) by ``pitch``. Booleaned IN → watertight."""
    cu, cv = center
    for k in range(n):
        off = (k - (n - 1) / 2.0) * pitch
        sw, sl = (slot_l, slot_w) if horizontal else (slot_w, slot_l)
        try:
            tool = (cq.Workplane(plane).workplane(offset=w_offset).center(cu, cv + off)
                    .rect(sw, sl).extrude(axis_into * depth))
            solid = _cut(solid, tool)
        except Exception:
            continue
    return solid


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
    # R2: FLATTER FRONT FACET — clip the depth (X) tighter (1.62·dt vs 2·dt) so the front and back read as
    # distinctly FLAT plated faces, not a round tube, at hero distance. Width (Y) keeps the full slab.
    box = (cq.Workplane("XY").box(1.62 * dt, 2 * wt, length + 30).translate((0, 0, -length / 2.0))
           .edges("|Z").fillet(edge_r))
    s = oval.intersect(box)
    s = _safe_fillet(s, ">Z", end_r)
    s = _safe_fillet(s, "<Z", end_r * 0.85)

    fx = 0.81 * dt  # the front face x (the flatter clip box front facet sits near x=+0.81·dt)
    if front_panel:
        # R2: a RAISED central front PLATE (relief) framed by two deeper border grooves — reads as a real
        # bolted-on panel at distance, not just scribed lines. The plate is a thin proud slab (union); the
        # grooves bite deeper/wider around it (cut).
        zc = -length * 0.5
        zh = length * 0.62
        ph = wt * 0.58  # half the panel width
        plate = (cq.Workplane("XY").workplane(offset=zc + zh / 2.0)
                 .center(fx - 0.5, 0).rect(3.0, 2 * ph).extrude(-zh))
        s = _union(s, plate)
        for yy in (ph, -ph):
            groove = (cq.Workplane("XY").workplane(offset=zc + zh / 2.0)
                      .center(fx, yy).rect(8.0, 4.5).extrude(-zh))
            s = _cut(s, groove)
        # R3: TWO transverse panel-break grooves (at ~1/3 and ~2/3 length) so each limb reads as 3 stacked
        # panels (the Apollo panel-density cue), not one smooth cover.
        for fr in (0.36, 0.68):
            s = _cut(s, (cq.Workplane("XZ").workplane(offset=-fx).center(0, -length * fr).rect(4.0, 2 * ph)
                         .extrude(7.0)))
    if seam:
        # R2: DEEPER parting groove down each Y flank — the front/back half-cover split (reads at distance)
        for sy in (1, -1):
            g = (cq.Workplane("XY").workplane(offset=-10.0)
                 .center(0, sy * wt).rect(11.0, 5.5).extrude(-(length - 20.0)))
            s = _cut(s, g)
    if rib_z is not None:
        # a raised structural cross-rib band across the front (union — never opens the solid)
        rib = (cq.Workplane("XY").workplane(offset=rib_z)
               .center(fx - 1.0, 0).rect(7.0, 2 * wt - 16.0).extrude(-11.0).translate((3.0, 0, 0)))
        s = _union(s, rib)
    if cuff_top:
        # recessed machined end-collar at the top (the exposed actuator hub seats into this rebate)
        ring = (cq.Workplane("XY").workplane(offset=-1.0)
                .rect(2 * dt + 4, 2 * wt + 4).rect(2 * dt - 16, 2 * wt - 16).extrude(11.0))
        s = _cut(s, ring)
    if cuff_bot:
        ring = (cq.Workplane("XY").workplane(offset=-(length - 10.0))
                .rect(2 * db + 8, 2 * wb + 8).rect(2 * db - 12, 2 * wb - 12).extrude(11.0))
        s = _cut(s, ring)
    # R4 MICRO-DETAIL: a row of small FASTENER bolts down each side of the raised front plate (reads as a
    # bolted-on cover at hero distance — the Apollo hardware cue). Booleaned IN → watertight.
    if front_panel:
        zc = -length * 0.5
        ph = wt * 0.58
        pts = [(fx + 1.0, z) for z in (zc + length * 0.30, zc, zc - length * 0.30)]
        pts = [(x, y) for (x, y) in pts]
        # bolts along both plate edges (±ph in Y) at three heights
        bolts = []
        for zz in (-length * 0.20, -length * 0.5, -length * 0.80):
            for yy in (ph - 2.0, -(ph - 2.0)):
                bolts.append((zz, yy))
        for (zz, yy) in bolts:
            tool = (cq.Workplane("XY").workplane(offset=zz).center(fx + 1.0, yy).circle(1.5).extrude(-2.2))
            s = _cut(s, tool)
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


# ── hand: a real contoured PALM/hand-back with a metacarpal knuckle block + thumb web ───────────────
# RE-AUTHORED in Round 1: the old hand read as a blocky lump (URDF palm box + raised knuckle box + thumb
# boss). This builds a genuine hand BACK shell — a contoured slab (rounded back, tapered toward the wrist,
# widening at the knuckles), a METACARPAL knuckle ridge the four fingers hinge from (with four hinge
# saddles), a defined THUMB WEB ramp on the −Y side, knuckle tendon grooves and a wrist cuff. VISUAL ONLY:
# the palm collision box + finger collision/inertials/joints are byte-identical; this is mounted as the
# palm VISUAL in place of the bare box. Local frame MATCHES the URDF palm box: wrist face at z=0, the hand
# extends to z=-PALM_Z, fingers root off the +X / −z far edge; +X = the back-of-hand/finger-point side,
# −Y = the thumb side (the thumb is spread[0] at −pyh·0.38). Units mm.
PALM_X = 50.0    # length  (wrist→knuckles, local X) — matches _DIM['palm'][0]·1000
PALM_Y = 85.0    # width   (across the 5 fingers, local Y)
PALM_Z = 22.0    # thickness (back→palm, local Z)


def palm_shell():
    """A real hand BACK: a contoured slab with a metacarpal knuckle block (4 finger saddles), a thumb-web
    ramp and a wrist cuff. Authored in the URDF palm frame (wrist at z=0, hand to z=−PALM_Z, +X toward the
    fingertips, −Y the thumb side). Watertight by construction (ellipse∩box + interior unions/cuts)."""
    _need()
    hx, hy, hz = PALM_X * 0.5, PALM_Y * 0.5, PALM_Z
    # contoured hand back: an ellipse stack (narrow at the wrist, widest at the knuckles) → a hand fan
    # shape, lofted down −Z then intersected with a thin clip box so the back is a flat-faceted plate.
    oval = (cq.Workplane("XY")
            .workplane(offset=0).center(-hx * 0.30, 0).ellipse(hx * 0.72, hy * 0.66)   # wrist (narrow)
            .workplane(offset=-hz * 0.5).center(hx * 0.30, 0).ellipse(hx * 0.95, hy * 0.95)  # palm
            .workplane(offset=-hz * 0.5).center(hx * 0.55, 0).ellipse(hx * 0.80, hy * 1.02)  # knuckles
            .loft(combine=True))
    box = (cq.Workplane("XY").box(PALM_X + 14, PALM_Y + 6, PALM_Z).translate((6, 0, -hz * 0.5))
           .edges("|Z").fillet(10))
    s = oval.intersect(box)
    s = _safe_fillet(s, ">Z", 6)
    # METACARPAL KNUCKLE BLOCK: a raised dark-reading ridge across the finger end (+X far edge), at the
    # palm bottom (−z), where the four fingers hinge. A box union with four shallow hinge saddles cut in.
    knuckle = (cq.Workplane("XY").workplane(offset=-hz + 1.0)
               .center(hx * 0.62, 0).box(13.0, PALM_Y * 0.92, 12.0).edges("|Z").fillet(3.0))
    s = _union(s, knuckle)
    # four finger hinge saddles (shallow transverse grooves) across the knuckle block so it reads as four
    # separate knuckles, not one bar — at the index/middle/ring/pinky y positions (thumb is the −Y end).
    for yo in (-PALM_Y * 0.19, 0.0, PALM_Y * 0.19, PALM_Y * 0.38):
        saddle = (cq.Workplane("XZ").workplane(offset=-yo)
                  .center(hx * 0.62, -hz + 1.0).rect(8.0, 4.0).extrude(8.0, both=True))
        s = _cut(s, saddle)
    # THUMB WEB: a raised ramp boss on the −Y side at the wrist-third of the palm (the thenar eminence) so
    # the opposable thumb springs from a real web, not a flat edge.
    web = (cq.Workplane("XY").workplane(offset=-hz * 0.5)
           .center(hx * 0.05, -hy * 0.82).box(26.0, 18.0, 16.0).edges("|Z").fillet(6.0))
    s = _union(s, web)
    # KNUCKLE TENDON GROOVES on the back (four shallow grooves running from the wrist toward each finger)
    for yo in (-PALM_Y * 0.19, 0.0, PALM_Y * 0.19, PALM_Y * 0.38):
        groove = (cq.Workplane("XY").workplane(offset=0.5)
                  .center(hx * 0.15, yo).rect(PALM_X * 0.55, 2.4).extrude(-3.0))
        s = _cut(s, groove)
    # WRIST CUFF: a recessed transverse groove at the wrist end (−X) so the wrist-roll hub reads as
    # seating into a collar (a simple solid-cut groove — robust, stays watertight).
    cuff = (cq.Workplane("XY").workplane(offset=0.5)
            .center(-hx * 0.74, 0).rect(5.0, PALM_Y * 0.66).extrude(-4.0))
    s = _cut(s, cuff)
    return s


# ── fingers: real SEGMENTED phalanx shells (Round 6 — close the worst gap to Apollo) ────────────────
# The old hand read as smooth fused white SAUSAGES: each finger was three uniform white cylinders butted
# end-to-end with same-white sphere knuckles → no visible joint, taper or fingertip; four fingers fused
# into a mitten. Apollo (and any real robot) has ARTICULATED fingers: a dark machined knuckle housing at
# each joint, a tapering phalanx, a defined fingertip pad, visible hinge gaps. These shells re-author the
# finger VISUALS only (the cylinder+sphere collision and the inertials/joints are byte-identical and are
# EXCLUDED from the physics SHA), mounted per phalanx link in genesis_humanoid._add_finger.
#
# Local frame MATCHES the phalanx link (genesis_humanoid._add_finger): the proximal joint is at x=0, the
# phalanx body runs along +X to x=PHX_LEN, the knuckle is at the origin. +Z is the back of the finger.
# Units mm; the URDF scales 0.001. Two pieces per phalanx are emitted as SEPARATE shells so the URDF can
# tint them differently: the light tapering BODY and the dark machined KNUCKLE collar at the base. The
# distal phalanx body additionally gets a rounded fingertip; the proximal is the chunkiest.
PHX_LEN = 30.0   # one phalanx length [mm] — matches _DIM['phalanx_len']·1000
PHX_R = 8.5      # the URDF collision capsule radius [mm] — matches _DIM['phalanx_r']·1000


def _phalanx_body(*, w_prox: float, w_dist: float, h_prox: float, h_dist: float, tip: bool):
    """A tapering hard-surface phalanx BODY (light shell): a box-section bone narrowing proximal→distal,
    with chamfered long edges, a shallow dorsal tendon groove and (distal) a rounded fingertip dome.

    ``w_*`` = half-width (Y), ``h_*`` = half-height/thickness (Z) at each end. Authored x=0..PHX_LEN with
    a small inset at each end so the dark knuckle collars (mounted separately) show as joints. Watertight."""
    _need()
    inset = 2.4                 # leave a gap at the joint so the knuckle collar reads as a hinge
    x0, x1 = inset, PHX_LEN - (0.0 if tip else inset)
    L = x1 - x0
    # tapering bone: a loft from a proximal rounded-rect to a distal rounded-rect (use ellipse loft for a
    # clean tessellation, then clip to a box for flat-ish faceted faces — the hard-surface look).
    body = (cq.Workplane("YZ").workplane(offset=x0).ellipse(w_prox + 1.2, h_prox + 1.2)
            .workplane(offset=L).ellipse(w_dist + 1.2, h_dist + 1.2)
            .loft(combine=True))
    clip = (cq.Workplane("YZ").workplane(offset=x0 - 1).box(2 * max(w_prox, w_dist), 1.55 * h_prox, L + 2)
            .translate((0, 0, 0)))
    # the clip box must be oriented along X: build it as a plain box spanning x0..x1
    clip = (cq.Workplane("XY").box(L + 2, 2 * max(w_prox, w_dist), 1.62 * h_prox)
            .translate(((x0 + x1) / 2.0, 0, 0)).edges("|X").fillet(min(w_dist, h_dist) * 0.7))
    s = body.intersect(clip)
    s = _safe_fillet(s, ">X", h_dist * 0.5)
    # dorsal tendon groove down the back (+Z), a fine scribe (cut → watertight)
    s = _cut(s, (cq.Workplane("XY").workplane(offset=h_prox * 0.55).center((x0 + x1) / 2.0, 0)
                 .rect(L * 0.8, 1.6).extrude(h_prox)))
    if tip:
        # rounded fingertip pad: a small dome capping the distal end (union)
        cap = (cq.Workplane("YZ").workplane(offset=x1 - 2.0).ellipse(w_dist + 0.6, h_dist + 0.6)
               .workplane(offset=2.0).ellipse(w_dist * 0.5, h_dist * 0.55)
               .workplane(offset=1.6).ellipse(w_dist * 0.18, h_dist * 0.2).loft(combine=True))
        s = _union(s, cap)
    return s


def _knuckle_collar(*, r_y: float, r_z: float):
    """A dark machined KNUCKLE housing at a finger joint: a short faceted collar around the proximal end
    (x≈0) that reads as the hinge axle/bearing block. Mounted by the URDF as the dark (machined-metal)
    visual at each phalanx base; the body shell (light) butts above it → two-tone articulated finger.
    Authored centred on the joint at x=0, axle along Y (the flex axis). Watertight."""
    _need()
    # a barrel along Y (the pitch flex axis) clipped to a faceted block — reads as a knuckle bearing.
    barrel = (cq.Workplane("XZ").circle(max(r_y, r_z)).extrude(2 * (r_y + 1.4), both=True))
    block = (cq.Workplane("XY").box(2 * r_z + 2.4, 2 * (r_y + 1.0), 2 * r_z + 2.4)
             .edges("|Y").fillet(r_z * 0.5))
    s = barrel.intersect(block)
    # a centre groove around the barrel (the two cheek plates of a clevis) — reads as a real hinge
    s = _cut(s, (cq.Workplane("XZ").circle(max(r_y, r_z) + 0.5).circle(max(r_y, r_z) - 0.9)
                 .extrude(1.1, both=True)))
    return s


# the four long fingers taper index→pinky lengths via the same phalanx (the URDF spreads them); we author
# ONE set of three phalanx bodies (prox/mid/dist) + a knuckle, reused for every finger and (slimmer) thumb.
def finger_prox_shell():
    return _phalanx_body(w_prox=PHX_R * 0.92, w_dist=PHX_R * 0.80, h_prox=PHX_R * 0.92,
                         h_dist=PHX_R * 0.78, tip=False)


def finger_mid_shell():
    return _phalanx_body(w_prox=PHX_R * 0.80, w_dist=PHX_R * 0.68, h_prox=PHX_R * 0.80,
                         h_dist=PHX_R * 0.66, tip=False)


def finger_dist_shell():
    return _phalanx_body(w_prox=PHX_R * 0.68, w_dist=PHX_R * 0.50, h_prox=PHX_R * 0.68,
                         h_dist=PHX_R * 0.48, tip=True)


def finger_knuckle_shell():
    return _knuckle_collar(r_y=PHX_R * 0.86, r_z=PHX_R * 0.72)


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
    # R2 reshape: a real ATHLETIC V-taper — a PINCHED WAIST (lower ellipses pulled IN hard) under a broad
    # chest, so the midsection reads lean and the legs look longer (the R1→R2 torso-too-long fix). The
    # broadest point stays at mid-chest; the waist is a clear pinch above the hip girdle. Front depth (X)
    # is reduced too so the chest reads flatter/plated under the clip box (deeper facet).
    oval = (cq.Workplane("XY")
            .workplane(offset=6).ellipse(50, 80)         # z=6   WAIST — pinched (was 64,98)
            .workplane(offset=70).ellipse(58, 96)        # z=76  lower belly (rising)
            .workplane(offset=70).ellipse(78, 128)       # z=146 chest (broadening)
            .workplane(offset=44).ellipse(82, 134)       # z=190 mid/upper-chest (broadest)
            .workplane(offset=42).ellipse(64, 112)       # z=232 shoulder line
            .workplane(offset=34).ellipse(46, 74)        # z=266 upper-chest / clavicle (narrowing)
            .workplane(offset=28).ellipse(32, 44)        # z=294 collar base (the neck emerges from here)
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
        s = _cut(s, (cq.Workplane("XY").workplane(offset=150).center(fx, yy).rect(7.0, 4.0).extrude(-120)))
    # a horizontal lower-chest / abdominal seam (groove across the front)
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-fx).center(0, 96).rect(4.0, 210.0).extrude(6.0)))
    # R3 chest PANEL DENSITY: a CLAVICLE break high on the chest + an upper-ab segmentation seam + two
    # side-RIB VENT slots on each pec — turn the smooth white chest into a paneled mechanical cuirass.
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-fx).center(0, 205).rect(3.5, 150.0).extrude(6.0)))  # clavicle
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-fx).center(0, 70).rect(3.0, 170.0).extrude(6.0)))   # upper-ab
    for zz, yy in ((150, 40), (132, 40), (150, -40), (132, -40)):   # pec rib-vent slots (4)
        s = _cut(s, (cq.Workplane("XY").workplane(offset=zz).center(fx, yy).rect(5.0, 22.0).extrude(-4.0)))
    # R4 MICRO-DETAIL: fine VENT LOUVRES on the lower-chest sides (cooling vents) + FASTENER bolt rows on
    # the clavicle bar and along the sternum — Apollo-class hardware texture. Booleaned IN → watertight.
    for sy in (1, -1):
        s = _vent_louvres(s, plane="XZ", w_offset=-sy * 120.0, center=(0.0, 110.0), n=5, pitch=9.0,
                          slot_w=2.4, slot_l=26.0, depth=3.0, axis_into=sy, horizontal=True)
    # bolt row down the sternum centre + across the clavicle (small recessed heads)
    for zz in (60, 95, 130, 165, 200):
        s = _cut(s, (cq.Workplane("XY").workplane(offset=zz).center(fx + 1.0, 0).circle(1.7).extrude(-2.4)))
    for yy in (-58, -30, 30, 58):  # clavicle bolt row
        s = _cut(s, (cq.Workplane("XY").workplane(offset=205).center(fx + 1.0, yy).circle(1.6).extrude(-2.4)))

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
    # R2: narrower hip girdle (was 90×172) so the waist→hip read is leaner and the legs look longer; a
    # taller-than-wide block with a defined top rim (where the pinched torso waist seats) and chamfered
    # bottom corners where the thighs swing out.
    s = (cq.Workplane("XY").box(84, 150, 104)
         .edges("|Z").fillet(24).edges(">Z or <Z").fillet(12))
    # recessed circular hip-actuator wells on each side (±Y) so the exposed hip pancake seats in a collar
    for sy in (1, -1):
        well = (cq.Workplane("XZ").workplane(offset=sy * 75)
                .center(0, 0).circle(40).extrude(-sy * 9))
        s = _cut(s, well)
    # a front pelvic panel split (vertical groove pair, deeper) + a centre belt groove
    for yy in (40, -40):
        s = _cut(s, (cq.Workplane("XY").workplane(offset=46).center(42, yy).rect(6.0, 4.0).extrude(-76)))
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-42).center(0, 0).rect(4.0, 130.0).extrude(6.0)))
    # a top rim groove (where the torso waist seats into the girdle — reads as a real waist joint)
    s = _cut(s, (cq.Workplane("XY").workplane(offset=44).rect(80, 146).rect(64, 120).extrude(5.0)))
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
    # R3: head ~8% LARGER (it read small atop the broad shoulders) + a NECK-GUARD COLLAR at the base so the
    # neck stalk doesn't read fragile. DELTAS → ABSOLUTE z = -66, -24, 22, 64, 92 mm (a ~158 mm head).
    oval = (cq.Workplane("XY")
            .workplane(offset=-66).ellipse(50, 46)        # chin
            .workplane(offset=42).ellipse(65, 58)         # jaw
            .workplane(offset=46).ellipse(76, 69)         # cheek / widest
            .workplane(offset=42).ellipse(71, 65)         # cranium
            .workplane(offset=28).ellipse(43, 39)         # crown
            .loft(combine=True))
    # clip box → flat cheeks/temples + a flat-ish face plane, hard-but-rounded vertical edges
    box = (cq.Workplane("XY").box(130, 126, 184).translate((0, 0, 13)).edges("|Z").fillet(28))
    s = oval.intersect(box)
    s = _safe_fillet(s, ">Z", 15)
    s = _safe_fillet(s, "<Z", 10)
    # NECK-GUARD COLLAR: a short faceted ring at the head base (z≈-66..-86) the neck emerges from, so the
    # neck reads as guarded, not a bare stalk (union, watertight).
    collar = (cq.Workplane("XY").workplane(offset=-86).ellipse(40, 38)
              .workplane(offset=22).ellipse(52, 48).loft(combine=True))
    collarbox = (cq.Workplane("XY").box(96, 92, 40).translate((0, 0, -72)).edges("|Z").fillet(22))
    collar = collar.intersect(collarbox)
    s = _union(s, collar)

    # FLUSH VISOR: the larger clip box flattened the face to ~x=+65 across the eye band; cut a recessed
    # band INTO that face (booleaned IN). The band sits at the URDF eye height (z≈14 in the shell frame =
    # the URDF eyes at head-box z·0.62 minus the shell's +hz/2 mount lift). Spans the cheeks (Y).
    face_x = 65.0
    visor = (cq.Workplane("XY").workplane(offset=14.0)
             .moveTo(face_x, 0).rect(20.0, 104.0).extrude(44.0, both=True))
    # move it so it bites 9 mm into the face (inner wall at x = face_x - 9), outer flush with cheek
    visor = visor.translate((-9.0, 0, 0))
    s = _cut(s, visor)
    # BROW ridge above + a CHIN/jaw step below (raised unions — frame the visor so the camera looks
    # purposeful, not like a dent). R3: a touch larger to match the bigger head.
    brow = (cq.Workplane("XY").workplane(offset=38.0).moveTo(face_x - 2, 0).rect(10.0, 98.0).extrude(9.0))
    s = _union(s, brow)
    chin = (cq.Workplane("XY").workplane(offset=-33.0).moveTo(face_x - 6, 0).rect(13.0, 78.0).extrude(10.0))
    s = _union(s, chin)
    # a faceted CROWN panel groove + two temple panel lines (R3 head panel density)
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-face_x + 4).center(0, 60).rect(3.0, 70.0).extrude(8.0)))
    # SIDE SENSOR PODS at the temples (±Y) — small raised faceted bosses (union, watertight)
    for sy in (1, -1):
        pod = (cq.Workplane("XY").workplane(offset=24.0)
               .center(8.0, sy * 64.0).box(36, 24, 32).edges("|Z").fillet(7))
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
    # R3: a LARGER, more SCULPTED shoulder cap that wraps the deltoid (extends DOWN the outside of the arm
    # a touch) instead of a small dome nub. A squared dome (wide flat-ish lower ellipses) capped over the
    # shoulder, then a deltoid SKIRT lobe added on the outboard/front so it reads as integrated armour.
    s = (cq.Workplane("XY")
         .workplane(offset=-14).ellipse(58, 56)        # skirt base (extends below the shoulder line)
         .workplane(offset=14).ellipse(60, 58)         # widest (the shoulder shelf)
         .workplane(offset=18).ellipse(50, 48)
         .workplane(offset=22).ellipse(33, 32)
         .workplane(offset=16).ellipse(11, 11)
         .loft(combine=True))
    # clip the bottom flat-ish so the skirt has a hard lower rim (a designed armour edge, not a balloon)
    clip = (cq.Workplane("XY").box(150, 150, 120).translate((0, 0, 60 - 16)).edges("|Z").fillet(40))
    s = s.intersect(clip)
    s = _safe_fillet(s, "<Z", 4)
    # a layered ARMOUR-SEAM ridge around the cap (raised ring via union — watertight). A proud lip near the
    # shelf height that reads as a two-piece pauldron.
    lip = (cq.Workplane("XY").workplane(offset=12).ellipse(57, 55)
           .workplane(offset=5).ellipse(54, 52).loft(combine=True))
    s = _union(s, lip)
    # a second lower seam at the skirt base (more layered armour)
    lip2 = (cq.Workplane("XY").workplane(offset=-6).ellipse(58, 56)
            .workplane(offset=4).ellipse(55, 53).loft(combine=True))
    s = _union(s, lip2)
    # a shallow panel groove down the front of the cap (a centre split → reads as a shaped pauldron)
    s = _cut(s, (cq.Workplane("XZ").workplane(offset=-50).center(0, 6).rect(3.0, 50.0).extrude(8.0)))
    return s


# ── foot: a hard-surface boot over the flat sole ───────────────────────────────────────────────────

def foot_shell():
    """The foot: a hard-surface BOOT over the flat 240 mm box sole. The SOLE (collision) is unchanged and
    flat (ZMP-stable); this is a faceted upper — a defined TOE CAP (split from the mid-foot by a groove),
    an ANKLE COLLAR where the RMD-X6 ankle actuator seats, a heel counter and a sole-edge bevel. x =
    forward (toe +X), z = up; the flat underside sits at z=0 so the visual sole stays coincident with the
    collision sole top."""
    _need()
    # R5: a SLIMMER, TAPERED shoe (NOT the full 240×110 flat collision slab) so the two close-set feet read
    # as TWO discrete boots instead of merging into one black BASE PLATE. The flat collision box stays
    # 240×110 (physics-locked, ZMP-stable); this VISIBLE boot is narrower (≤92 mm) with a tapered toe + a
    # rounded heel + a contoured instep. A lofted plan-form (narrow heel → wide ball → tapered toe) clipped
    # to a low slab gives a real shoe outline. Underside flat at z=0 (coincident with the sole top).
    plan = (cq.Workplane("XY")
            .workplane(offset=0).center(-104, 0).ellipse(20, 38)      # heel (rounded, narrow)
            .workplane(offset=86).center(-18, 0).ellipse(70, 46)      # arch→ball (widest ≤92 mm)
            .workplane(offset=92).center(74, 0).ellipse(50, 40)       # ball→toe
            .workplane(offset=46).center(120, 0).ellipse(8, 28)       # toe tip (tapered)
            .loft(combine=True))
    # low slab clip: keep it a flat-bottomed shoe ~30 mm tall, hard-ish edges
    slab = (cq.Workplane("XY").box(260, 92, 30).translate((6, 0, 15)).edges("|Z").fillet(14))
    base = plan.intersect(slab)
    base = _safe_fillet(base, ">Z", 8)
    # ankle collar / instep hump (faceted): a clipped lofted hump where the ankle actuator seats
    hump = (cq.Workplane("XY")
            .workplane(offset=20).ellipse(74, 46)
            .workplane(offset=24).ellipse(60, 40)
            .workplane(offset=20).ellipse(30, 22)
            .loft(combine=True).translate((-10, 0, 0)))
    humpbox = (cq.Workplane("XY").box(140, 84, 90).translate((-10, 0, 40)).edges("|Z").fillet(18))
    hump = hump.intersect(humpbox)
    foot = _union(base, hump)
    foot = _safe_fillet(foot, ">Z", 6)
    # TOE-CAP split: a transverse groove across the forefoot separating the toe cap from the mid-foot
    foot = _cut(foot, (cq.Workplane("YZ").workplane(offset=64).center(0, 14).rect(30, 4.0).extrude(96)))
    # a heel counter groove (transverse, at the back)
    foot = _cut(foot, (cq.Workplane("YZ").workplane(offset=-86).center(0, 14).rect(24, 3.0).extrude(92)))
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
    "palm": palm_shell,
    # Round 6: segmented finger phalanx shells (light bodies) + the dark machined knuckle collar.
    "finger_prox": finger_prox_shell,
    "finger_mid": finger_mid_shell,
    "finger_dist": finger_dist_shell,
    "finger_knuckle": finger_knuckle_shell,
}


def build_all(out_dir: str) -> dict:
    """Generate every shell STL into ``out_dir``; return a ``{name: {path, triangles}}`` manifest.

    Every successful entry is guaranteed triangles > 0 (an empty mesh is turned into an error entry, the
    file removed). The solids are watertight by construction (ellipse∩box + interior cuts/unions); the
    STL triangle count + the consuming pipeline's mesh_integrity prove it for the written file. A single
    shell failing must not kill the rest (resilience contract)."""
    manifest = {}
    for name, fn in SHELLS.items():
        try:
            os.makedirs(out_dir, exist_ok=True)
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
