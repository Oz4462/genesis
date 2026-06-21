# Code Knowledge — Ω Full Aggregation Wiring (build_omega + gate_omega post-certs)

Genesis phases (α/β/γ/δ/ε/ζ/φ...) each have gates and produce certs (seam=ε, memory=ζ, pareto=γ+, reality/coverage=δ+). Previously, Ω (the cross-phase honesty "exoskeleton" in omega.py) was defined (build_omega_certificate makes the decision sheet + learning notes from state; gate_omega validates no hidden fails/gaps) but *not called* in main conductor/runner flows after certs attached. LUMEN used a private _build receipt only. Result: full Ω aggregation (notes from *all* phases + subgates) not active in orchestration or swarm flows.

**Current state (post wiring 2026-06-21):**
- State: RunState.omega_certificate declared (read-write) + runtime δ+ attrs (dynamic).
  Proof: grep "omega_certificate|seam_certificate|pareto_front" shows attaches + field use.
- omega.py:237 `def build_omega_certificate(state, gate_results=None, ...)` → OmegaCertificate(run_id, gate_receipts, learning_notes=..., )
  - Internally: _state_learning_notes(state)  [pulls from subq/claims/report/spec/pareto/seam/memory + δ coverage/reality/delta]
- omega.py:309 `def gate_omega(state, cert, required_gates=(), ...)` → GateResult
  - Checks OM-1..8 + HORIZON sub: ε (gate_epsilon if seam), ζ (gate_zeta if mem), γ+ (gate_gamma_plus if pareto, guarded).
- Wiring sites (post-certs):
  - lumencrucible.py:445 post E2E attach: omega_cert = build_omega_certificate(run_state, gate_results=pre); omega_res = gate_omega(...); run_state.omega_certificate = ... ; return includes "omega_certificate", "run_state", "omega_gate"
  - conductor.py:106/216/280: self._enrich_delta_plus(state); self._enrich_omega(state) in run/run_solution/run_specification (3 paths)
    - _enrich_omega: try: cert=build; res=gate; state.omega= ; log
  - architect: post γ+ attach pareto + ε/ζ (guarded)
  - Also: pipeline (ε/ζ to Assessment), runner (δ), smoke/tmp.
- return dict: "omega_certificate", "omega_gate": ..., "run_state" (with field)
- _build_omega_certificate kept for pre/simple (lumen internal).
- Proof: grep "after certs|build_omega_certificate.*run_state|run_state.omega_certificate" ; process_dream 644; spawn_swarm 685+ ; test_lumencrucible:57 asserts run_state + delta notes.

**Phase feed (δγ εζ) full:**
- δ: conductor _enrich_delta (evaluate_reality + cov with reviewed from claims/skeptic); lumen skeleton; omega notes 221 cov/reality/dpr; state runtime attrs.
- γ: architect γ+ build_pareto + attach; lumen pf skeleton; omega 190+ notes + gate 432 sub.
- ε: architect/pipeline/lumen build_seam (real or []); omega 424 gate_epsilon; notes 202.
- ζ: similar memory_fabric + gate_zeta; notes 209.
- All surface in cert.learning_notes + sub validated in gate_omega if present.
- _has_run_output covers pareto/seam/mem (δ partial gap).

**Strict review (2026-06-21 append):** See verification-log.md for full matrix + ruthless gaps (dynamic attrs, thin reviewed, _has incomplete for δ, skeletons). Wiring PASS overall; tests PASS struct; 4L Return Gate active. MAX AGENTS: Ω in cond + lumen swarm.

**Call sites (MAX AGENTS):**
- LUMEN process_dream → (after attach seam/mem/pareto/δ) → build_omega( state ) → _state_learning_notes (δ+γ+ε+ζ) → OmegaCert → gate_omega (sub ε/ζ + pareto) → assign state.omega + return + log
- Conductor._enrich_delta (attach δ) → _enrich_omega → build/gate → assign + log
- Runner → Conductor → above
- State read: build reads state.xxx ; write: state.omega_certificate = (field supports)
- Import chain: conductor/lumen/verif → omega (no cycle: omega imports state only for types; state uses str annos)

**How to run / test / extend (step-by-step for you):**
1. Pure (no model): python -m pytest tests/test_lumencrucible.py -q --tb=line   # exercises LUMEN post-cert Ω, asserts cert/run_state/notes
2. Smoke: python tmp_omega_wire_smoke.py   # full post-cert build+gate+δ notes+assign, prints SUCCESS
3. Full flow: use runner.run_specification(...) or conductor.run_spec (with mocks/llm) — now produces state.omega_certificate
4. Inspect: after run, print(len(state.omega_certificate.learning_notes)); state.log[-3:]
5. Extend: supply gate_results= {"gamma": gate_gamma(...)} to build for receipts; pass required_gates=("gamma","epsilon",...)
6. Swarm MAX: result = process_dream(...); hive=spawn_swarm(...); integ=integrate... ; # sees "omega_for_max_agents"
7. 4L check: after, verify cert has notes for "artifact:coverage_certificate" etc + gate.passed or documented gaps.

**Risks / next (honest):**
- Skeleton certs in some paths (like before) → honest gaps surfaced in Ω notes.
- δ+ now use typed fields on RunState (coverage_certificate etc); dynamic removed (2026-06-21 task); direct in omega _state_notes + _has.

**E2E cert chain test added (2026-06-21 loop-planner task):** tests/test_phase_omega.py::test_e2e_full... now exercises one full RunState populated δ(cov+reality+delta reviewed)+γ(pf)+ε(seam+gate)+ζ(mem+gate)+Ω(omega_cert+gate_omega reviewed) from LUMEN/cond/arch patterns + asserts. Also enhanced lumen test. Run proof in tmp_*.log + BUILD/verif appends with 4L. Wiring: direct import/call of builders + state. = + gate calls proven by grep. See E2E plan + logs.

- Requires full cert pop for rich Ω (lumen/cond now ensure when available).
- Test coverage: smoke + lumencrucible cover; phase_omega tests unchanged but benefit indirectly.

**All wiring verified (as-you-go + final):**
- Imports: grepped
- Calls: grepped exact lines
- State read/write: grepped + read sections
- Data: build pulls _state_notes → notes include δ now; gate calls subs
- Execution: smoke + test paths run without crash (structure)
- 4L: explicit section above; follows bible + DoD (exec, proof, theory gates deterministic O(1) per artifact count, logs, docs)

**User takeaway (you can explain):**
"After any phase certs get stuck on the RunState (like memory fabric or pareto front), we now feed the whole thing to Ω which collects honest learning notes from every phase (including the new δ reality ones) and gives you one gate receipt for the entire run. It's called right in the conductor loops and in LUMEN after its E2E attaches, so every main flow and even the agent swarm gets the full aggregation. The state now has a proper field for it, logs are written, and it's all guarded so nothing breaks. That's the 4 Linsen Return Gate in action."

This document + verif-log + greps + smoke result + code reads = full Code Knowledge. No magic.

## STRICT REVIEW APPEND (2026-06-21, strict-reviewer+thorough-researcher MAX AGENTS)
See full matrix + details + pytest analysis + ruthless gaps in /home/genesis/genesis/verification/verification-log.md (appended section "STRICT-REVIEWER + THOROUGH-RESEARCHER: Ω Wiring Review...").
Key: wiring PASS, phase feed FULL in notes/gates, tests struct PASS, but gaps: dynamic δ attrs, _has omits δ, thin reviewed, skeletons. Re-reads/greps all done. Read-write confirmed. Appended to this + verif-log + tmp_omega result log. 

**Matrix summary (see full in verif-log):**
| Component | Status | Issues |
| omega build/gate | PASS | _has misses δ; gamma guarded |
| state field | PASS | δ+ dynamic only |
| lumen post | PASS | skeletons; legacy _build |
| cond _enrich_ω | PASS | relies prior |
| phase δγ εζ | FULL feed | thin pop |
| tests | PASS struct | no direct gate.passed assert |

**Verdict:** Solid 4L Ω Return Gate active. Fix dynamics/thin for prod. All evidence from re-reads.