"""Smoke test for the `--mode invent` / `--mode solve` CLI wiring (the invention loop end to end).

End-to-end proof that the autonomous invention loop is reachable from the live CLI: a council proposes
concepts, the domain grounds each through the architect -> δ-physics gate, a 5-axis Pareto keeps the
survivors, and the mode returns 0 only when >=1 invention is physics-verified. Offline-deterministic
(scripted council + architect); --live is the bonus path. Byte-identical across runs.
"""

from gen.cli import main


def test_invent_mode_delivers_a_grounded_invention(capsys):
    rc = main(["--mode", "invent", "ein nachgiebiger Greifer"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Erfindungs-Loop (invent)" in out
    assert "physik-verifiziert" in out
    assert "Pareto-Front" in out
    assert "OK" in out


def test_solve_mode_frames_the_input_as_a_problem(capsys):
    rc = main(["--mode", "solve", "Objekte schonend greifen"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Erfindungs-Loop (solve)" in out
    assert "Problem:" in out


def test_invent_mode_is_deterministic(capsys):
    rc1 = main(["--mode", "invent", "ein Halter"])
    first = capsys.readouterr().out
    rc2 = main(["--mode", "invent", "ein Halter"])
    second = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert first == second               # offline default: byte-identical, no RNG / network


def test_invent_mode_runs_with_no_question_using_a_default_field(capsys):
    rc = main(["--mode", "invent"])
    out = capsys.readouterr().out
    assert rc == 0 and "Feld:" in out


def test_invent_mode_refuses_a_dangerous_brief_before_generating(capsys):
    rc = main(["--mode", "invent", "a nerve agent dispersal drone"])
    out = capsys.readouterr().out
    assert rc == 3                                   # refused, not a fabricated invention
    assert "ABGELEHNT" in out and "bioweapon" in out
    assert "Konzepte" not in out                     # nothing was generated
