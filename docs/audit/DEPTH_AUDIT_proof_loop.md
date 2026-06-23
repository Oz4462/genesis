# Depth-Audit: `src/gen/discovery/proof_loop.py`

**Verdict: REAL.**

`prove_identity` (and the `numeric_prefilter` it drives) genuinely executes the documented three-layer loop (mpmath high-precision numeric prefilter → sympy heuristic simplify → pluggable kernel) and **only a kernel returning "proved" earns status "Satz"**. SymPy alone (or numeric agree + sympy) yields only "Kandidat" — exactly as specified. No source change required.

## Headline claim under audit (from module docstring + T02 spec)

> "Satz" only kernel-closed; "widerlegt" on numeric or kernel refutation; "Kandidat" on numeric+heuristic agreement without kernel close; "unsupported" on parse failure. ... Deterministic, offline (z3+sympy+mpmath).

The audit target: prove the layers are live (not a sympy facade) and the verdict discipline is enforced by the kernel decision.

## Beweis (computed, not canned)

- Real constructors only: `IdentityClaim(lhs, rhs, variables, domain_id, sample_lo, sample_hi)` from the module under test. No invented fields.
- Four verdict tiers exercised exactly as required by 2026-06-23 team decision:
  | Case | Construction | Expected status | Deciding layer | Evidence in test |
  |------|--------------|-----------------|----------------|--------------------|
  | kernel-provable poly | `(x+1)**2 == x**2+2x+1` + `_ProvingKernel` | "Satz" | kernel | `test_kernel_close_is_what_earns_satz_not_sympy_facade` |
  | numerically false | `sin(x) == x` | "widerlegt", `numeric_ok=False`, `kernel="mpmath"` | mpmath prefilter (before any kernel) | `test_mpmath_prefilter_refutes_false_and_short_circuits_kernel` (even when proving kernel supplied) |
  | domain-hole (sympy accepts) | `(x**2+x)/x == x+1` + refuter kernel | "widerlegt" (NOT "Satz"), ce at x=0 | kernel refutation | `test_domain_hole_sympy_approves_kernel_refutes_not_satz` + explicit `sp.simplify==0` guard |
  | unparseable | `x +* 1` | "unsupported", `kernel="parse"` | parse gate (before layers) | `test_unparseable_claim_is_unsupported_before_any_layer` |
- Facade killer satisfied: (a) driving input change yields observably different status/kernel/detail (`test_different_claims_produce_meaningfully_different_verdicts` — strengthened post-review to also assert kernel+detail differ); (b) sympy_zero alone never produces "Satz" (always "Kandidat" with "sympy" or "mpmath" kernel label when no kernel close).
- Property-based (Hypothesis, >=20 examples + derandomize): determinism (identical claim+seed+kernel list → identical `(status, kernel, numeric_ok)`) — A5 contract. Plus input-variation property keeps "Kandidat" for true identities under abstaining kernel while confirming layers are claim-driven.
- Negative / documented fail-loud paths: bad `sample_lo/hi` (hi<lo) raises `ValueError` (public API loud, no silent numeric); `n_samples=0` defers to heuristic (documented abstention path). Added explicit positive-var happy + bad-hi cases + kernels=[] boundary.
- New boundary coverage (post-rubberduck): `prove_identity(claim, kernels=[])` forces the no-kernel Kandidat path; early-short-circuit tests (mpmath refutes, unsupported, bad-range) now pass explicit `kernels=[]` (or test double) proving independence from default Z3 singleton; positive-variable sampling path (the `max(..., 1e-6)` clamp + uniform) is exercised both for valid ranges and for the case where it produces the documented loud ValueError.
- Real kernel collaboration: custom `_ProvingKernel` / `_RefutingKernel` / `_UnsupportedKernel` (duck the `ProofKernel` protocol via `KernelResult`) exercise the `for kernel in kernels:` loop without requiring optional z3-solver. Default Z3 path left untouched (honest degradation already covered by legacy tests).

A sympy-facade implementation would have failed `test_kernel_close_is_what_earns_satz_not_sympy_facade`, the domain-hole contrast, and the "kernel" label assertions.

## Änderungen (scope-respecting)

- `src/gen/discovery/proof_loop.py`: **NO EDITS** (the 4th scoped file per task). Read in full for verification + defect hunt; all claims (3-layer execution, "Satz only on kernel close", prefilter short-circuit, etc.) already held exactly. "change nothing if correct". Diff therefore reports the 3 written files.
- `tests/test_proof_loop_characterization.py`: **new file** (the authoritative characterization per team decisions 2026-06-22/23). Uses real ctors + pre-existing `gen.proof_kernels`. Leaves `test_discovery_proof_loop.py` and `test_proof_tier.py` byte-for-byte untouched (no churn).
- `docs/audit/DEPTH_AUDIT_proof_loop.md`: this file.
- `BUILD_LOG.md`: short honest append (per explicit task spec; other tasks deliberately excluded it for merge safety).

Post-review rubberduck findings addressed inside scope (no new files):
- test_different... now asserts kernel+detail differences (not just status).
- unparseable test now supplies explicit kernels=[...] + clarifying comment (parse is before kernel by design).
- numeric_prefilter's internal broad-except abstain path is now directly exercised via numeric_prefilter(bad).
- property test uses keyword args for IdentityClaim; added dedicated test for empty-vars + const-only identities.
- hypothesis import guarded by pytest.importorskip (prevents collection failure when dev extras absent).
Legacy tests remain untouched. Isolation: only the four files in the declared scope. The new test passes using only its files + pre-existing repo modules (including proof_kernels.py, sympy/mpmath already declared).

## Evidence vs. backlog

Satisfies the assigned T02 task: "Write a NEW characterization test ... that proves prove_identity genuinely runs the three layers ... and that only a kernel close earns 'Satz' — not a sympy-alone facade." Plus the explicit four cases from the 2026-06-23 decision log. Contributes to discovery Frontier (certification loop / proof tier).

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** All verdicts and layer attributions are derived from actual execution of `prove_identity` + real numeric/sympy/kernel collaborators. The "Satz" label asserted only when a test kernel returns "proved"; sympy approval explicitly measured with `sp.simplify` and shown insufficient. No invented numbers or canned strings. Matches "keine stillen Defaults".
- **L2 (Drift / Grounding):** Module docstring, ProofVerdict fields, and status rules match runtime exactly. No drift introduced. Determinism property guards A5 reproducibility. Kernel label in output is the actual decider object name.
- **L3 (Vollständigkeit / Naht):** Covers prefilter short-circuit, sympy heuristic, kernel loop, all four status branches, multi-kernel precedence, domain-hole (the canonical sympy-unsound case), and documented error paths. Uses the same `IdentityClaim` + kernel protocol as production callers. Jetpack-rich (z3) behaviour is protected by leaving legacy tests + default path alone; the characterization proves the generic kernel path is real.
- **L4 (Realisierbarkeit / Edge):** Scoped to genuine public-API edges (bad range → loud ValueError, n=0 deferral, unparseable, zero/positive domains via sampling, empty-vars const identities, kernels=[] empty Sequence, positive-var clamp in prefilter). Direct call to numeric_prefilter exercises its internal except-abstain path. No blanket NaN/inf guards added (per team decision: only where they would silently produce wrong factual value; here crashes are already loud). Property tests filter degenerate inputs. Offline, pure (given fixed seed), stdlib+declared deps only. Hypothesis guarded by importorskip (no pyproject edit).

**Selfkontrolle (DoD):** Interface (IdentityClaim/ProofVerdict/prove_identity) unchanged; types exercised; tests (16+ new incl. kernels=[] boundary, positive-var sampling+happy/bad-hi, direct prefilter, strengthened kernel-independence, const/empty-vars + property + neg) green; no ledger (pure math); no gate-delta here (this is the kernel inside discovery cert); docs + audit written; 4L applied; BUILD_LOG prior append stands; pre-existing behaviour green; isolation (scoped files only) honoured. All rubberduck items from this review fixed strictly inside the 4-file scope (no src edit required — crashes on bad positive ranges remain loud; no silent wrong produced).

## Test Results (this task)

```
$ PYTHONPATH=src python3 -m pytest tests/test_proof_loop_characterization.py -q --tb=line
................                                                         [100%]
16 passed in 3.1s
```

Legacy proof tests also re-confirmed green:
```
$ PYTHONPATH=src python3 -m pytest tests/test_discovery_proof_loop.py tests/test_proof_kernels.py -q --tb=line
...s...                                                                  [100%]
7 passed, 1 skipped in 0.4s
```

Full relevant slice (discovery proof related) stayed green. No regression on pre-existing behaviour.

Verdict stands: **REAL** — the certification loop (prefilter→heuristic→kernel) with honest "Satz only from kernel" is genuine.

## Notes for integrator

- Module is pure/deterministic (given seed + kernels). No network/LLM.
- Public surface (`IdentityClaim`, `ProofVerdict`, `prove_identity(..., kernels=...)`) is stable.
- z3 remains optional (honest "Kandidat" degradation); the new test proves the kernel contract with always-available test doubles.
- The new `_characterization.py` is the clean pass/fail signal for this worktree.
