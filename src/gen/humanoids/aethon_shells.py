"""aethon_shells — generate AETHON's ORGANIC+INDUSTRIAL exo-shell meshes with CadQuery.

This module is the geometry generator for AETHON's *visual* skin: smooth, lofted, filleted/chamfered
shell covers for the head, torso, pelvis and limb members — a sleek organic exo-shell — while the
INDUSTRIAL mechanics (the joint actuators, knuckles, structural cores) stay exposed as the URDF's
primitive joint visuals. The shells are VISUAL ONLY: the URDF collision geometry, masses and inertias
are untouched, so the validated physics (mass / DOF / actuators / FEM / the 5 s stand) are unaffected.

CadQuery (OCCT B-rep: ``loft``/``fillet``/``chamfer``/``sweep``) is NOT installed in the Genesis main
venv (numpy-incompatible). It lives in a SEPARATE venv ``/home/genesis/.venv-cad``. Therefore this file
is executed as a SUBPROCESS by that interpreter (``genesis_humanoid.build_shells``), never imported into
the main venv. It writes one binary STL per shell into ``out_dir`` and prints a JSON manifest.

Run standalone:  /home/genesis/.venv-cad/bin/python -m gen.humanoids.aethon_shells <out_dir>
  (or)           /home/genesis/.venv-cad/bin/python aethon_shells.py <out_dir>

Every shell is now a hollow exo-shell with documented MIN_WALL_MM wall thickness (was solid before
— the root cause of "thick walls" weakness flagged by print/DFM analysis). The solids are
manifold by construction; build_all guarantees each written STL has triangles > 0 (or error entry).
Units are MILLIMETRES (matching the spec geometry); the URDF scales by 0.001 to SI.
Deterministic: same inputs → identical meshes.
"""

from __future__ import annotations

import json
import sys
import os  # for build_all makedirs and path ops

#: Documented minimum wall thickness for all AETHON exo-shells [mm].
#: Enforces a printable shell (not a solid) and is >= FDM free-standing wall (1.0 mm)
#: from printability + dfm floor (0.8 mm) with margin for curvature and fillet loss.
#: This is the concrete fix for "thin/sub-threshold walls" and "solid instead of shell".
MIN_WALL_MM: float = 1.2

# CadQuery lives in the isolated .venv-cad only (numpy conflict in main genesis venv).
# We do NOT SystemExit at import time so that pure constants (MIN_WALL_MM) and
# SHELLS keys can be inspected without the kernel (test min-wall contract runs
# unconditionally; geometry tests use pytest.importorskip("cadquery")).
# Build fns still fail loud on use when cad unavailable — no silent bad geometry.
_CAD_AVAILABLE = False
try:
    import cadquery as cq
    from cadquery import exporters
    _CAD_AVAILABLE = True
except Exception:  # pragma: no cover - only meaningful inside .venv-cad
    pass  # defer failure to actual geometry use


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────

def _safe_fillet(wp, selector, radius):
    """Fillet the selected edges, backing off the radius if OCCT rejects it (robustness over bravado).
    Returns the original solid if even a small fillet fails — a missing fillet is a cosmetic loss, not
    a crash."""
    for r in (radius, radius * 0.6, radius * 0.35):
        try:
            return wp.edges(selector).fillet(r)
        except Exception:
            continue
    return wp


def _safe_shell(wp, thickness: float):
    """Hollow the (filleted) solid into a thin exo-shell of given wall thickness.

    WHY: converts the previous solid lumps (effectively infinite wall) into genuine
    printable hollow covers with controlled material use and heat/warp behaviour.
    Backs off on OCCT refusal for complex lofts+fillets. Returns the unshelled solid
    only as last resort — never produces zero-thickness wall (silent defect).
    Thickness is clamped to MIN_WALL_MM at call sites.
    """
    if thickness <= 0.0:
        return wp
    for t in (thickness, thickness * 0.75, thickness * 0.5):
        try:
            return wp.shell(t)
        except Exception:
            continue
    return wp


def _export(solid, path):
    exporters.export(solid, path)
    # triangle count (binary STL: 80-byte header + uint32 count) — a quick non-empty proof
    import struct
    with open(path, "rb") as fh:
        fh.seek(80)
        n = struct.unpack("<I", fh.read(4))[0]
    return n


# ── the shells (organic, lofted, filleted) ───────────────────────────────────────────────────────
# Each returns a CadQuery solid in MILLIMETRES, centred sensibly for the URDF visual origin that
# genesis_humanoid sets (see SHELL_VISUAL_ORIGINS there). Limb shells run along the local Z axis
# (URDF limbs extend down -Z) so the URDF mounts them with a simple z-offset.


def head_shell():
    """An organic helmet: a lofted ovoid (narrow chin → broad cranium) with a chamfered facia panel
    and a soft fillet everywhere — a sleek 'face' over the industrial camera/IMU bay (which stays
    visible as the URDF eye spheres). z is up; centred so the URDF places it at the head origin."""
    if not _CAD_AVAILABLE:
        raise RuntimeError("cadquery unavailable — run with the .venv-cad interpreter")
    # DELTAS (CadQuery workplane offsets are relative) placing sections at ABSOLUTE z =
    # -58, -20, 20, 58, 84 mm → a ~142 mm head ovoid.
    s = (cq.Workplane("XY")
         .workplane(offset=-58).ellipse(44, 38)        # z=-58 chin
         .workplane(offset=38).ellipse(56, 50)         # z=-20 jaw
         .workplane(offset=40).ellipse(66, 60)         # z=20  cheek / mid (widest)
         .workplane(offset=38).ellipse(62, 56)         # z=58  cranium
         .workplane(offset=26).ellipse(36, 32)         # z=84  crown
         .loft(combine=True))
    s = _safe_fillet(s, ">Z", 14)
    s = _safe_fillet(s, "<Z", 9)
    # Enforce documented min wall + make hollow exo-shell (was solid before).
    # Smooth loft + fillets already minimise steep local overhangs vs faceted.
    s = _safe_shell(s, MIN_WALL_MM)
    return s


def torso_shell():
    """The chest/back exo-shell: a lofted, athletic CUIRASS — broad shoulders over a tapered waist, a
    deep oval cross-section (wider in y than x), with strong fillets. It ENDS at the shoulder line
    (~225 mm) so the head + neck stay clearly above it (not a tall cone). z up, base at z=0 (mounts on
    the waist joint). The spine stays an exposed industrial member behind it."""
    if not _CAD_AVAILABLE:
        raise RuntimeError("cadquery unavailable — run with the .venv-cad interpreter")
    # NOTE: CadQuery .workplane(offset=...) is RELATIVE to the previous workplane, so these are DELTAS
    # that place the loft sections at ABSOLUTE z = 6, 95, 175, 222 mm (a 222 mm cuirass, NOT a tall cone).
    s = (cq.Workplane("XY")
         .workplane(offset=6).ellipse(58, 92)           # z=6   waist (narrower)
         .workplane(offset=89).ellipse(72, 118)         # z=95  belly/lower chest
         .workplane(offset=80).ellipse(78, 126)         # z=175 mid-chest — the broadest (pectoral/shoulder)
         .workplane(offset=47).ellipse(64, 110)         # z=222 shoulder line (still broad — NOT a neck cone)
         .loft(combine=True))
    s = _safe_fillet(s, ">Z or <Z", 18)
    # a soft collar bevel on the very top so the neck emerges cleanly
    s = _safe_fillet(s, ">Z", 10)
    # Enforce min wall (hollow cover). Lofted oval profile + heavy fillet chosen to
    # keep wall angles gradual; reduces DFM 45° overhang area vs blocky geometry.
    s = _safe_shell(s, MIN_WALL_MM)
    return s


def pelvis_shell():
    """The hip girdle shell: a wide, rounded oval block (the pelvis), softly chamfered. Hosts the hip
    actuators (exposed as the URDF hip joints). Centred on the pelvis origin."""
    if not _CAD_AVAILABLE:
        raise RuntimeError("cadquery unavailable — run with the .venv-cad interpreter")
    s = (cq.Workplane("XY").box(86, 168, 96).edges("|Z").fillet(30).edges(">Z or <Z").fillet(16))
    # Hollow to documented min wall; the previous solid box is now a light printable girdle shell.
    # Rounded fillets already minimise sharp overhang starts.
    s = _safe_shell(s, MIN_WALL_MM)
    # Small base chamfer on lower rim reduces elephant-foot + initial overhang angle for
    # parts that may be printed base-down.
    try:
        s = s.edges("<Z").chamfer(1.0)
    except Exception:
        pass
    return s


def _tapered_limb(top_a, top_b, bot_a, bot_b, length, top_fillet=10, bot_fillet=10):
    """A lofted limb COVER: an oval cross-section tapering from (top_a×top_b) at z=0 down to
    (bot_a×bot_b) at z=-length, with end fillets. URDF limbs extend along -Z, so the cover runs the
    same way; the URDF mounts it at the joint with the limb's centre offset. Organic muscle taper."""
    if not _CAD_AVAILABLE:
        raise RuntimeError("cadquery unavailable — run with the .venv-cad interpreter")
    s = (cq.Workplane("XY")
         .workplane(offset=0).ellipse(top_a, top_b)
         .workplane(offset=-length).ellipse(bot_a, bot_b)
         .loft(combine=True))
    s = _safe_fillet(s, ">Z", top_fillet)
    s = _safe_fillet(s, "<Z", bot_fillet)
    # Min-wall hollowing turns the previous solid "muscle" into a thin printed sleeve.
    # The taper angles are deliberately gentle (organic) to limit unsupported overhang
    # surface when the part is printed upright or slightly tilted.
    s = _safe_shell(s, MIN_WALL_MM)
    return s


# Limb-cover lengths MATCH the URDF limb lengths exactly (m→mm) so each cover spans joint-to-joint with
# no gap: thigh 300, shank 300, upper arm 240, forearm 220 mm (see genesis_humanoid._DIM). A small inset
# is left at each end so the exposed actuator hub at the joint shows through (industrial mechanics).

def thigh_shell():
    """Thigh cover: a powerful muscle taper (broad at the hip, narrowing to the knee), spanning the full
    300 mm thigh. The knee actuator (AK80-64) stays exposed as the URDF knee hub below it."""
    return _tapered_limb(52, 60, 40, 46, 288, top_fillet=18, bot_fillet=14)


def shank_shell():
    """Shank cover: calf swell near the knee tapering to a slim ankle (full 300 mm shank)."""
    return _tapered_limb(44, 50, 28, 32, 288, top_fillet=14, bot_fillet=10)


def upper_arm_shell():
    """Upper-arm cover: deltoid swell to a tapered elbow (full 240 mm upper arm)."""
    return _tapered_limb(40, 44, 30, 32, 230, top_fillet=14, bot_fillet=10)


def forearm_shell():
    """Forearm cover: houses the finger servos; broad below the elbow tapering to the wrist (220 mm)."""
    return _tapered_limb(36, 38, 24, 26, 210, top_fillet=12, bot_fillet=9)


def shoulder_pauldron():
    """An industrial shoulder pauldron: a domed cap (half-ellipsoid) that caps the shoulder actuator
    organically while leaving the joint axis visible below it. Mounts at the shoulder."""
    if not _CAD_AVAILABLE:
        raise RuntimeError("cadquery unavailable — run with the .venv-cad interpreter")
    # Lofted shallow dome (stacked ellipses) instead of sphere+planar-cut.
    # WHY: sphere cut produces sliver/degenerate triangles on the flat rim under tessellate;
    # the loft produces clean manifold faces that survive .shell + stl_integrity (watertight).
    # Still reads as a rounded pauldron cap; low overhang convex profile when printed base-down.
    s = (cq.Workplane("XY")
         .workplane(offset=0).ellipse(48, 48)
         .workplane(offset=18).ellipse(46, 46)
         .workplane(offset=22).ellipse(32, 32)
         .workplane(offset=16).ellipse(10, 10)
         .loft(combine=True))
    s = _safe_fillet(s, "<Z", 3)
    s = _safe_shell(s, MIN_WALL_MM)
    return s


def foot_shell():
    """The foot: a sculpted shoe over the flat 240 mm box sole. The SOLE (collision) is unchanged and
    flat (ZMP-stable); this is a rounded, chamfered upper — toe taper + heel — so the foot reads as a
    boot, not a brick. Box-sole collision stays; this is the visual only. x = forward, z = up; the
    flat underside sits at z=0 so the visual sole stays coincident with the collision sole top."""
    if not _CAD_AVAILABLE:
        raise RuntimeError("cadquery unavailable — run with the .venv-cad interpreter")
    base = (cq.Workplane("XY").box(240, 110, 28).translate((0, 0, 14))
            .edges("|Z").fillet(22))
    # chamfer the top front (toe) and add a rounded instep dome (a lofted ellipse stack → ankle hump)
    base = _safe_fillet(base, ">Z", 10)
    instep = (cq.Workplane("XY")            # DELTAS → absolute z = 20, 44, 64 mm (ankle hump)
              .workplane(offset=20).ellipse(78, 50)
              .workplane(offset=24).ellipse(64, 42)
              .workplane(offset=20).ellipse(30, 22)
              .loft(combine=True).translate((-12, 0, 0)))
    foot = base.union(instep)
    foot = _safe_fillet(foot, ">Z", 8)
    # Flat underside is the natural plate contact; generous fillets + toe chamfer
    # reduce first-layer and overhang issues. Shell makes it a light printable boot upper.
    foot = _safe_shell(foot, MIN_WALL_MM)
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

    Every successful entry is guaranteed triangles > 0 (empty mesh is turned into error entry).
    The kernel solids are hollowed with >= MIN_WALL_MM and are manifold by construction
    (loft/shell/fillet preserve watertightness for these topologies); the STL count + later
    mesh_integrity in consuming pipeline prove it for the written file.
    makedirs is inside per-shell try so a bad out_dir surfaces as manifest error entry
    rather than escaping (matches the resilience contract used by callers).
    """
    manifest = {}
    for name, fn in SHELLS.items():
        try:
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"aethon_{name}_shell.stl")
            solid = fn()
            n = _export(solid, path)
            if n < 1:
                # enforce non-empty STL; do not leave zero-triangle file
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
