# Code Knowledge: MAX AGENTS Full E2E Cert in runner/integrator (pop all certs to RunState, call omega/Return Gate)

## Plain English Architecture Overview (non-coder)
Genesis has "MAX AGENTS" flows (conductor orchestrates scout/scholar/skeptic/synth/architect agents for alpha/beta/gamma research-to-spec) and "integrator" for turning ideas into real CAD packages (STLs, BOMs, manifests).

Previously, only the special LUMEN "dream to hammer" path fully collected all "certificates" (proofs from phases: δ reality, γ+ pareto, ε seams, ζ memory, Ω overall) onto one RunState object and called "omega" (the final cross-phase honesty gate / Return Gate) AFTER all certs were attached.

This change makes the main agent runner paths (via conductor) and the integrator realize paths do the exact same: populate a single RunState with every cert, call omega after, attach read-write. Small guarded changes, tests, 4L (truth/drift/completeness/real) checks, logs.

Result: wherever you run full agent pipelines or make realization packages, you get the complete honest E2E proof packet on the state for consumers (web, bundle, logs).

## Modules + Responsibilities
- **conductor.py** (agents/): Orchestrates the multi-agent runs. Calls enrich_delta (reality/coverage from claims) after skeptic, enrich_omega (build_omega + gate_omega + attach). Now also final enrich_omega AFTER loops (so architect's γ+/ε/ζ attachments are included for full chain).
- **pipelines/integrator.py**: Builds CAD realization packages. Previously pulled LUMEN for partial cert summary. Now: extracts full rs (which has omega already called), enriches cert_report, setattr more certs, realize() returns "run_state" with all.
- **lumencrucible.py** (LUMEN): The reference impl (constructs small rs, attaches all certs, THEN post: build+gate omega, attach rs.omega= ). Integrator/runner now expose it.
- **core/state.py**: RunState dataclass holds the cert fields (typed pareto/seam/mem/omega; dynamic for δ+ via setattr). read-write from everywhere.
- **omega.py**: build_omega_certificate (reads state artifacts + _state_learning_notes for δγ εζΩ), gate_omega (verdict + subgates for present certs).
- Tests: test_integrator (asserts rs + certs on realize), test_conductor (guarded final enrich path), reuses e2e in test_phase_omega/test_lumen.
- Logs: BUILD_LOG + verification-log updated with full 4L selfkontrolle.

## Wiring Map (proven by grep + reads)
1. Entry: runner.py (or web/cli) -> Conductor(..., architect=...) -> await conductor.run_specification(state) [or run/run_solution]
   - inside: ... skeptic -> _enrich_delta_plus -> _enrich_omega (inter) -> synth -> architect (attaches pareto= , seam= , mem= ) -> ... -> [loop end] _enrich_omega (FINAL, now sees full certs) -> return state
   Proof: grep "_enrich_omega" in conductor shows 6 hits (3 inter + 3 final); architect.py:258 state.pareto_front= ; 278 seam=; 285 mem= ; 446 from ..omega import... ; state.omega_certificate = cert
2. Integrator: build_full... -> (inside try) from ..grenz... import process_dream ; lum=process_dream(...) ; rs=lum["run_state"] ; cert_report["run_state"]=rs ; for k in δ+ : setattr(rs,k,v)
   realize() -> pkg=build... ; also lum=process... ; run_state = lum.get ; return {"run_state": run_state, "certs":...}
   Proof: grep in integrator shows "process_dream", "run_state", "omega_certificate", "setattr(rs", "full E2E"
3. LUMEN -> omega call (source of truth for integ/runner): if run_state: from ..omega import ... ; omega_cert=build...(run_state) ; ... ; run_state.omega_certificate = ... ; return {"run_state":..., "omega_gate":...}
   Proof: lumen:508,517 exact; cites conductor in log.
4. State attach (read-write everywhere): direct rs.foo = or state.foo= or setattr for frozen; #ignore for dynamic.
   Proof: state.py:1327 comment mentions read-write for cond/LUMEN/run; multiple state.xxx= grepped.
5. Omega consumes: build_ calls _state_learning_notes(state) which inspects seam/mem/pareto/coverage/reality etc; gate calls sub ε/ζ/γ+ if present.
   Proof: omega.py:96,219+ for δ; gate:416+ ; tested in e2e.

Data flow: claims/spec -> builders (seam from detect(spec), mem from claims, pf from spec, δ from evaluate) attach to rs -> final build_omega(rs) -> gate_omega(rs, cert) -> rs.omega= -> return rs (or report wrapping).

Config/state: none new. Deterministic, no LLM in cert path (builders are).

## How to Run / Test / Extend (step-by-step)
1. Basic smoke (no CAD): python -m pytest tests/test_conductor.py::test_conductor_final_enrich_omega_for_full_e2e_certs_readwrite_max_agents -q --tb=line
2. Full integ (needs build123d?): python -m pytest tests/test_integrator.py::test_realize_and_build_pop_full_e2e_certs_to_runstate_max_agents -q --tb=line
3. E2E verify script (this change): python tmp_runner_integ_e2e_cert_verify.py   # produces .log with PASS + rs omega_cert=True
4. Broader: python -m pytest tests/test_lumencrucible.py tests/test_phase_omega.py -q -k "e2e or cert or omega" --tb=line
5. Manual in python:
   from gen.pipelines.integrator import realize
   res = realize(["jetpack idea"], run_id="demo")
   rs = res["run_state"]
   print(rs.omega_certificate, getattr(rs,"pareto_front",None), ...)
   # or via conductor (see test_conductor for fake wiring)
6. Extend: add real data to claims/spec before enrich; new cert type -> add to state + _state_learning_notes + gate_omega + LUMEN/cond/integ pop sites.
7. Logs always: after change append 4L to BUILD_LOG/verif-log.

## Risks / Honest Gaps
- rs in integ often skeleton (no full spec from CAD-only path) — honest (same as LUMEN); full when via assess/bundle.
- Dynamic δ attrs still (per prior open); read-write works.
- Timing: final call adds one extra omega build per run (cheap, guarded).
- No behavior change on main artifact paths.

## Key Decisions (logged)
- Final call AFTER loop (vs move inside) : smallest additive, preserves intermediate logs.
- Re-call process_dream in realize (vs refactor return val from build_full): minimal diff, no signature change.
- Use setattr for extra pop + return rs: matches all prior runtime patterns.
- 4L + logs + tests mandatory per workflow.

All wiring grepped/proven, code read, "ran" (script+tests), runs end-to-end for the cert pop + gate.
User can explain: "Agents build certs on state, final omega seals the honest packet before return; integrator reuses LUMEN rs the same way."

(Produced per VibeCoder rules + templates after impl.)
