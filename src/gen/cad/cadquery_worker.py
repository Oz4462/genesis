"""CadQuery worker — runs INSIDE the isolated cad venv (/home/genesis/.venv-cad).

This script is NEVER imported by the main GENESIS package. It is executed as a
subprocess by ``cad.cadquery_bridge`` using the cad-venv interpreter, because
importing ``cadquery`` into the main ``.venv`` downgrades numpy and breaks the rest
of GENESIS. All OpenCASCADE work (build the CSG solid, boolean ops, fillet, exact
volume / validity / interference, tessellation, STEP/STL export) happens HERE and
only serialisable results (numbers, booleans, STEP/STL text) cross back.

Protocol (stdin -> stdout, both JSON, one request per invocation):

  request  = {"op": <str>, "node": <csg>, "values": {qid: float}, ...op args...}
  csg      = {"kind": <str>, "params": {name: qid}, "children": [csg, ...]}
  response = {"ok": true,  "result": <json>}        on success
           | {"ok": false, "error": "<ExcType>: <msg>"}  on any failure

Ops:
  "volume"      -> result: float (exact OCCT solid volume)
  "valid"       -> result: bool  (BRepCheck topological validity)
  "interferes"  -> args: node_b, tolerance; result: bool (intersection vol > tol)
  "stl"         -> args: tolerance, name; result: str (ASCII STL, kernel winding)
  "step"        -> result: str (STEP AP214 text)

Geometry convention matches the rest of GENESIS: primitives CENTERED at the origin
(see PHASE_DELTA.md §1 / export/openscad.py). A failure is reported as a typed
error string, never a fabricated number — the bridge re-raises it loudly.
"""

from __future__ import annotations

import json
import sys


def _val(qid, values):
    if qid not in values:
        raise KeyError(f"geometry references unknown quantity {qid!r}")
    return float(values[qid])


def build_solid(node, values):
    """Translate a serialised CSG dict into an OpenCASCADE solid (cadquery)."""
    from cadquery import Solid, Vector  # imported in the cad venv only

    kind = node["kind"]
    params = node.get("params", {})
    children = node.get("children", [])

    if kind == "box":
        sx = _val(params["size_x"], values)
        sy = _val(params["size_y"], values)
        sz = _val(params["size_z"], values)
        return Solid.makeBox(sx, sy, sz, Vector(-sx / 2, -sy / 2, -sz / 2))
    if kind == "cylinder":
        r = _val(params["radius"], values)
        h = _val(params["height"], values)
        return Solid.makeCylinder(r, h, Vector(0, 0, -h / 2), Vector(0, 0, 1))
    if kind == "sphere":
        r = _val(params["radius"], values)
        return Solid.makeSphere(r, Vector(0, 0, 0), Vector(0, 0, 1), -90, 90, 360)

    if kind == "translate":
        child = build_solid(children[0], values)
        x = _val(params["x"], values)
        y = _val(params["y"], values)
        z = _val(params["z"], values)
        return child.translate(Vector(x, y, z))
    if kind == "rotate":
        child = build_solid(children[0], values)
        ax = _val(params["axis_x"], values)
        ay = _val(params["axis_y"], values)
        az = _val(params["axis_z"], values)
        if (ax * ax + ay * ay + az * az) ** 0.5 < 1e-12:
            raise ValueError("rotate axis must be non-zero")
        angle = _val(params["angle_deg"], values)
        return child.rotate(Vector(0, 0, 0), Vector(ax, ay, az), angle)

    if kind in ("union", "difference", "intersection"):
        solids = [build_solid(c, values) for c in children]
        if not solids:
            raise ValueError(f"{kind!r} operation has no children")
        result = solids[0]
        for other in solids[1:]:
            if kind == "union":
                result = result.fuse(other)
            elif kind == "difference":
                result = result.cut(other)
            else:
                result = result.intersect(other)
        return result

    raise ValueError(f"unknown geometry kind {kind!r}")


def _facet(a, b, c):
    """One ASCII-STL facet from three tessellation vertices (kernel winding kept)."""
    ux, uy, uz = b.x - a.x, b.y - a.y, b.z - a.z
    vx, vy, vz = c.x - a.x, c.y - a.y, c.z - a.z
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length < 1e-15:
        return None
    nx, ny, nz = nx / length, ny / length, nz / length
    return (
        f"  facet normal {nx:.6e} {ny:.6e} {nz:.6e}\n"
        "    outer loop\n"
        f"      vertex {a.x:.6e} {a.y:.6e} {a.z:.6e}\n"
        f"      vertex {b.x:.6e} {b.y:.6e} {b.z:.6e}\n"
        f"      vertex {c.x:.6e} {c.y:.6e} {c.z:.6e}\n"
        "    endloop\n"
        "  endfacet\n"
    )


def solid_to_stl(solid, *, name: str, tolerance: float) -> str:
    """Tessellate a solid to ASCII STL (one ``solid`` block, kernel outward winding)."""
    verts, tris = solid.tessellate(tolerance)
    chunks = [f"solid genesis_{name}\n"]
    n = 0
    for i, j, k in tris:
        f = _facet(verts[i], verts[j], verts[k])
        if f is not None:
            chunks.append(f)
            n += 1
    if n == 0:
        raise ValueError(f"tessellation produced no facets for {name!r} (degenerate)")
    chunks.append(f"endsolid genesis_{name}\n")
    return "".join(chunks)


def solid_to_step(solid) -> str:
    """Export a solid to a STEP AP214 string (the exact-BREP interchange format)."""
    import os
    import tempfile

    import cadquery as cq
    from cadquery import exporters

    wp = cq.Workplane(obj=solid)
    path = tempfile.mktemp(suffix=".step")
    try:
        exporters.export(wp, path)
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    finally:
        if os.path.exists(path):
            os.remove(path)


def handle(req: dict) -> dict:
    op = req["op"]
    values = req.get("values", {})
    node = req.get("node")

    if op == "volume":
        return {"result": float(build_solid(node, values).Volume())}
    if op == "valid":
        return {"result": bool(build_solid(node, values).isValid())}
    if op == "interferes":
        a = build_solid(node, values)
        b = build_solid(req["node_b"], values)
        tol = float(req.get("tolerance", 1e-9))
        inter = a.intersect(b)
        try:
            vol = float(inter.Volume())
        except Exception:  # noqa: BLE001 - empty intersection can be a null shape
            return {"result": False}
        return {"result": vol > tol}
    if op == "stl":
        solid = build_solid(node, values)
        return {
            "result": solid_to_stl(
                solid,
                name=str(req.get("name", "part")),
                tolerance=float(req.get("tolerance", 0.1)),
            )
        }
    if op == "step":
        return {"result": solid_to_step(build_solid(node, values))}

    raise ValueError(f"unknown op {op!r}")


def main() -> int:
    raw = sys.stdin.read()
    try:
        req = json.loads(raw)
        out = handle(req)
        sys.stdout.write(json.dumps({"ok": True, **out}))
        return 0
    except Exception as exc:  # noqa: BLE001 - any failure -> typed error string back
        sys.stdout.write(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        )
        return 0  # protocol-level success; the error is in the payload


if __name__ == "__main__":
    raise SystemExit(main())
