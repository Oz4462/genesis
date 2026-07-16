"""kicad — real, verified KiCad export (Stein 6).

electronics.py carried `generate_kicad_schematic_stub`, which silently dropped
every component past the 8th (`components[:8]`), placed them ALL at the origin
(overlapping), and labelled each as a resistor symbol regardless of kind. This
module replaces that with honest exports plus a VERIFIER — in GENESIS a generator
without a checker is half a feature.

What IS real and verifiable: the KiCad NETLIST — the complete electrical
interchange (every component, every net, every pin connection), importable into
Pcbnew. The verifier proves it: valid S-expression nesting, the export header,
EVERY declared component present (none dropped), and NO node referencing an
undeclared component (no dangling). What is NOT faked: a fully-rendered graphical
schematic needs KiCad's symbol-library geometry and an auto-placer/router; the
`.kicad_sch` here is an honest skeleton — all components GRID-placed (no
all-at-origin overlap) with connectivity via global labels, the symbol graphics
resolved from KiCad libraries on import (a declared gap).

Format refs: KiCad netlist (`.net`) and schematic (`.kicad_sch`) S-expression.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KICAD_SOURCE = "KiCad .net / .kicad_sch S-expression (2026-06-18)"

#: Map a component kind to a generic KiCad library symbol id (graphics resolved by
#: KiCad on import; an unknown kind falls back to a generic symbol — declared, not
#: silently mislabelled as a resistor like the old stub did).
_KIND_TO_LIB = {
    "resistor": "Device:R",
    "capacitor": "Device:C",
    "inductor": "Device:L",
    "diode": "Device:D",
    "fuse": "Device:Fuse",
    "battery": "Device:Battery",
    "connector": "Connector:Conn_01x02",
}
_GENERIC_LIB = "Device:U"


@dataclass(frozen=True)
class KiCadCheck:
    """Verifier verdict — ok plus the concrete issues (empty when ok)."""

    ok: bool
    issues: list[str]
    n_components: int
    n_nets: int


#: A full quoted S-expression string, escape-aware (matches \" and \\ inside).
_STR = r'"((?:[^"\\]|\\.)*)"'


def _esc(s: str) -> str:
    """Escape a string for a KiCad S-expression token (backslash then quote)."""
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def _unesc(s: str) -> str:
    """Inverse of _esc — recover the literal value captured from emitted text."""
    return s.replace('\\"', '"').replace("\\\\", "\\")


def _paren_issues(text: str) -> list[str]:
    """Balanced-parentheses check that ignores parens inside quoted strings."""
    issues: list[str] = []
    depth = 0
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                issues.append("unbalanced parentheses (an extra ')')")
                return issues
    if depth > 0:
        issues.append(f"unbalanced parentheses ({depth} unclosed '(')")
    return issues


def to_kicad_netlist(netlist, components) -> str:
    """Export a complete, valid KiCad netlist (`.net`) S-expression: every component
    and every net with its pin nodes. Strings are escaped; the order follows the
    inputs, so the output is deterministic. Pin references in `Net.pins` are
    ``"{ref}.{pin}"`` (see core.state.Net)."""
    lines = [
        '(export (version "E")',
        "  (design",
        '    (source "genesis_electronics")',
        '    (tool "GENESIS cad.kicad")',
        "  )",
        "  (components",
    ]
    for c in components:
        lines.append(
            f'    (comp (ref "{_esc(c.id)}") (value "{_esc(c.name)}") '
            f'(footprint "{_esc(c.package or "generic")}"))')
    lines.append("  )")
    lines.append("  (nets")
    for i, n in enumerate(netlist.nets):
        nodes = []
        for p in n.pins:
            ref, _, pin = p.partition(".")
            nodes.append(f'(node (ref "{_esc(ref)}") (pin "{_esc(pin)}"))')
        node_str = (" " + " ".join(nodes)) if nodes else ""
        lines.append(f'    (net (code {i + 1}) (name "{_esc(n.name)}"){node_str})')
    lines.append("  )")
    lines.append(")")
    return "\n".join(lines)


def verify_kicad_netlist(text: str, *, components, netlist) -> KiCadCheck:
    """Verify a KiCad netlist is valid + COMPLETE: balanced S-expr, export header,
    every declared component present (none dropped), every net node referencing a
    declared component (no dangling). Non-vacuous: a truncated or dangling netlist
    fails."""
    issues = _paren_issues(text)
    if not text.lstrip().startswith("(export"):
        issues.append("missing (export ...) header")
    for section in ("(components", "(nets"):
        if section not in text:
            issues.append(f"missing {section} section")

    declared = {c.id for c in components}
    comp_list = [_unesc(m) for m in re.findall(r"\(comp \(ref " + _STR, text)]
    comp_refs = set(comp_list)
    if len(comp_list) != len(comp_refs):
        dup = sorted({r for r in comp_list if comp_list.count(r) > 1})
        issues.append(f"duplicate component refs in (components): {dup}")
    for cid in declared:
        if cid not in comp_refs:
            issues.append(f"declared component {cid!r} missing from (components) — dropped")
    for ref in sorted(comp_refs - declared):
        issues.append(f"netlist has undeclared component {ref!r}")

    node_refs = {_unesc(m) for m in re.findall(r"\(node \(ref " + _STR, text)}
    for ref in sorted(node_refs - declared):
        issues.append(f"net node references undeclared component {ref!r} (dangling)")

    # source-level completeness (surfaced before export is persisted): a net with no
    # nodes is floating; an empty ref/pin means a malformed "{ref}.{pin}" reference.
    for n in netlist.nets:
        if not n.pins:
            issues.append(f"net {n.name!r} has no nodes (floating)")
        for p in n.pins:
            ref, sep, pin = p.partition(".")
            if not sep or not ref.strip() or not pin.strip():
                issues.append(f"net {n.name!r} has a malformed pin reference {p!r}")

    return KiCadCheck(ok=not issues, issues=issues,
                      n_components=len(comp_refs), n_nets=len(netlist.nets))


def to_kicad_schematic(components, netlist, *, columns: int = 8, grid_mm: float = 50.0) -> str:
    """Export a KiCad schematic (`.kicad_sch`) SKELETON: ALL components, GRID-placed
    (no all-at-origin overlap), each with its real reference and a kind-appropriate
    generic lib symbol; connectivity via per-net global labels.

    Honest scope: this is a structural CONTENT map (every component + net present and
    placed), NOT a guaranteed drop-in import — a fully-importable schematic needs the
    complete v20231120 schema (per-symbol UUIDs, pin instances, effects) and the
    symbol-library geometry, which are a declared gap. For machine import use the
    NETLIST (to_kicad_netlist); the schematic is for human/structural inspection."""
    lines = [
        '(kicad_sch (version 20231120) (generator "genesis_cad_kicad")',
        '  (paper "A4")',
    ]
    for idx, c in enumerate(components):
        x = (idx % columns) * grid_mm + grid_mm
        y = (idx // columns) * grid_mm + grid_mm
        lib = _KIND_TO_LIB.get((c.kind or "").lower(), _GENERIC_LIB)
        lines.append(
            f'  (symbol (lib_id "{_esc(lib)}") (at {x:g} {y:g} 0) (unit 1) '
            f'(property "Reference" "{_esc(c.id)}" (at {x:g} {y - 5:g} 0)) '
            f'(property "Value" "{_esc(c.name)}" (at {x:g} {y + 5:g} 0)))')
    for idx, n in enumerate(netlist.nets):
        lines.append(
            f'  (global_label "{_esc(n.name)}" (shape input) '
            f'(at {grid_mm:g} {(idx + 1) * 10:g} 0))')
    lines.append('  (sheet_instances (path "/" (page "1")))')
    lines.append(")")
    return "\n".join(lines)


def verify_kicad_schematic(text: str, *, components, netlist=None) -> KiCadCheck:
    """Verify the schematic skeleton: balanced S-expr, kicad_sch header, EVERY
    component present (catches the old `[:8]` silent truncation) at DISTINCT
    positions (catches the old all-at-origin overlap), and — when `netlist` is given
    — one global label per net. Non-vacuous."""
    issues = _paren_issues(text)
    if not text.lstrip().startswith("(kicad_sch"):
        issues.append("missing (kicad_sch ...) header")

    refs = [_unesc(m) for m in re.findall(r'\(property "Reference" ' + _STR, text)]
    declared = {c.id for c in components}
    for cid in declared:
        if cid not in refs:
            issues.append(f"component {cid!r} missing from schematic — silent truncation")

    # capture ONLY the position (lib_id matched non-capturingly) so two different-kind
    # symbols at the SAME (at) are still caught as overlapping.
    positions = re.findall(r'\(symbol \(lib_id "(?:[^"\\]|\\.)*"\) \(at ([^)]*)\)', text)
    if len(positions) != len(set(positions)):
        issues.append("overlapping symbols — duplicate (at x y) positions (all-at-origin?)")

    n_nets = 0
    if netlist is not None:
        n_nets = len(netlist.nets)
        labels = re.findall(r"\(global_label " + _STR, text)
        if len(labels) != n_nets:
            issues.append(f"global-label count {len(labels)} != net count {n_nets}")

    return KiCadCheck(ok=not issues, issues=issues, n_components=len(refs), n_nets=n_nets)


def _is_number(token: str) -> bool:
    """True iff `token` parses as a float — guards the (at x y rot) coordinate check."""
    try:
        float(token)
        return True
    except ValueError:
        return False


def _placement_envelope_mm(placements) -> tuple[float, float, float, float]:
    """Axis-aligned envelope (xmin, ymin, xmax, ymax) of placement centres + keepouts."""
    if not placements:
        return (0.0, 0.0, 100.0, 80.0)
    xs: list[float] = []
    ys: list[float] = []
    for p in placements:
        x, y = float(p.pos_mm[0]), float(p.pos_mm[1])
        ko = getattr(p, "keepout_mm", None) or (10.0, 10.0, 0.0)
        hx = float(ko[0]) / 2.0 if ko else 5.0
        hy = float(ko[1]) / 2.0 if ko else 5.0
        xs.extend([x - hx, x + hx])
        ys.extend([y - hy, y + hy])
    margin = 5.0
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def to_kicad_pcb(
    placements,
    components,
    *,
    thickness_mm: float = 1.6,
    copper_zones: bool = True,
    zone_nets: tuple[str, ...] = ("GND", "PWR"),
    netlist=None,
    autoroute: bool = True,
    track_width_mm: float = 0.25,
) -> str:
    """Export a KiCad PCB (`.kicad_pcb`) placement SKELETON (v20231120): every placement
    as a ``(footprint ...)`` at its ``(at x y z-rotation)``, the footprint id resolved by
    ``ref_des`` from the matching component's package (generic fallback) — NOT by the old
    positional ``zip`` that mis-paired and silently dropped the tail.

    H6: optional rectangular F.Cu **copper zones** (fill pours) for named nets (default
    GND/PWR) covering the placement envelope.

    Residual copper autoroute: when ``autoroute`` and ``netlist`` are set, emits
    Manhattan ``(segment ...)`` tracks between placed components (simple L-paths).
    Not a production autorouter — real segments for package handoff. Full interactive
    DRC still requires KiCad. Strings escaped; deterministic.
    """
    comp_by_ref = {c.id: c for c in components}
    lines = [
        '(kicad_pcb (version 20231120) (generator "genesis_cad_kicad")',
        f"  (general (thickness {thickness_mm:g}))",
        '  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (32 "B.SilkS" user))',
        "  (setup (pad_to_mask_clearance 0))",
    ]
    for p in placements:
        x, y = p.pos_mm[0], p.pos_mm[1]
        rot = p.rot_deg[2] if isinstance(p.rot_deg, (tuple, list)) else (p.rot_deg or 0.0)
        comp = comp_by_ref.get(p.ref_des)
        fp = p.footprint or (getattr(comp, "package", "") or "") or "Genesis:Generic_SMD"
        lines.append(
            f'  (footprint "{_esc(fp)}" (layer "F.Cu") (at {x:g} {y:g} {rot:g}) '
            f'(fp_text reference "{_esc(p.ref_des)}" (at 0 0 {rot:g}) (layer "F.SilkS")))')
    if copper_zones and placements:
        xmin, ymin, xmax, ymax = _placement_envelope_mm(placements)
        for i, net in enumerate(zone_nets):
            # slight inset so zones don't claim identical polygons (layer separation)
            inset = float(i) * 0.5
            lines.append(
                f'  (zone (net 0) (net_name "{_esc(net)}") (layer "F.Cu") '
                f"(hatch edge 0.5) (connect_pads (clearance 0.2)) "
                f"(fill yes (thermal_gap 0.3) (thermal_bridge_width 0.3)) "
                f"(polygon (pts "
                f"(xy {xmin + inset:g} {ymin + inset:g}) "
                f"(xy {xmax - inset:g} {ymin + inset:g}) "
                f"(xy {xmax - inset:g} {ymax - inset:g}) "
                f"(xy {xmin + inset:g} {ymax - inset:g}))))"
            )
    if autoroute and netlist is not None and placements:
        tracks = manhattan_autoroute(
            placements, netlist, track_width_mm=track_width_mm
        )
        lines.extend(tracks_to_kicad_sexpr(tracks))
    lines.append(")")
    return "\n".join(lines)


def manhattan_autoroute(
    placements,
    netlist,
    *,
    track_width_mm: float = 0.25,
    layer: str = "F.Cu",
) -> list[dict]:
    """Simple Manhattan (orthogonal) copper tracks between nets with ≥2 placed pins.

    Algorithm: for each net, take the first two components that appear in
    ``placements`` and connect their centres with an L-shaped track
    (horizontal then vertical). Not a production autorouter — closes the
    "no copper routing" gap with real track segments verifiable in the PCB text.

    Returns list of {net, points: [(x,y),...], width_mm, layer}.
    """
    if track_width_mm <= 0 or track_width_mm != track_width_mm:
        raise ValueError("manhattan_autoroute: track_width_mm must be finite > 0")
    pos = {p.ref_des: (float(p.pos_mm[0]), float(p.pos_mm[1])) for p in placements}
    nets = getattr(netlist, "nets", None) or []
    tracks: list[dict] = []
    for n in nets:
        name = getattr(n, "name", None) or (n.get("name") if isinstance(n, dict) else None)
        pins = getattr(n, "pins", None) or (n.get("pins") if isinstance(n, dict) else None) or []
        refs: list[str] = []
        for pin in pins:
            ref = str(pin).split(".", 1)[0]
            if ref in pos and ref not in refs:
                refs.append(ref)
        if len(refs) < 2:
            continue
        (x0, y0), (x1, y1) = pos[refs[0]], pos[refs[1]]
        # L-path: (x0,y0) → (x1,y0) → (x1,y1)
        points = [(x0, y0), (x1, y0), (x1, y1)]
        tracks.append(
            {
                "net": str(name or ""),
                "from": refs[0],
                "to": refs[1],
                "points": points,
                "width_mm": track_width_mm,
                "layer": layer,
            }
        )
    return tracks


def tracks_to_kicad_sexpr(tracks: list[dict]) -> list[str]:
    """Serialize Manhattan tracks as KiCad ``(segment ...)`` lines (v20231120-ish)."""
    lines: list[str] = []
    for t in tracks:
        pts = t.get("points") or []
        w = float(t.get("width_mm") or 0.25)
        layer = t.get("layer") or "F.Cu"
        for a, b in zip(pts, pts[1:]):
            lines.append(
                f'  (segment (start {a[0]:g} {a[1]:g}) (end {b[0]:g} {b[1]:g}) '
                f'(width {w:g}) (layer "{_esc(layer)}") '
                f'(net 0) (tstamp "genesis-route"))'
            )
    return lines


def placement_clearance_drc(
    placements,
    *,
    min_clearance_mm: float = 0.2,
) -> dict:
    """H6: internal placement clearance DRC (AABB keepouts), not full copper DRC.

    Returns ``{ok, violations, n_checked, min_clearance_mm, gaps}``. Overlapping
    keepout boxes produce violations. Does **not** claim KiCad copper-to-copper DRC.
    """
    if min_clearance_mm < 0 or min_clearance_mm != min_clearance_mm:
        raise ValueError("placement_clearance_drc: min_clearance_mm must be finite >= 0")
    violations: list[dict] = []
    items = list(placements or [])
    for i, a in enumerate(items):
        ax, ay = float(a.pos_mm[0]), float(a.pos_mm[1])
        ako = getattr(a, "keepout_mm", None) or (5.0, 5.0, 0.0)
        ahx, ahy = float(ako[0]) / 2.0, float(ako[1]) / 2.0
        for b in items[i + 1 :]:
            bx, by = float(b.pos_mm[0]), float(b.pos_mm[1])
            bko = getattr(b, "keepout_mm", None) or (5.0, 5.0, 0.0)
            bhx, bhy = float(bko[0]) / 2.0, float(bko[1]) / 2.0
            # gap between boxes along each axis (negative = overlap)
            dx = abs(ax - bx) - (ahx + bhx)
            dy = abs(ay - by) - (ahy + bhy)
            if dx < min_clearance_mm and dy < min_clearance_mm:
                violations.append(
                    {
                        "type": "placement_clearance",
                        "severity": "fail" if dx < 0 or dy < 0 else "warn",
                        "a": getattr(a, "ref_des", "?"),
                        "b": getattr(b, "ref_des", "?"),
                        "gap_x_mm": round(dx, 3),
                        "gap_y_mm": round(dy, 3),
                        "min_clearance_mm": min_clearance_mm,
                    }
                )
    return {
        "ok": not any(v["severity"] == "fail" for v in violations),
        "violations": violations,
        "n_checked": len(items),
        "min_clearance_mm": min_clearance_mm,
        "gaps": [
            "full copper pour / track DRC requires KiCad or an external DRC engine",
            "this check is keepout AABB only (placement clearance)",
        ],
        "quelle": "gen.cad.kicad.placement_clearance_drc (H6)",
    }


def verify_kicad_pcb(
    text: str, *, placements, require_copper_zones: bool = False
) -> KiCadCheck:
    """Verify a KiCad PCB skeleton: balanced S-expr, kicad_pcb header, the (layers) and
    (footprint) sections, EVERY placement's ref_des emitted as a footprint reference
    (catches the old positional-zip drop), and every ``(at ...)`` numeric (catches the
    old rot-tuple leak ``(at 1 1 (0.0, 0.0, 90.0))``). Non-vacuous.

    H6: when ``require_copper_zones`` is True, at least one ``(zone`` block must exist.
    """
    issues = _paren_issues(text)
    if not text.lstrip().startswith("(kicad_pcb"):
        issues.append("missing (kicad_pcb ...) header")
    for section in ("(layers", "(footprint"):
        if section not in text:
            issues.append(f"missing {section} section")

    refs = {_unesc(m) for m in re.findall(r"\(fp_text reference " + _STR, text)}
    declared = {p.ref_des for p in placements}
    for ref in sorted(declared - refs):
        issues.append(f"placement {ref!r} missing from the .kicad_pcb — dropped")

    for at in re.findall(r"\(at ([^)]*)\)", text):
        if not at.split() or not all(_is_number(t) for t in at.split()):
            issues.append(f"malformed (at {at}) — non-numeric placement coordinate")

    if require_copper_zones and "(zone" not in text:
        issues.append("missing (zone ...) copper pour blocks (H6 require_copper_zones)")

    return KiCadCheck(ok=not issues, issues=issues, n_components=len(refs), n_nets=0)
