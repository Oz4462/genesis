"""build123d drawing worker — runs INSIDE the isolated build123d venv.

This script is NEVER imported by the main GENESIS package. It is executed as a
subprocess by ``export.drawing`` using the build123d-venv interpreter, because
``build123d`` (like ``cadquery``) pulls an OpenCASCADE/numpy stack that is kept out of
the main ``.venv``. All build123d work — build the CSG solid, take a planar SECTION,
export a 2-D manufacturing drawing as DXF or SVG — happens HERE; only serialisable
results (the DXF/SVG text + a few section metrics) cross back.

Protocol (stdin -> stdout, both JSON, one request per invocation):

  request  = {"op": "section_dxf"|"section_svg"|"section_info",
              "node": <csg>, "values": {qid: float},
              "plane": "XY"|"XZ"|"YZ", "offset": <float>}
  csg      = {"kind": <str>, "params": {name: qid}, "children": [csg, ...]}
  response = {"ok": true,  "result": <json>}            on success
           | {"ok": false, "error": "<ExcType>: <msg>"} on any failure

Ops:
  "section_dxf"  -> result: str   (the DXF text of the planar section)
  "section_svg"  -> result: str   (the SVG text of the planar section)
  "section_info" -> result: dict  (n_faces, n_edges, bbox) of the section sketch

Geometry convention matches the rest of GENESIS: build123d primitives are CENTERED at
the origin (verified: ``Box(l,w,h)`` spans −l/2..l/2 etc.), like export/openscad.py and
cad/cadquery_worker.py. A failure is reported as a typed error string, never a fabricated
drawing — the bridge re-raises it loudly.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

# This worker lives next to ``export/build123d.py`` (GENESIS' own build123d code
# EXPORTER, a different thing from the build123d LIBRARY). When run as a script, the
# worker's own directory is on sys.path[0], which would shadow the real ``build123d``
# package with that sibling module — so ``import build123d`` would import the wrong one
# and fail. Strip this directory from sys.path so the genuine library is imported.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _HERE]


def _val(qid, values):
    if qid not in values:
        raise KeyError(f"geometry references unknown quantity {qid!r}")
    return float(values[qid])


def build_part(node, values):
    """Translate a serialised CSG dict into a build123d ``Part`` (algebra mode)."""
    from build123d import Box, Cylinder, Pos, Sphere  # build123d venv only

    kind = node["kind"]
    params = node.get("params", {})
    children = node.get("children", [])

    if kind == "box":
        sx = _val(params["size_x"], values)
        sy = _val(params["size_y"], values)
        sz = _val(params["size_z"], values)
        return Box(sx, sy, sz)
    if kind == "cylinder":
        r = _val(params["radius"], values)
        h = _val(params["height"], values)
        return Cylinder(r, h)
    if kind == "sphere":
        r = _val(params["radius"], values)
        return Sphere(r)

    if kind == "translate":
        child = build_part(children[0], values)
        x = _val(params["x"], values)
        y = _val(params["y"], values)
        z = _val(params["z"], values)
        return Pos(x, y, z) * child
    if kind == "rotate":
        from build123d import Axis

        child = build_part(children[0], values)
        ax = _val(params["axis_x"], values)
        ay = _val(params["axis_y"], values)
        az = _val(params["axis_z"], values)
        if (ax * ax + ay * ay + az * az) ** 0.5 < 1e-12:
            raise ValueError("rotate axis must be non-zero")
        angle = _val(params["angle_deg"], values)
        return child.rotate(Axis((0, 0, 0), (ax, ay, az)), angle)

    if kind in ("union", "difference", "intersection"):
        parts = [build_part(c, values) for c in children]
        if not parts:
            raise ValueError(f"{kind!r} operation has no children")
        result = parts[0]
        for other in parts[1:]:
            if kind == "union":
                result = result + other
            elif kind == "difference":
                result = result - other
            else:
                result = result & other
        return result

    raise ValueError(f"unknown geometry kind {kind!r}")


def _plane(name: str, offset: float):
    """A build123d cutting plane by name, shifted by ``offset`` along its normal."""
    from build123d import Plane

    base = {"XY": Plane.XY, "XZ": Plane.XZ, "YZ": Plane.YZ}.get(name)
    if base is None:
        raise ValueError(f"plane must be one of XY/XZ/YZ, got {name!r}")
    if offset:
        return base.offset(offset)
    return base


def _section(node, values, plane_name, offset):
    """Build the part and return its planar section as a build123d ``Sketch``.

    Non-XY sections are ROTATED into the XY plane before export: the DXF/SVG
    exporters are 2-D (XY) writers, and an XZ/YZ-embedded sketch would trigger
    ezdxf's "non-planar shape" path (points outside XY, warning noise on
    stdout). The rotation is a rigid map of the true cut profile — no shape
    change, just the drawing convention."""
    from build123d import Axis, section

    part = build_part(node, values)
    sec = section(part, section_by=_plane(plane_name, offset))
    if len(sec.faces()) == 0:
        raise ValueError(
            f"section on plane {plane_name} (offset {offset}) is empty — the plane does "
            f"not cut the solid; pick a plane/offset that intersects the part"
        )
    if plane_name == "XZ":
        sec = sec.rotate(Axis.X, 90)
    elif plane_name == "YZ":
        sec = sec.rotate(Axis.Y, -90)
    return sec


def _write_dxf(sec) -> str:
    from build123d import ExportDXF, Unit

    exporter = ExportDXF(unit=Unit.MM)
    exporter.add_shape(sec)
    path = tempfile.mktemp(suffix=".dxf")
    try:
        exporter.write(path)
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    finally:
        if os.path.exists(path):
            os.remove(path)


def _write_svg(sec) -> str:
    from build123d import ExportSVG, Unit

    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_shape(sec)
    path = tempfile.mktemp(suffix=".svg")
    try:
        exporter.write(path)
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    finally:
        if os.path.exists(path):
            os.remove(path)


def handle(req: dict) -> dict:
    op = req["op"]
    values = req.get("values", {})
    node = req.get("node")
    plane = req.get("plane", "XY")
    offset = float(req.get("offset", 0.0))

    sec = _section(node, values, plane, offset)
    if op == "section_dxf":
        return {"result": _write_dxf(sec)}
    if op == "section_svg":
        return {"result": _write_svg(sec)}
    if op == "section_info":
        bb = sec.bounding_box()
        return {
            "result": {
                "n_faces": len(sec.faces()),
                "n_edges": len(sec.edges()),
                "bbox_min": [bb.min.X, bb.min.Y, bb.min.Z],
                "bbox_max": [bb.max.X, bb.max.Y, bb.max.Z],
            }
        }
    raise ValueError(f"unknown op {op!r}")


def main() -> int:
    raw = sys.stdin.read()
    try:
        import contextlib
        import io

        req = json.loads(raw)
        # Libraries (ezdxf/build123d) print warnings to stdout, which would
        # corrupt the JSON protocol — capture and forward them to stderr.
        noise = io.StringIO()
        with contextlib.redirect_stdout(noise):
            out = handle(req)
        if noise.getvalue():
            sys.stderr.write(noise.getvalue())
        sys.stdout.write(json.dumps({"ok": True, **out}))
        return 0
    except Exception as exc:  # noqa: BLE001 - any failure -> typed error string back
        sys.stdout.write(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        )
        return 0  # protocol-level success; the error is in the payload


if __name__ == "__main__":
    raise SystemExit(main())
