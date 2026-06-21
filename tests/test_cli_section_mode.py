"""Smoke test for the `--mode section` CLI wiring.

End-to-end proof that the grounded, gate-verified section optimizer is reachable from the live CLI:
the mode dispatches, runs ``section_optimizer.propose_and_verify`` over every grounded material, and
returns 0 only because each proposal cleared the INDEPENDENT yield gate. Offline, deterministic — no
LLM, no network.
"""

from gen.cli import main


def test_section_mode_runs_and_every_proposal_clears_the_gate(capsys):
    rc = main(["--mode", "section"])
    out = capsys.readouterr().out
    assert rc == 0                                   # exit 0 == every material's section cleared the gate
    assert "Querschnitts-Optimierer" in out
    assert "PETG" in out                             # a grounded registry material appears
    assert "Streckgrenzen-Quelle" in out            # the yield strength is shown WITH its provenance
