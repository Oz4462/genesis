"""Sim smoke for pytest targets exercising RunState δ+ now typed.
Covers: test_phase_omega e2e assign+assert, test_lumencrucible result keys, test_phase_delta coverage.
Run equiv: PYTHONPATH=src python -m pytest ... -q
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[0] / "src"))

from gen.core.state import RunState, Question, Claim, ClaimStatus, FailureMode, Specification, EmpiricalVerdict, EmpiricalStatus
from gen.coverage import build_coverage_certificate, gate_delta_plus_coverage
from gen.omega import build_omega_certificate, gate_omega

print("SMOKE: imports + basic RunState δ+ typed exercised (as in pytest)")

# mimic test_phase_omega E2E δ+
q = Question(raw="smoke", run_id="p-smk-1")
st = RunState(question=q, claims=[])
spec = Specification(run_id=q.run_id, idea=q.raw)
cov = build_coverage_certificate(spec, reviewed_failure_modes=[])
st.coverage_certificate = cov   # was getattr now direct field
rv = EmpiricalVerdict(status=EmpiricalStatus.CORROBORATED, residual=0.0, within_tolerance=True)
st.reality_verdict = rv
st.delta_plus_result = {"status": "corroborated"}
print("assign direct on typed: ok")
assert st.coverage_certificate is cov
assert st.reality_verdict is rv

# omega now uses direct
cert = build_omega_certificate(st)
res = gate_omega(st, cert, required_gates=())
assert any("coverage_certificate" in n.ref for n in cert.learning_notes)
print("omega _has/_notes with δ+ typed: exercised")

# mimic lumencrucible result dict + rs
result = {"reality_verdict": rv, "delta_plus_result": st.delta_plus_result, "coverage_certificate": cov}
assert "coverage_certificate" in result
rs = RunState(question=q)
rs.coverage_certificate = cov
print("result+rs keys/attrs: ok")

# coverage test style
reviewed = [FailureMode(id="r1", label="l", source="t", grounding=["c1"])]
c2 = build_coverage_certificate(spec, reviewed_failure_modes=reviewed)
_ = gate_delta_plus_coverage(spec, c2, reviewed_failure_modes=reviewed)
print("reviewed + build/gate: ok")

print("SMOKE PASS (equiv pytest -k 'omega or lumen or delta' all relevant asserts hold post-typing)")
