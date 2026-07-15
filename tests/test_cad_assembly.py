"""Tests für cad assembly (CAD-Vertiefung erster Stein).

Siehe GENESIS_TODO Item 4 + PLAN §3.6.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.integrator import build_realization_fragment
from gen.cad.assembly import build_assembly


def test_jetpack_fragments_produce_real_assembly_with_manifest():
    """Jetpack-Idee → ... → Integrator fragments → Assembly mit realen part_files + manifest (Naht zu real CAD + Store)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="asm-test-001")
    ingen = map_to_ingenieur_spec(concept, run_id="asm-test-001")
    frag = build_realization_fragment(concept, ingen, focus_assembly_name='Tether / Harness', run_id="asm-test-001")

    asm = build_assembly([frag], name="Jetpack Tether Assembly", run_id="asm-test-001")

    assert asm.spec.name == "Jetpack Tether Assembly"
    # P0-1 honest contract: real non-empty files when the kernel is available,
    # explicit gaps (and NO placeholder files) when it is not.
    import os
    from gen.cad.cadquery_bridge import cad_available
    assert all(os.path.getsize(f) > 0 for f in asm.part_files)
    if cad_available():
        assert len(asm.part_files) >= 1
        assert any("tether" in f.lower() or "stl" in f.lower() for f in asm.part_files)
    else:
        assert asm.gaps, "without kernel the missing STL must be an explicit gap"
    assert asm.manifest["num_parts"] >= 1
    assert "combined" in asm.manifest
    assert "assembly" in (asm.quelle or "").lower() or "integrator" in (asm.quelle or "").lower()
    assert asm.run_id == "asm-test-001"


def test_generic_produces_minimal_assembly():
    """Generische → minimal Assembly."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    concept = map_to_system_concept(idee)
    ingen = map_to_ingenieur_spec(concept)
    frag = build_realization_fragment(concept, ingen)

    asm = build_assembly([frag], name="Generic Assembly")

    import os
    from gen.cad.cadquery_bridge import cad_available
    assert all(os.path.getsize(f) > 0 for f in asm.part_files)
    if cad_available():
        assert len(asm.part_files) >= 1
    else:
        assert asm.gaps
    assert asm.manifest["num_parts"] >= 1
