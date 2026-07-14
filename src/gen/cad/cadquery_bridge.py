"""Bridge to the isolated CadQuery venv (the exact-OCCT-BREP path, made usable).

GENESIS's main ``.venv`` deliberately does NOT contain ``cadquery``: installing it
there downgrades numpy and breaks the rest of the stack. CadQuery lives in a
SEPARATE interpreter (``/home/genesis/.venv-cad``). This module is the bridge: it
serialises a GENESIS CSG tree to JSON, runs ``cad/cadquery_worker.py`` under the
cad-venv interpreter as a subprocess, and parses back only serialisable results
(exact volume, validity, interference, print-ready STL, STEP). No OCCT object —
and no ``import cadquery`` — ever enters the main process.

This is the wiring that turns brep.py's exact-OCCT path from "needs cadquery in the
main venv (impossible)" into a working capability: ``brep.py`` now delegates here.

Configuration (env, with a sane default):
  * ``GENESIS_CAD_PYTHON`` — path to the cad-venv interpreter
    (default ``/home/genesis/.venv-cad/bin/python``).

Failure is LOUD and typed (CLAUDE.md: no silent defaults / no fabricated geometry):
  * interpreter missing                  -> GeometryError
  * subprocess crash / non-zero exit     -> GeometryError (stderr included)
  * worker reports a typed error          -> GeometryError (re-raised faithfully)
  * unparseable output                    -> GeometryError
A genuine geometric "no" (e.g. an empty intersection -> not interfering) comes back
as a real value, not an error.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ..core.errors import GeometryError
from ..core.state import GeometryNode, Quantity

#: The worker script (shipped in this package; executed by the cad-venv interpreter).
_WORKER = Path(__file__).resolve().parent / "cadquery_worker.py"

#: Default cad-venv interpreter; override with GENESIS_CAD_PYTHON.
_DEFAULT_CAD_PYTHON = "/home/genesis/.venv-cad/bin/python"

#: Generous default timeout (s): OCCT boolean+tessellation on a cold import.
_DEFAULT_TIMEOUT = 120.0


def cad_python() -> str:
    """Resolve the cad-venv interpreter path (env override, else the default)."""
    return os.environ.get("GENESIS_CAD_PYTHON", _DEFAULT_CAD_PYTHON)


def cad_available() -> bool:
    """True iff the cad-venv interpreter and the worker script both exist.

    Mirrors the ``available()`` pattern of the optimizer adapters so callers (and
    tests) can skip-guard cleanly. A True here does NOT prove cadquery imports —
    only the first real call does — but a False is a definitive 'no kernel'.
    """
    return Path(cad_python()).exists() and _WORKER.is_file()


def _serialize(node: GeometryNode) -> dict:
    """Serialise a CSG node tree to the worker's JSON shape (kind/params/children)."""
    return {
        "kind": node.kind,
        "params": dict(node.params),
        "children": [_serialize(c) for c in node.children],
    }


def _resolved_values(quantities: dict[str, Quantity]) -> dict[str, float]:
    """Flatten the Quantity map to the {quantity_id: float} the worker needs."""
    return {qid: float(q.value) for qid, q in quantities.items()}


def _run(request: dict, *, timeout: float = _DEFAULT_TIMEOUT):
    """Run the worker once with ``request`` (JSON on stdin) and return its result.

    Raises GeometryError on any failure mode (missing interpreter, subprocess
    error, worker-reported error, unparseable output) — loud, never a guessed value.
    """
    py = cad_python()
    if not Path(py).exists():
        raise GeometryError(
            f"exact BREP needs the isolated CadQuery venv interpreter at {py!r} "
            f"(set GENESIS_CAD_PYTHON). CadQuery is intentionally NOT in the main "
            f".venv — it downgrades numpy. Use the AABB layer "
            f"(verification/geometry.py) for a kernel-free bound."
        )
    if not _WORKER.is_file():
        raise GeometryError(f"CadQuery worker script missing at {_WORKER}")
    try:
        proc = subprocess.run(
            [py, str(_WORKER)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GeometryError(
            f"CadQuery worker timed out after {timeout}s for op {request.get('op')!r}"
        ) from exc
    if proc.returncode != 0:
        raise GeometryError(
            f"CadQuery worker exited {proc.returncode} for op {request.get('op')!r}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GeometryError(
            f"CadQuery worker returned unparseable output for op "
            f"{request.get('op')!r}: {proc.stdout[:500]!r} (stderr: "
            f"{proc.stderr[:300]!r})"
        ) from exc
    if not payload.get("ok", False):
        raise GeometryError(
            f"CadQuery worker (op {request.get('op')!r}) failed: "
            f"{payload.get('error', 'unknown error')}"
        )
    return payload["result"]


# --- Public API (mirrors brep.py's numeric/bool/export surface) --------------

def exact_volume(node: GeometryNode, quantities: dict[str, Quantity]) -> float:
    """Exact OCCT solid volume of the CSG (booleans evaluated by the kernel)."""
    return float(_run({"op": "volume", "node": _serialize(node),
                       "values": _resolved_values(quantities)}))


def is_valid(node: GeometryNode, quantities: dict[str, Quantity]) -> bool:
    """True iff the kernel reports a topologically valid solid (BRepCheck)."""
    return bool(_run({"op": "valid", "node": _serialize(node),
                     "values": _resolved_values(quantities)}))


def interferes(
    node_a: GeometryNode,
    node_b: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    tolerance: float = 1e-9,
) -> bool:
    """Exact interference: True iff the two solids actually overlap (intersection
    volume > tolerance) — the EXACT test the conservative AABB layer cannot decide."""
    values = _resolved_values(quantities)
    return bool(_run({
        "op": "interferes",
        "node": _serialize(node_a),
        "node_b": _serialize(node_b),
        "values": values,
        "tolerance": tolerance,
    }))


def to_stl(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    name: str = "part",
    tolerance: float = 0.1,
) -> str:
    """Print-ready ASCII STL of the CSG, booleans evaluated then tessellated on the
    OCCT kernel (kernel outward winding). ``tolerance`` is the chordal sag (mm)."""
    return str(_run({
        "op": "stl",
        "node": _serialize(node),
        "values": _resolved_values(quantities),
        "name": name,
        "tolerance": tolerance,
    }))


def to_step(node: GeometryNode, quantities: dict[str, Quantity]) -> str:
    """Exact-BREP STEP (AP214) text of the CSG — the lossless solid interchange the
    AABB/STL paths cannot produce. For downstream CAD/CAM that needs true geometry."""
    return str(_run({"op": "step", "node": _serialize(node),
                    "values": _resolved_values(quantities)}))


def bounding_box(
    node: GeometryNode, quantities: dict[str, Quantity]
) -> tuple[float, float, float, float, float, float]:
    """Axis-aligned bounding box of the solid: (xmin, xmax, ymin, ymax, zmin, zmax)."""
    raw = _run(
        {"op": "bbox", "node": _serialize(node), "values": _resolved_values(quantities)}
    )
    return tuple(float(x) for x in raw)  # type: ignore[return-value]


def tessellate(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    *,
    tolerance: float = 0.1,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Kernel tessellation as plain floats (verts, tris) for orientation/DFM without
    importing OCCT into the main process (self-improve gap close 2026-07-14)."""
    raw = _run(
        {
            "op": "tessellate",
            "node": _serialize(node),
            "values": _resolved_values(quantities),
            "tolerance": tolerance,
        }
    )
    verts = [tuple(float(c) for c in v) for v in raw["verts"]]
    tris = [tuple(int(i) for i in t) for t in raw["tris"]]
    return verts, tris  # type: ignore[return-value]


__all__ = [
    "cad_python",
    "cad_available",
    "exact_volume",
    "is_valid",
    "interferes",
    "to_stl",
    "to_step",
    "bounding_box",
    "tessellate",
]
