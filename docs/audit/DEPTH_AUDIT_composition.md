# Depth-Audit: `src/gen/discovery/composition.py`

**Verdict: REAL.**

`discover_correction` genuinely performs minimal additive dimensional symbolic regression on the signed residual `r = y − y_base` (from a composed baseline of sourced laws) and applies the δ-asymmetry gate before asserting a correction. The new `tests/test_composition_characterization.py` proves input consumption (different baselines/problems change output; exact coupling structure recovered) and the honest abstention path.

## Headline-Claim (from module + GROK_BUILD / STATUS 6.5)

> Given observational data for a target and a baseline prediction coming from the naive composition of independently-sourced laws, form the residual and discover the smallest dimensionally-valid additive correction term (if any). A correction is only returned under the strict three-way gate (`residual_explained >= 0.9` ∧ `ΔR² > 1e-3` ∧ `loo_r2 >= 0.5`); otherwise the honest verdict is `vollstaendig` (no correction within the additive monomial basis). The fit is on the SIGNED residual so the coefficient carries direction; every term is dimensionally consistent by construction.

## Beweis (computed, not canned)

- Real constructors only: `DiscoveryProblem` / `Variable` / `Constant` from `engine.py` (read actual field names and defaults; `run_id` etc.). No invented fields or bypassing.
- Coupling case (exactly `y = x + 0.5·k·x²`, `y_base = x`, n=8): yields `verdict="korrektur_noetig"`, exactly one `Term` with `coefficient≈0.5`, `exponents={"x":2.0, "k":1.0}`, `residual_explained>=0.9`, `loo_r2>=0.5`, and `ΔR² > 1e-3` — `test_discovers_minimal_coupling_correction_and_crosses_delta_gate`.
- Pure-noise residual case: `verdict="vollstaendig"`, `n_terms=0`, `correction_terms=()` — proves the δ-gate actually withholds promotion when there is no generalising structure (`test_pure_noise_residual_yields_honest_abstention_not_rubber_stamp`).
- Length mismatch: raises `ValueError` with the documented message containing "baseline_prediction length ... != target length" — `test_length_mismatch_raises_valueerror`.
- Additional negative: exact baseline match → `vollstaendig` + 0 terms.
- Property-based (Hypothesis, >=40 examples): determinism (`r1 == r2` for identical problem+baseline, A5 contract); structure of recovered coupling term on exact-construction draws (when n sufficient). `test_discover_correction_is_deterministic_and_gate_contract`.
- Real math path exercised: `_greedy_correction` + `_fit` (lstsq) + `_leave_one_out_r2` + `candidate_term_exponents` (dimensional lattice solve) on the residual. The coefficient recovery `coef * (x**2 * k) = 0.5 * k * x**2` is numerically exact.
- No dependence on LLM, RNG inside the function, or hidden constants.

A constant-stub or facade implementation would have failed the "exact 0.5 + x2 k" recovery, the three gate assertions, the noise-abstention, the determinism property, and/or the length guard.

## Änderungen (scope-respecting)

- **`src/gen/discovery/composition.py`**: **NO EDITS**. Length guard, δ-gate (residual_bar + significance + loo), greedy selection, LOO, term construction, and non-positive delegation to `_arrays` were already present and matched the documented contract exactly (L1 + L4 + "keine stillen Defaults"). "change nothing if correct".
- **`tests/test_composition_characterization.py`**: new file (the authoritative characterization signal per 2026-06-23 decisions). Uses only real ctors + pre-existing modules. Does not touch or depend on legacy `test_discovery_composition.py`.
- **`docs/audit/DEPTH_AUDIT_composition.md`**: this file.

Legacy tests remain byte-for-byte untouched (no churn). Isolation satisfied: task only touches its three scoped paths. BUILD_LOG.md deliberately untouched (merge-collision avoidance per team decision).

## Evidence vs. backlog

Satisfies the 2026-06-23 assigned T02 task and the Frontier 6.5 item ("Minimal-Correction bei Komposition") in `docs/discovery/STATUS.md`, `GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md`, and `GENESIS_PLATFORM_PLAN.md`. Proves the residual SR + honest δ-asymmetry gate over additive monomials (the declared scope; multiplicative/transcendental remain out of scope and are routed to `transcendental.py`).

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** All numeric results (coef, residual_explained, loo_r2, verdict) are derived from real lstsq fits on the residual of real problem data + the dimensional lattice from `candidate_term_exponents`. The 'vollstaendig' case on noise is an explicit abstention with measurable low explained variance, not a fabricated "complete". No hallucinated law. Matches "keine stillen Defaults".
- **L2 (Drift / Grounding):** Determinism asserted via property test (identical inputs → identical `CompositionResult`). No RNG, no LLM inside module. Uses the same `DiscoveryProblem` and dimensional machinery as the rest of discovery (engine/multiterm). Cross-checked by both example and generative tests.
- **L3 (Vollständigkeit / Naht):** Covers the core facade-risk surface exactly as specified: (a) output changes with driving input (coupling structure recovered only when the term is present in residual), (b) documented fail-loud + honest abstention paths exercised. The three conditions of the δ-gate are individually asserted. Jetpack/rich behaviour (exact recovery) protected implicitly by the exact numeric match; the generic correction path is proven live. Ties the composition claim to the rest of the discovery pipeline (uses multiterm internals unmodified).
- **L4 (Realisierbarkeit / Edge):** Guards as documented (length mismatch, non-positive inputs via delegation). n>=6..8 regime used for gate reliability. No blanket NaN/inf added (scoped to spec; current bypass of <=0 on NaN produces a non-asserted result rather than wrong numeric claim in the exercised paths, and adding it was not required by the T02 spec). Property test filters degenerate inputs.

No over-scope changes. No new dependencies (hypothesis already declared in dev extras). The characterization test is self-contained, passes using only its files + pre-existing repo modules, and satisfies the "pass using only this task's files plus pre-existing" isolation rule.

## Test Results (this task)

```
$ PYTHONPATH=src python3 -m pytest tests/test_composition_characterization.py -q --tb=short
.....                                                                    [100%]
5 passed, 1 warning in 2.16s
```

Full relevant discovery slice (legacy composition + engine/multiterm) stayed green. No regression.

Verdict stands: **REAL** — minimal-correction discovery on residuals is genuine.

## Notes for integrator

- This module is pure/deterministic (no network, no external state).
- Public API surface (`discover_correction`, `CompositionResult`, the three DEFAULT_* bars) is stable.
- The new test is intentionally a separate `_characterization.py` so it can serve as the clean pass/fail signal for this worktree without churn on pre-existing tests.
