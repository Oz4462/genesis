"""GATE PROTOCOL — reproducibility-design check for the bio ε domain.

A wet-lab/field protocol that measures a quantitative outcome but has no control or
too few replicates is the root of the reproducibility crisis. gate_protocol checks
the design deterministically; parameter SAFETY LIMITS and units reuse the existing
constraint machinery (C-13 / C-15). The demo realizes the VISION's plant-growth
example across a completely different domain than the bracket - the same engine.

Offline, no LLM.

Run:  pytest tests/test_protocol.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import ExperimentDesign, Question, RunState, Specification  # noqa: E402
from gen.verification.gates import gate_gamma, gate_protocol  # noqa: E402


def _state(design: ExperimentDesign | None) -> RunState:
    spec = Specification(run_id="r", idea="exp", experiment=design)
    st = RunState(question=Question(raw="exp", run_id="r"))
    st.specification = spec
    return st


def _good() -> ExperimentDesign:
    return ExperimentDesign(measured="stem height", groups=["treatment", "control"],
                            control="control", replicates=5)


# --- the demo protocol passes both gates ---------------------------------------

def test_protocol_demo_passes_gamma_and_protocol():
    from gen.demo import protocol_state
    st = protocol_state()
    assert gate_gamma(st).passed, [f"{f.code}: {f.detail}" for f in gate_gamma(st).failures]
    assert gate_protocol(st).passed


def test_sound_design_passes():
    assert gate_protocol(_state(_good())).passed


def test_no_experiment_passes_trivially():
    assert gate_protocol(_state(None)).passed


# --- each reproducibility rule has teeth ---------------------------------------

def test_measured_without_control_is_caught():
    d = ExperimentDesign(measured="yield", groups=["treatment"], control=None, replicates=5)
    assert "MEASURE_WITHOUT_CONTROL" in {f.code for f in gate_protocol(_state(d)).failures}


def test_control_not_in_groups_is_caught():
    d = ExperimentDesign(measured="yield", groups=["treatment", "placebo"],
                         control="control", replicates=5)
    assert "CONTROL_NOT_IN_GROUPS" in {f.code for f in gate_protocol(_state(d)).failures}


def test_too_few_replicates_is_caught():
    d = ExperimentDesign(measured="yield", groups=["treatment", "control"],
                         control="control", replicates=2)
    assert "INSUFFICIENT_REPLICATES" in {f.code for f in gate_protocol(_state(d)).failures}


# --- the safety limit rides on the existing constraint machinery (C-13) --------

def test_overdose_trips_the_safety_constraint():
    from gen.demo import protocol_state
    st = protocol_state()
    conc = next(q for q in st.specification.quantities if q.id == "q_conc")
    conc.value = 250.0          # above the 200 g/m^3 phytotoxic threshold
    codes = {f.code for f in gate_gamma(st).failures}
    assert "CONSTRAINT_VIOLATION" in codes


def test_protocol_round_trips():
    from gen.demo import protocol_spec
    from gen.runner import _specification_to_dict, specification_from_dict
    spec = protocol_spec()
    spec2 = specification_from_dict(_specification_to_dict(spec))
    assert _specification_to_dict(spec2) == _specification_to_dict(spec)
    assert spec2.experiment is not None and spec2.experiment.control == "control"
