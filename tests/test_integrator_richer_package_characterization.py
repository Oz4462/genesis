"""Characterization test for integrator.build_full_mini_realization_package.

Headline claim under audit: the "richer package" genuinely EMITS a BOM + assembly +
manufacturing docs that are DERIVED from the input ideas — not constant stubs.

This file pins that the manifest is computed from the ideas:
  * the BOM is a non-empty list whose length tracks the fragment/part count, and whose
    content varies with the idea (adding/removing an idea changes both),
  * the assembly manifest is present and references the real STL parts written to disk,
  * the honest fields (physics_gate "not run", open_gaps) are present and unchanged.

Runs WITHOUT build123d: the fragment path (gen.cad.prototype_cad_builder) produces a real
STL on disk even without the optional build123d backend, so no importorskip is needed.

Regression guard: an earlier version embedded the live, non-JSON-serializable RunState into
the manifest dict, so json.dumps crashed and NO package was emitted at all. These tests would
fail loudly on that facade because manifest.json could not be read back.
"""

import json
import os
from pathlib import Path

from hypothesis import given, settings, strategies as st

from gen.pipelines.integrator import build_full_mini_realization_package


def _build(ideas, tmp_path, run_id):
    """Run the packager inside an isolated cwd and return (pkg_path, manifest, files)."""
    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        pkg = build_full_mini_realization_package(ideas, run_id=run_id)
        # The packager returns a path RELATIVE to cwd; resolve it to absolute BEFORE chdir back,
        # otherwise it would later resolve against the original cwd and miss the package.
        pkg_path = Path(pkg).resolve()
    finally:
        os.chdir(cwd)
    manifest = json.loads((pkg_path / "manifest.json").read_text(encoding="utf-8"))
    files = sorted(p.name for p in pkg_path.iterdir())
    return pkg_path, manifest, files


def test_manifest_bom_and_assembly_are_derived_from_ideas(tmp_path):
    """One concrete idea-set: BOM non-empty + length == fragments, assembly refs real STLs, honest fields present."""
    ideas = ["Ein faltbares Lastenrad für die Stadt.", "Eine modulare Akku-Box."]
    pkg_path, manifest, files = _build(ideas, tmp_path, run_id="char-2")

    # The artifact bundle actually got written (would be absent if json.dumps had crashed on a
    # non-serializable embedded object — the bug this test characterizes).
    assert "manifest.json" in files
    assert "SUMMARY.md" in files

    # BOM is a non-empty list whose length tracks the produced fragments/parts.
    bom = manifest["bom"]
    assert isinstance(bom, list)
    assert len(bom) == manifest["num_fragments"] == len(ideas)
    assert all(isinstance(entry, str) and entry for entry in bom)

    # Assembly manifest is present and references the real STL parts ON DISK.
    asm = manifest["assembly"]
    assert isinstance(asm, dict)
    assert asm["num_parts"] == len(ideas)  # both <= the assembly's 3-part cap
    part_stls = [p["stl"] for p in asm["parts"]]
    assert part_stls and all(stl and os.path.exists(stl) for stl in part_stls)
    # And those parts are copied into the package dir as real .stl files.
    assert any(f.endswith(".stl") for f in files)

    # Honest gate status is present and says the physics gate did NOT run here.
    assert "not run" in manifest["physics_gate"].lower()
    assert "open_gaps" in manifest and isinstance(manifest["open_gaps"], list)


def test_adding_an_idea_grows_part_count_and_bom(tmp_path):
    """Input is genuinely consumed: more ideas -> more fragments, more BOM lines, more STLs, more open_gaps."""
    one_path, one, one_files = _build(["Nur eine Idee: ein Türstopper."], tmp_path / "one", run_id="char-one")
    three_path, three, three_files = _build(
        ["Idee A: Türstopper.", "Idee B: Regalwinkel.", "Idee C: Kabelhalter."],
        tmp_path / "three",
        run_id="char-three",
    )

    # Part count and BOM length both grow with the number of ideas — not constant stubs.
    assert one["num_fragments"] == 1 and three["num_fragments"] == 3
    assert len(one["bom"]) == 1 and len(three["bom"]) == 3
    assert one["assembly"]["num_parts"] == 1 and three["assembly"]["num_parts"] == 3

    # More fragments -> more real STL parts on disk.
    one_stls = [f for f in one_files if f.endswith(".stl")]
    three_stls = [f for f in three_files if f.endswith(".stl")]
    assert len(three_stls) > len(one_stls)

    # open_gaps aggregates per-fragment gaps, so it grows too (proves it is computed, not a fixed list).
    assert len(three["open_gaps"]) > len(one["open_gaps"])


def test_bom_content_reflects_the_idea_not_a_constant(tmp_path):
    """Two DIFFERENT single-idea packages must yield DIFFERENT BOM content (no constant part-name stub)."""
    _, m_rocket, _ = _build(["Eine Wasserrakete für den Physikunterricht."], tmp_path / "a", run_id="char-rocket")
    _, m_lamp, _ = _build(["Eine Schreibtischlampe mit Gelenkarm."], tmp_path / "b", run_id="char-lamp")

    # Same length (one part each) but the lines must differ — the idea must reach the BOM.
    assert len(m_rocket["bom"]) == len(m_lamp["bom"]) == 1
    assert m_rocket["bom"] != m_lamp["bom"], (
        "BOM content is identical for different ideas -> the idea is not consumed (constant-stub facade)"
    )


@settings(max_examples=8, deadline=None)
@given(n=st.integers(min_value=1, max_value=3))
def test_bom_length_invariant_tracks_fragment_count(tmp_path_factory, n):
    """Property: for n ideas (within the 3-part assembly cap), BOM length == num_fragments == n."""
    tmp_path = tmp_path_factory.mktemp("prop")
    ideas = [f"Idee Nummer {k}: ein kleines Bauteil." for k in range(n)]
    _, manifest, _ = _build(ideas, tmp_path, run_id=f"char-prop-{n}")
    assert manifest["num_fragments"] == n
    assert len(manifest["bom"]) == n
    assert manifest["assembly"]["num_parts"] == n
