"""Tests für prototype_cad_builder (erster Stein des CAD/Fertigung-Kerns).

Siehe GENESIS_PLATFORM_PLAN.md §3.6, §3.7, 4.7, 8.4.
"""

from gen.cad.prototype_cad_builder import (
    PrototypeSpec,
    build_prototype_cad,
)


def test_jetpack_tether_anchor_produces_real_build123d_code_and_dfm():
    """Jetpack-spezifischer Stein (abgeleitet aus Safety-Ladder + Recovery) erzeugt echten, lauffähigen build123d-Code + vernünftige DFM-Flags."""
    spec = PrototypeSpec(
        name="Jetpack Tether Anchor Plate",
        description="Sichere Tether/Recovery-Befestigungsplatte für Bench- und tethered Tests (S1/S2).",
        bounding_box_hint_mm=(120, 80, 6),
        min_wall_thickness_mm=2.0,
        material_hint="PLA/PETG",
        quelle="prior LearningDelta (Recovery <3s) + safety_ladder S1/S2",
    )

    artifact = build_prototype_cad(spec, run_id="cad-test-001")

    assert "build123d" in artifact.generated_code
    assert "BuildPart" in artifact.generated_code
    assert "BuildSketch" in artifact.generated_code
    assert "extrude" in artifact.generated_code
    assert "Hole" in artifact.generated_code
    assert "fillet" in artifact.generated_code.lower() or "Fillet" in artifact.generated_code

    # DFM enthält praktische Hinweise für 3D-Druck
    assert any("Wandstärke" in line or "mm" in line for line in artifact.dfm_report)
    assert any("Support" in line or "Perimeter" in line for line in artifact.dfm_report)

    assert artifact.is_buildable
    assert artifact.quelle is not None
    assert "GENESIS_PLATFORM_PLAN" in (artifact.quelle or "")


def test_generic_spec_produces_minimal_valid_code():
    """Generische Spec → minimaler aber valider build123d-Code + Basis-DFM."""
    spec = PrototypeSpec(
        name="Generic Test Plate",
        description="Einfache Montageplatte für erste Prototypen-Tests.",
        bounding_box_hint_mm=(100, 60, 5),
    )

    artifact = build_prototype_cad(spec)

    assert "from build123d import" in artifact.generated_code
    assert "BuildPart" in artifact.generated_code
    assert len(artifact.dfm_report) >= 1
    assert artifact.is_buildable
