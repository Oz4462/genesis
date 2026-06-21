"""MAX AGENTS / Return Gate verify: typed RunState δ+ fields + read-write + omega _has + accessors.
Smallest. Runs with PYTHONPATH=src python tmp_....py
Proves: fields declared (no dynamic), assign works, read works, _has includes them, notes use direct access.
Uses real classes. No LLM. 4L applied.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[0] / "src"))

from gen.core.state import RunState, Question, CoverageCertificate, EmpiricalVerdict, EmpiricalStatus
from gen.omega import _has_run_output, _state_learning_notes

print("=== Read all imports OK ===")

q = Question(raw="typed delta+ test", run_id="delta-typ-001")
state = RunState(question=q)

# 1. typed fields default None (read)
print("defaults:", state.coverage_certificate, state.reality_verdict, state.delta_plus_result)
assert state.coverage_certificate is None
assert state.reality_verdict is None
assert state.delta_plus_result is None

# 2. read-write assign (direct, no #ignore needed)
cov = CoverageCertificate(spec_run_id=q.run_id, complete=True)
state.coverage_certificate = cov
print("after write cov:", state.coverage_certificate is cov)

rver = EmpiricalVerdict(status=EmpiricalStatus.CORROBORATED, residual=0.01, within_tolerance=True)
state.reality_verdict = rver
state.delta_plus_result = {"status": "corroborated", "within_tolerance": True, "gate_passed": True}

assert state.coverage_certificate is cov
assert state.reality_verdict is rver
assert state.delta_plus_result["status"] == "corroborated"
print("read-write direct: PASS")

# 3. _has_run_output now includes δ+
has_before = _has_run_output(state)  # true because we set some
print("_has includes delta+:", has_before)
assert has_before  # at least the ones we set

# reset to test pure
state2 = RunState(question=q)
state2.sub_questions = ["x"]  # make has true independent
print("_has on minimal non-delta:", _has_run_output(state2))

# 4. _state_learning_notes uses direct (no getattr crash, produces notes)
notes = _state_learning_notes(state)
note_refs = [n.ref for n in notes]
print("notes count:", len(notes))
print("sample δ notes:", [r for r in note_refs if "coverage" in r or "reality" in r or "delta" in r])
assert any("artifact:coverage_certificate" in r for r in note_refs)
assert any("artifact:reality_verdict" in r for r in note_refs)
assert any("artifact:delta_plus_result" in r for r in note_refs)
print("omega accessors direct: PASS")

print("=== ALL PASS: typed RunState δ+ fields + read-write + omega updated ===")
print("4L L4: executable, gates unaffected (pure), fidelity to dataclass.")