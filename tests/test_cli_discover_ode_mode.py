"""Smoke test for the `--mode discover-ode` CLI wiring (research-core ODE discovery in one command).

End-to-end proof that the SINDy research arm is reachable from the live CLI: the mode simulates a damped
pendulum with a GENESIS RK4 simulator, recovers its second-order ODE by sparse identification, runs the
SINDy-hygiene dummy-feature test, reports an ensemble-bootstrap uncertainty band per coefficient, and
returns 0 only on an honest success (sparse law recovered AND dummy excluded). Offline, deterministic.
"""

from gen.cli import main


def test_discover_ode_mode_recovers_the_ode_with_hygiene_and_uncertainty(capsys):
    rc = main(["--mode", "discover-ode"])
    out = capsys.readouterr().out
    assert rc == 0                                       # honest success: law + dummy-out + band
    assert "ODE-Entdeckung" in out
    assert "theta_ddot" in out and "sin(theta)" in out   # the recovered sparse law
    assert "ausgeschlossen" in out                       # the planted dummy feature was excluded
    assert "Ensemble-SINDy-Bootstrap" in out             # an uncertainty band was reported
    assert "OK" in out


def test_discover_ode_mode_is_deterministic(capsys):
    rc1 = main(["--mode", "discover-ode"])
    first = capsys.readouterr().out
    rc2 = main(["--mode", "discover-ode"])
    second = capsys.readouterr().out
    assert rc1 == rc2 == 0
    assert first == second                               # no RNG leakage: byte-identical report
