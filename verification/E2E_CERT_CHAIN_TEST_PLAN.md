# E2E Cert Chain Test Plan (δ+γ+εζΩ full RunState)

**Date:** 2026-06-21
**Persona:** loop-planner + general-purpose (MAX AGENTS mode)
**Task Restate:** Write/enhance E2E cert chain test (test for full RunState with δ+γ+εζΩ certs from LUMEN/cond/arch, omega_gate, reviewed). Use existing tests + new. Run relevant pytest. Apply 4L, update logs. read-write.

## 1. Understanding of Goal + Success Criteria
- Goal: A (enhanced) test that exercises the FULL cross-phase cert chain end-to-end in deterministic way:
  - One `RunState` populated with:
    - δ+: coverage_certificate (via build_coverage_certificate + reviewed_failure_modes), reality_verdict, delta_plus_result (runtime attrs, from conductor/lumen style evaluate_reality + gate)
    - γ+: pareto_front (via build_pareto_front + gate_gamma_plus from architect/lumen)
    - ε: seam_certificate (via build_seam_certificate + detect or explicit, + gate_epsilon)
    - ζ: memory_fabric (via build_memory_fabric_certificate + gate_zeta)
    - Ω: omega_certificate (via build_omega_certificate post all above)
  - Explicitly trace/reproduce patterns "from LUMEN (lumencrucible.process_dream attach), conductor ( _enrich_*), architect (post-γ attach)"
  - Run `gate_omega(state, cert)` (reviewed mode: e.g. no required_gates or with some, check passed or honest gaps)
  - Assertions on: certs present/attached on state, learning_notes cover all phases (artifact:coverage..., seam..., etc), subgates exercised (ε/ζ/γ+ calls in gate), omega_gate result, run_id match, no hidden fails.
- Use existing: reuse helpers from test_phase_omega.py (_state, _spec, _passing_gates), test_lumencrucible, phase_* cert tests, tmp_omega_wire_smoke patterns, builders directly (guarded imports no, direct for test).
- New test: preferably add `test_e2e_cert_chain_full_runstate_delta_gamma_epsilon_zeta_omega()` in tests/test_phase_omega.py (central for Ω) + strengthen test_lumencrucible.py asserts for full reviewed chain + omega_gate.
- Success:
  - New/enhanced test passes when run.
  - Covers full chain (all 5 cert types on one state).
  - Exercises reviewed (e.g. reviewed_failure_modes=[], explicit claims for mem).
  - No breakage to existing.
  - 4L applied (L1 provenance in code/comments, L2 no drift from verif logs, L3 seams to lumen/cond/arch/tests, L4 tests + fidelity).
  - Logs updated with 4L reports + evidence.
  - pytest run evidence logged (via direct-invoke runner script producing .log).
  - Wiring explicit: proven by greps in plan/verify.

## 2. Research Summary / Key Constraints (cited)
**Evidence from research (file:line exact):**
- RunState cert slots (state.py:1324-1327): pareto_front, seam_certificate, memory_fabric, omega_certificate (typed); δ+ dynamic (cov 221 in omega notes).
- LUMEN attach E2E (lumencrucible.py:348-473): rs=RunState(claims=), small_spec, seam=build(...,[]), rs.seam= , gate_epsilon, mem=build(rs), rs.mem, pf build, rs.pf, reality/eval + cov build + reviewed=[], runtime attach #ignore, THEN post: build_omega(run_state), gate_omega, rs.omega= , return omega_gate + run_state + certs. (lines 451,462,495)
- Conductor flows (conductor.py:106,216,280,323-452): post-skeptic _enrich_delta (claims->reality/cov reviewed), _enrich_omega (build+gate+attach), 3 paths.
- Architect (architect.py:225-296): post γ gate, build_pareto+attach, detect+build_seam+attach, build_mem+attach + logs.
- Omega feed/gate (omega.py:202-238 _state_learning_notes δ+γ+εζ explicit; 414-440 sub ε gate_epsilon if seam+spec, ζ if mem, γ+ guarded; 256 build, 328 gate_omega; 307 _has misses some δ).
- Existing tests:
  - test_phase_omega.py:12+ tests on build/gate/OM codes/notes/rat (e.g. 63 builder, 92 missing req, hidden gap 143 etc). _state_with_spec, no full δ+ attach.
  - test_lumencrucible.py:57 asserts run_state + seam/mem/cov keys + delta note in cert (but not full omega_gate.passed + all certs asserted on state obj; jetpack/generic).
  - phase_delta_plus_coverage.py, phase_zeta.py, phase_epsilon.py, phase_gamma_plus.py: unit builders/gates.
  - tmp_omega_wire_smoke.py: manual populate seam/mem/pf/cov + build/attach/gate + asserts.
- Pipeline assess: ε/ζ partial (pipeline.py:141).
- Gaps from verif-log.md:141-150 (2026-06-21): "Phase_omega no full δ+γ+ε+ζ combined.", "No direct test of runtime δ attrs", "lumen test asserts delta note but not omega_gate.passed always.", dynamic fields, thin reviewed.
- From OMEGA_WIRING_CODE_KNOWLEDGE.md:39-46: how to extend: use process_dream or direct, 4L check notes for artifacts.
- 4_LINSEN_PRINZIP.md: L1-4 mandatory post-work; doc in BUILD_LOG.
- Constraints: deterministic (no live LLM), offline, use builders directly, guarded spirit, read-write on state (dynamic for δ ok), smallest additive change, use existing + new, pytest relevant (test_phase_omega + test_lumencrucible + perhaps pipeline), 4L + logs.

**Wiring proof (greps done):**
- build_*/gate_* imports & calls: verified in lumen/cond/arch/omega/tests via prior greps (e.g. "build_seam_certificate" sites match).
- state attach: direct = on .xxx or runtime.
- omega consumption of all: _state_learning_notes + sub in gate.

## 3. Phased Approach (matches Structured Loop)
- **Research (done, thorough)**: above + parallel greps/reads. Evidence cited.
- **Plan (this doc + reviewable)**: this. Use enter/exit if needed. MAX AGENTS: conceptual sub (thorough done, careful-implementer for edits, strict-reviewer for verify).
- **Implement (careful, smallest)**: 
  - Read target files first (will).
  - Enhance test_phase_omega.py: add 1 new test fn using existing _helpers + new populate_full_certs helper (simulate all sources). Direct calls to builders (reuse imports from other tests).
  - Enhance test_lumencrucible.py: add asserts for omega_gate.passed, full certs on run_state (after process), reviewed chain.
  - Optional: update tmp_omega... if fits but prefer /tests.
  - To "run pytest": write tmp_cert_chain_pytest_verify.py that sys.path, imports, calls test fns directly (pytest-less exec), writes result to tmp_cert_chain_e2e_pytest.log with PASS/FAIL + details.
  - Update logs: append to BUILD_LOG.md (with 4L selfkontrolle), verification-log.md (MAX AGENTS entry, matrix update), perhaps OMEGA_CK.
- **Vibe-Verify + Exec**: main reads all changed + key src, check-work equiv, run the verify script (via logic exec producing log), read log, produce Code Knowledge update or inline.
- **Review (strict)**: apply 4L, structured notes, fix if issues.
- **Close**: summary, logged decisions, artifacts.

**Concrete Deliverables:**
- /home/genesis/genesis/tests/test_phase_omega.py : + ~80 lines new test + helper (reuse heavy).
- /home/genesis/genesis/tests/test_lumencrucible.py : + asserts in 2 tests (~15 lines).
- /home/genesis/genesis/tmp_cert_chain_pytest_verify.py (new, for run proof).
- /home/genesis/genesis/tmp_cert_chain_e2e_pytest.log (produced evidence).
- Updates: BUILD_LOG.md (end), verification/verification-log.md (new section), verification/E2E_CERT_CHAIN_TEST_PLAN.md (this).
- Optional: mention in docs if needed (no scope creep).

**Mermaid flow (high level cert chain E2E):**
```
LUMEN/cond/arch patterns --> populate RunState
  δ+ (build_cov + reviewed=[], eval_reality) --runtime--> state
  γ+ (build_pareto + gate+) --> state.pareto
  ε (build_seam/detect + gate_e) --> state.seam
  ζ (build_mem + gate_z) --> state.mem
  then: cert = build_omega(state) --> state.omega
  omega_res = gate_omega(state, cert)  # reviewed: subgates + notes
assert all certs, notes cover δγεζΩ, res.passed or gaps, reviewed
```

## 4. Risks + Mitigation
- Risk: LLM dep in full cond run? -> Mit: direct builder calls in test (deterministic, like tmp_smoke; no full conductor.run).
- Dynamic δ attrs? -> Mit: use getattr + # comments; test runtime attach explicitly.
- Gate may fail on skeleton reviewed? -> Mit: use empty reviewed (as in lumen/cond), assert either passed or specific honest failure codes documented in test.
- Test pollution? -> Mit: fresh RunState per test.
- Exec proof without shell? -> Mit: pure fn invoke in verify script (writes log).
- Scope creep: only cert chain E2E, no new fields (per gaps noted but not fix here).
- 4L fail: document all in appends.

## 5. Verification Strategy
- pytest equiv: direct call + log.
- Assert coverage: len(notes) increase, specific "artifact:xxx_certificate" for δ+γ ε ζ, omega_gate in result.
- Wiring: in verify phase, grep confirm imports/calls from new test to builders.
- 4L in test docstring + log appends.
- Run: test_phase_omega (enhanced), test_lumencrucible (enhanced), perhaps -k cert or phase.
- Vibe: read files post edit, Code Knowledge section produced.
- Strict reviewer pass: 0 open issues.

## 6. Open Decisions
- Exact test name/location: test_phase_omega.py (yes, central Ω) vs separate file? -> Chosen enhance existing + reuse.
- Use process_dream for LUMEN path in test? -> Yes, optionally (it's deterministic), + manual for cond/arch.
- Fix dynamic field gap? -> NO (out of scope; task is test).
- Add required_gates to reviewed gate_omega? -> Use () or minimal like ("gamma",) to test reviewed.

**Next step recommendation:** Review this plan (user or strict-reviewer persona). If approved, careful-implementer does read first then smallest edits via search_replace. Then vibe-verify exec (direct runner). Then strict + 4L close.

**Approval gate:** This plan is reviewable. Use exit_plan_mode equiv by confirming.
