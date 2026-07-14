"""Schritt-7-Batch-2-Härtungen (Review 2026-07-04): brep.py Fehler-Kontrakt.

Fünf Härtungen — jede war ein Pfad, auf dem brep.py seinen dokumentierten
GeometryError-Kontrakt brach oder in die falsche sichere Richtung schwieg:
  B1 fehlender params-Key            → roher KeyError statt GeometryError
  B2 negative/Null/NaN-Primitivmaße  → rohe OCCT-Failure statt GeometryError
  B3 interferes: Kernel-Fehler wurde als "keine Kollision" gemeldet (falsche
     sichere Richtung); nur eine echte Null-Shape-Schnittmenge ist "kein Overlap"
  B4 Transform ohne Kind             → IndexError statt GeometryError
  B7 NaN-Rotationsachse              → passierte den <1e-12-Guard (NaN-Vergleich)

Stub-basiert: läuft OHNE cadquery (der optionale Kernel wird gemonkeypatcht,
exakt wie in test_step7_hardening.py / test_printability_pipeline.py). Der
Kernel-gebundene Kugel-Volumen-Anker (B6) lebt in test_brep.py.

Run:  pytest tests/test_step7_brep_hardening.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.core.state import GeometryNode  # noqa: E402


def _dec(qid, value):
    # Duck-typed quantity (brep._val reads only .value): the real Quantity class
    # already REJECTS non-finite values at construction (root guard in state.py),
    # so the NaN/inf cases here exercise brep.py's DEFENSE-IN-DEPTH for callers
    # that pass quantity-likes around that root guard.
    return SimpleNamespace(id=qid, value=value)


class _StubShape:
    def translate(self, v):
        return self

    def rotate(self, a, b, angle):
        return self


class _StubSolid:
    @staticmethod
    def makeBox(sx, sy, sz, origin):
        return _StubShape()

    @staticmethod
    def makeCylinder(r, h, p, d):
        return _StubShape()

    @staticmethod
    def makeSphere(r, *args):
        return _StubShape()


class _StubVec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


def _patch_kernel(monkeypatch):
    import gen.brep as brep
    monkeypatch.setattr(brep, "_require_cadquery", lambda: (_StubSolid, _StubVec))
    return brep


# --- B1: fehlender params-Key → GeometryError, nicht KeyError --------------------

def test_missing_param_key_is_geometry_error(monkeypatch):
    brep = _patch_kernel(monkeypatch)
    node = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s"})  # size_z fehlt
    with pytest.raises(GeometryError, match="size_z"):
        brep.csg_to_solid(node, {"s": _dec("s", 10.0)})


# --- B2: nicht-positive Primitivmaße → GeometryError, nicht rohe OCCT-Failure ----

@pytest.mark.parametrize("kind,params,qs", [
    ("box", {"size_x": "z", "size_y": "p", "size_z": "p"}, {"z": 0.0, "p": 10.0}),
    ("box", {"size_x": "p", "size_y": "n", "size_z": "p"}, {"n": -5.0, "p": 10.0}),
    ("cylinder", {"radius": "z", "height": "p"}, {"z": 0.0, "p": 10.0}),
    ("cylinder", {"radius": "p", "height": "n"}, {"n": -1.0, "p": 10.0}),
    ("sphere", {"radius": "n"}, {"n": -2.0}),
    ("sphere", {"radius": "x"}, {"x": float("nan")}),
    ("sphere", {"radius": "x"}, {"x": float("inf")}),
])
def test_non_positive_primitive_dimension_is_geometry_error(monkeypatch, kind, params, qs):
    brep = _patch_kernel(monkeypatch)
    quantities = {k: _dec(k, v) for k, v in qs.items()}
    with pytest.raises(GeometryError, match="positive"):
        brep.csg_to_solid(GeometryNode(kind=kind, params=params), quantities)


# --- B4: Transform ohne Kind → GeometryError, nicht IndexError -------------------

def test_transform_without_child_is_geometry_error(monkeypatch):
    brep = _patch_kernel(monkeypatch)
    q = {"v": _dec("v", 1.0)}
    node = GeometryNode(kind="translate", params={"x": "v", "y": "v", "z": "v"})
    with pytest.raises(GeometryError, match="child"):
        brep.csg_to_solid(node, q)


# --- B7: NaN-Rotationsachse passierte den Null-Guard (NaN < 1e-12 == False) ------

def test_nan_rotation_axis_is_geometry_error(monkeypatch):
    brep = _patch_kernel(monkeypatch)
    q = {"nan": _dec("nan", float("nan")), "one": _dec("one", 1.0),
         "zero": _dec("zero", 0.0), "s": _dec("s", 10.0), "a": _dec("a", 45.0)}
    node = GeometryNode(
        kind="rotate",
        params={"axis_x": "nan", "axis_y": "zero", "axis_z": "zero", "angle_deg": "a"},
        children=[GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})],
    )
    with pytest.raises(GeometryError, match="finite"):
        brep.csg_to_solid(node, q)


# --- B3: interferes — Null-Shape ist "kein Overlap", Kernel-Fehler wirft ---------

def test_interferes_null_intersection_is_no_overlap(monkeypatch):
    """Eine leere Schnittmenge (Null-Shape) IST der Beweis für keine Kollision —
    Volume() darf dafür gar nicht erst befragt werden."""
    import gen.brep as brep

    class _NullWrapped:
        @staticmethod
        def IsNull():
            return True

    class _S:
        wrapped = _NullWrapped()

        def intersect(self, other):
            return self

        def Volume(self):
            raise AssertionError("Volume() must not be measured on a null shape")

    monkeypatch.setattr(brep, "_prefer_cad_bridge", lambda: False)
    monkeypatch.setattr(brep, "csg_to_solid", lambda node, q: _S())
    assert brep.interferes(None, None, {}) is False


def test_interferes_kernel_failure_raises_not_false(monkeypatch):
    """Ein echter Kernel-Fehler bei der Volumenmessung darf NIE als 'keine
    Kollision' gemeldet werden (falsche sichere Richtung) — er muss werfen."""
    import gen.brep as brep

    class _Wrapped:
        @staticmethod
        def IsNull():
            return False

    class _S:
        wrapped = _Wrapped()

        def intersect(self, other):
            return self

        def Volume(self):
            raise RuntimeError("BRepGProp failed")

    monkeypatch.setattr(brep, "_prefer_cad_bridge", lambda: False)
    monkeypatch.setattr(brep, "csg_to_solid", lambda node, q: _S())
    with pytest.raises(GeometryError, match="intersection"):
        brep.interferes(None, None, {})


def test_interferes_boolean_failure_raises_not_false(monkeypatch):
    """Auch ein Fehler in der booleschen Operation selbst muss werfen."""
    import gen.brep as brep

    class _S:
        def intersect(self, other):
            raise RuntimeError("BOPAlgo error")

    monkeypatch.setattr(brep, "_prefer_cad_bridge", lambda: False)
    monkeypatch.setattr(brep, "csg_to_solid", lambda node, q: _S())
    with pytest.raises(GeometryError, match="intersection"):
        brep.interferes(None, None, {})
