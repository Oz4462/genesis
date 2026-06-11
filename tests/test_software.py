"""GATE CODE — software deliverables validated by EXECUTION (the epsilon software arc).

Every other layer re-checks a declared value; software has the strongest
deterministic validator: run it. A code artifact is `source` + a `check`; gate_code
runs them in an isolated subprocess and passes only if the process exits zero. No
model judgement - the machine decides. This is deterministic and offline (a
subprocess of the same interpreter, no network, no LLM).

Run:  pytest tests/test_software.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import CodeArtifact, Question, RunState, Specification  # noqa: E402
from gen.software import run_python_artifact  # noqa: E402
from gen.verification.gates import gate_code  # noqa: E402

_SRC = "def add(a, b):\n    return a + b\n"


def _state(*artifacts: CodeArtifact) -> RunState:
    spec = Specification(run_id="r", idea="sw", code_artifacts=list(artifacts))
    st = RunState(question=Question(raw="sw", run_id="r"))
    st.specification = spec
    return st


def _art(check: str, *, source: str = _SRC, language: str = "python") -> CodeArtifact:
    return CodeArtifact(id="ca", name="adder", language=language, source=source, check=check)


# --- the runner executes ------------------------------------------------------

def test_runner_passes_and_fails():
    ok, _ = run_python_artifact(_SRC, "assert add(2, 3) == 5")
    assert ok
    bad, out = run_python_artifact(_SRC, "assert add(2, 3) == 6")
    assert not bad and "AssertionError" in out


# --- the gate ------------------------------------------------------------------

def test_sound_code_passes():
    assert gate_code(_state(_art("assert add(2, 3) == 5\nassert add(-1, 1) == 0"))).passed


def test_no_artifacts_passes_trivially():
    assert gate_code(_state()).passed


def test_failing_check_is_caught():
    codes = {f.code for f in gate_code(_state(_art("assert add(2, 3) == 7"))).failures}
    assert codes == {"CODE_CHECK_FAILED"}, codes


def test_syntax_error_is_caught():
    codes = {f.code for f in gate_code(_state(_art("pass", source="def f(:\n  pass"))).failures}
    assert codes == {"CODE_CHECK_FAILED"}, codes


def test_unsupported_language_is_reported_not_faked():
    art = _art("// nothing", source="int add(int a,int b){return a+b;}", language="c")
    codes = {f.code for f in gate_code(_state(art)).failures}
    assert codes == {"UNSUPPORTED_LANGUAGE"}, codes


# --- the capstone carries a real, executing deliverable -----------------------

def test_capstone_code_executes_and_passes():
    from gen.demo import capstone_state
    st = capstone_state()
    result = gate_code(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]
    # the deliverable is the LED operating-point resistance helper
    assert any(a.name == "led_resistance" for a in st.specification.code_artifacts)


def test_code_artifacts_round_trip():
    from gen.demo import capstone_spec
    from gen.runner import _specification_to_dict, specification_from_dict
    spec = capstone_spec()
    spec2 = specification_from_dict(_specification_to_dict(spec))
    assert _specification_to_dict(spec2) == _specification_to_dict(spec)
    assert gate_code(_wrap(spec2)).passed


def _wrap(spec):
    st = RunState(question=Question(raw="x", run_id=spec.run_id))
    st.specification = spec
    return st
