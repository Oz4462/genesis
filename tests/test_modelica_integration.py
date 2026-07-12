"""Modelica / OpenModelica system-simulation adapter — real-solver integration tests.

simulation/modelica.py drives OpenModelica (via OMPython's OMCSessionZMQ) to compile and
simulate a coupled transient model. These tests pin, against the real ``omc`` compiler:

  * POSITIVE (verified, not asserted): the first-order decay model der(x)=-x, x(0)=1 has
    the known closed form x(t)=exp(-t); OpenModelica's transient solve of it must return
    exp(-stop_time) at several stop times — the solver independently reproduces the closed
    form, so the integration genuinely runs a multi-physics solve, not a canned number;
  * POSITIVE (coupled domains): a real RC circuit charges to Vin*(1-exp(-t/RC)) — a second,
    parameterised model read back through the same seam;
  * NEGATIVE (loud failure): a request for a variable not in the result, and a simulate of
    an unknown model, both raise the typed GenesisError (no fabricated value).

Two FAST unit tests (no compiler) always run: the availability probe is a bool, and an
unconnected session is a loud GenesisError. The solver-dependent tests SKIP when OMPython
is absent (the ``_integration`` suffix marks them slow/solver-dependent).

Engine: OpenModelica (omc 1.26.x via OMPython). Run:  pytest tests/test_modelica_integration.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import GenesisError  # noqa: E402
from gen.simulation.modelica import (  # noqa: E402
    DECAY_MODEL,
    ModelicaSimulation,
    openmodelica_available,
    simulate_decay,
)

_HAVE_OM = openmodelica_available()
_skip_no_om = pytest.mark.skipif(
    not _HAVE_OM, reason="OpenModelica system simulation needs the optional OMPython package + omc")


# --- FAST unit tests (no compiler) -------------------------------------------------

def test_availability_probe_is_bool():
    assert isinstance(openmodelica_available(), bool)


def test_unconnected_session_is_loud():
    sim = ModelicaSimulation()
    with pytest.raises(GenesisError):
        sim.simulate("Decay", ["x"], stop_time=1.0)


# --- solver-dependent integration tests --------------------------------------------

@_skip_no_om
@pytest.mark.parametrize("stop_time", [0.5, 1.0, 2.0])
def test_decay_solution_matches_exponential(stop_time, tmp_path):
    """OpenModelica's transient solve of der(x)=-x reproduces x(t)=exp(-t)."""
    x = simulate_decay(stop_time, work_dir=str(tmp_path))
    assert x == pytest.approx(math.exp(-stop_time), abs=2e-3)


@_skip_no_om
def test_rc_circuit_charges_to_steady_state(tmp_path):
    """A coupled RC model charges toward Vin: at t=5τ, Vc ≈ Vin·(1-exp(-5))."""
    rc = (
        "model RC\n"
        "  parameter Real R = 1000.0;\n"
        "  parameter Real C = 1e-3;\n"
        "  parameter Real Vin = 5.0;\n"
        "  Real Vc(start = 0.0);\n"
        "equation\n"
        "  R*C*der(Vc) + Vc = Vin;\n"
        "end RC;\n"
    )
    with ModelicaSimulation() as sim:
        assert "OpenModelica" in sim.version()
        sim.load_model_string(rc)
        res = sim.simulate("RC", ["Vc"], stop_time=5.0, intervals=100, work_dir=str(tmp_path))
    # tau = R*C = 1 s; at t = 5 s (5τ) the cap is 99.3% charged.
    assert res.final_values["Vc"] == pytest.approx(5.0 * (1.0 - math.exp(-5.0)), abs=1e-2)
    assert res.result_file  # a real result file was produced


@_skip_no_om
def test_unknown_variable_is_loud(tmp_path):
    """Reading a variable that is not in the result raises GenesisError, not a fake 0."""
    with ModelicaSimulation() as sim:
        sim.load_model_string(DECAY_MODEL)
        with pytest.raises(GenesisError):
            sim.simulate("Decay", ["nonexistent_var"], stop_time=1.0, work_dir=str(tmp_path))


@_skip_no_om
def test_unknown_model_is_loud(tmp_path):
    """Simulating a model that was never loaded produces no result file → GenesisError."""
    with ModelicaSimulation() as sim:
        with pytest.raises(GenesisError):
            sim.simulate("NoSuchModel", ["x"], stop_time=1.0, work_dir=str(tmp_path))
