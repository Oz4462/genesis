"""Smoke test for the `--mode training` CLI wiring.

End-to-end proof that GENESIS's honest ML boundary is reachable from the live CLI: the mode gates a
complete demo training plan for completeness, surfaces the gaps of an incomplete one, and ratifies
measured numbers against the pre-declared bar (δ-asymmetry) — returning 0 only when the plan is complete
AND the measured results clear the bar. Offline, deterministic — no model, no training.
"""

from gen.cli import main


def test_training_mode_runs_and_ratifies_the_demo_plan(capsys):
    rc = main(["--mode", "training"])
    out = capsys.readouterr().out
    assert rc == 0                                   # complete plan + measured results cleared the bar
    assert "Trainings-Plan-Gate" in out
    assert "Vollständigkeit: OK" in out              # success was declared up front
    assert "RATIFIZIERT" in out                      # measured numbers cleared the pre-declared bar
    assert "trainiert nicht" in out                  # the honest boundary is stated, not hidden
