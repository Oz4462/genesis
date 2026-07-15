"""P0-1 regression tests: the assembly/CAD path must NEVER emit 0-byte
placeholder artifacts (audit finding 2026-07-15: 147 empty STLs in
out/realization_packages/, silently produced by cad/assembly.py).

Contract under test:
  * part_files contains ONLY existing, non-empty files.
  * a part without real geometry produces NO file and an explicit gap entry.
  * combined_stl is a REAL kernel union (or None + gap) — never a renamed copy.
  * with the kernel unavailable the builder reports an honest hint string, no file.
"""

from __future__ import annotations

import os

import pytest

from gen.cad.assembly import build_assembly
from gen.cad.cadquery_bridge import cad_available
from gen.cad.prototype_cad_builder import PrototypeSpec, build_prototype_cad

JETPACK = PrototypeSpec(
    name="Jetpack Tether / Harness",
    description="recovery anchor plate",
    bounding_box_hint_mm=(120.0, 80.0, 10.0),
)
GENERIC = PrototypeSpec(
    name="Sensor Mount",
    description="generic mount plate",
    bounding_box_hint_mm=(50.0, 50.0, 5.0),
)


def _no_empty_files(paths: list[str]) -> bool:
    return all(os.path.isfile(p) and os.path.getsize(p) > 0 for p in paths)


# --- kernel unavailable: honest gaps, no placeholder files -------------------


def test_builder_without_kernel_emits_no_file_and_no_empty_stl(monkeypatch):
    monkeypatch.setenv("GENESIS_CAD_PYTHON", "/nonexistent/cad-python")
    assert not cad_available()
    art = build_prototype_cad(JETPACK, run_id="p01-nokernel")
    stl_claim = art.exports["stl"]
    # honest hint string, not a path to a (possibly empty) file
    assert not os.path.exists(stl_claim)
    assert "kernel unavailable" in stl_claim or "exported on execution" in stl_claim
    # geometry is still real CSG (kernel-free), for downstream consumers
    assert art.geometry is not None
    assert art.geometry.kind == "difference"


def test_assembly_without_kernel_records_gaps_instead_of_placeholders(monkeypatch):
    monkeypatch.setenv("GENESIS_CAD_PYTHON", "/nonexistent/cad-python")
    asm = build_assembly([JETPACK, GENERIC], name="No Kernel Asm", run_id="p01-nk")
    # NO placeholder files — the old behavior appended empty tempfiles here
    assert _no_empty_files(asm.part_files)
    assert asm.part_files == []  # kernel off → no real geometry files exist
    assert asm.combined_stl is None
    # every missing part is an explicit, named gap
    assert len(asm.gaps) >= 2
    assert any("Jetpack" in g for g in asm.gaps)
    assert asm.manifest["gaps"] == asm.gaps
    assert asm.manifest["num_parts"] == 2
    # manifest part entries carry stl=None, not a fake path
    assert all(p["stl"] is None for p in asm.manifest["parts"])


# --- kernel available: real geometry, still never an empty file --------------


@pytest.mark.skipif(not cad_available(), reason="cad-venv kernel not installed")
def test_builder_with_kernel_writes_real_nonempty_stl():
    art = build_prototype_cad(JETPACK, run_id="p01-kernel")
    stl = art.exports["stl"]
    assert os.path.isfile(stl) and os.path.getsize(stl) > 0
    assert stl.endswith(".stl")


@pytest.mark.skipif(not cad_available(), reason="cad-venv kernel not installed")
def test_assembly_with_kernel_builds_real_union_no_empty_files():
    asm = build_assembly([JETPACK, GENERIC], name="Real Asm", run_id="p01-real")
    assert len(asm.part_files) == 2
    assert _no_empty_files(asm.part_files)
    # combined is a REAL union file, distinct from every single part
    assert asm.combined_stl is not None
    assert os.path.getsize(asm.combined_stl) > 0
    assert asm.combined_stl not in asm.part_files
    # union of two solids must carry more geometry than the largest single part
    assert os.path.getsize(asm.combined_stl) > max(
        os.path.getsize(p) for p in asm.part_files
    )
    assert asm.gaps == []
