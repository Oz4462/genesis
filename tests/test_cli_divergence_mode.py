"""CLI wiring of Phase φ — `genesis --mode divergence` (run_divergence) + format_divergence.

run_divergence was a real, tested, gated capability with NO CLI route (STATUS.md §3:
"φ has no CLI route — dangling capability"). These tests lock the wire: the mode is
registered, the renderer is honest (grounded possibilities + the grounded-sample
disclaimer; empty = honest abstention), and `--demo --mode divergence` runs offline.
"""

from __future__ import annotations

from gen.cli import format_divergence, main
from gen.core.state import Divergence, Possibility, Spark


def _spark() -> Spark:
    return Spark(id="rid:spark", raw="etwas das eine konstante Referenz nutzt")


def test_format_divergence_renders_grounded_possibility_with_anchor():
    # Arrange — a grounded possibility (Possibility forbids empty grounding by construction)
    poss = Possibility(
        id="p1",
        statement="ein Pendel als Taktgeber",
        mechanism="g ist konstant -> Periode hängt nur von der Länge ab",
        grounding=["claim-grav-1"],
    )
    div = Divergence(spark=_spark(), possibilities=[poss], grounded_sample=True)

    # Act
    out = format_divergence(div)

    # Assert — the statement, mechanism, anchor, and the honest sample disclaimer all surface
    assert "ein Pendel als Taktgeber" in out
    assert "g ist konstant" in out
    assert "claim-grav-1" in out
    assert "STICHPROBE" in out  # honest "this is a grounded sample, not the whole space"


def test_format_divergence_empty_is_honest_abstention():
    # Arrange — zero possibilities is valid abstention, never a fabricated direction
    div = Divergence(spark=_spark(), possibilities=[], grounded_sample=True)

    # Act
    out = format_divergence(div)

    # Assert
    assert "ehrliche Enthaltung" in out
    assert "Funke:" in out


def test_divergence_mode_is_registered_and_runs_offline_in_demo():
    # Act — the demo path drives run_divergence over the scripted world (no network/Ollama)
    rc = main(["--demo", "--mode", "divergence"])

    # Assert — the mode dispatches and completes honestly (never falls through to spec)
    assert rc == 0
