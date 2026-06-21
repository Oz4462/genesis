"""Smoke test for the `--mode chip` CLI wiring (Robot-δ Tour 5 chip-selection-by-requirement).

End-to-end proof that chip selection is reachable from the live CLI: the mode evaluates every catalog
chip against a humanoid's compute requirement using compute.py's gates, prints the per-chip verdict, and
returns 0 only when a feasible chip is selected (with its provenance). Offline, deterministic.
"""

from gen.cli import main


def test_chip_mode_runs_and_selects_a_feasible_chip(capsys):
    rc = main(["--mode", "chip"])
    out = capsys.readouterr().out
    assert rc == 0                                   # a catalog chip cleared all three compute gates
    assert "Chip-Auswahl" in out
    assert "Jetson Orin NX" in out                   # the cheapest feasible chip for the demo requirement
    assert "Gewählt" in out and "Quelle" in out      # a selection with its provenance
