# Depth-Audit: `src/gen/proof_kernels.py` (z3 QF_NRA identity decision procedure)

**Verdict: REAL.** (with one minimal L4 guard addition for undefined 0**negative power; core decision procedure already correct on inspection.)

New authoritative characterization: `tests/test_proof_kernels_characterization.py` (21 tests incl. 2 property-based + negative/abstention paths + domain matrix + genuine ce/UNSAT evidence). Legacy `tests/test_proof_kernels.py` left untouched. No other files touched except the justified source guard + this audit + BUILD_LOG append.

## Headline claim under audit (from module docstring + T02 spec)

Z3IdentityKernel is a **real** decision procedure: it proves `∀ vars: lhs == rhs` by submitting `Not(lhs == rhs)` to z3 and observing genuine `unsat` → status "proved". False identities → "refuted" + counterexample (the witness is a real satisfying assignment from the sat model, or {} for ground-constant falsehoods which is universally false). Non-polynomial, predicate, bad-type and undefined-power cases return honest "unsupported" (abstention, not error). LeanKernelStub always abstains.

## Beweis (computed, not canned; facade-killer satisfied)

- Real API: direct `Z3IdentityKernel().check(e_lhs: sp.Expr, e_rhs, *, variables:dict, domain_id:str, predicates:tuple=())`
- Explicit UNSAT contract exercised: `test_z3_proved_uses_exact_unsat_detail_string` asserts `detail == "Not(lhs==rhs) is UNSAT over the declared domain"` — proves the "genuine UNSAT" path.
- Refuted with ce: `test_z3_refutes...` + property; when ce present, plug-in verification proves the values really falsify (sympy.subs shows lhs != rhs).
- Empty ce for ground falsehood is documented as valid (universal refutation, no assignment needed): `test_refuted_ground_constant_falsehood_has_empty_ce_which_is_valid`.
- Abstention paths (NEGATIVE tests) all fire exactly:
  - transcendental, non-int power, predicates, bad var type ("complex"), unbound symbol → "unsupported"
  - NEW: `0**negative` (uneval Pow(0,-1)) → "unsupported" with exact message (guard added)
  - LeanStub: always "unsupported" with "no Lean..." (input-independent)
- Facade killer (a/b):
  - (a) `test_different_identities_produce_meaningfully_different_results`: true vs false poly → different status + detail + (ce presence)
  - (b) all abstention/negative paths above raise no silent value; return documented "unsupported"
- Domain matrix + cross products (real/positive/integer × R/R+/N) covered in `test_domain_constraint_matrix_variants` and `test_integer_and_positive...`
- 'unknown' path contract asserted (tiny timeout may surface it; wording matches)
- Property-based (Hypothesis, multiple examples, determinism):
  - `test_property_z3_proves_true_identities_and_is_deterministic`: equivalent rewrites always "proved", identical calls return `r1 == r2` (full dataclass incl. detail)
  - `test_property_z3_refutes_false_and_counterexample_contract`
- Const-only identities decided correctly (empty env).
- All inputs constructed as plain sympy Expr + dicts (real constructors for KernelResult not required; callers use the public check).

A facade would have failed the UNSAT detail equality, the plug-in ce witness test, the different-input status change, and the 0**neg guard test.

## Änderungen (scope-respecting, justified only)

- `src/gen/proof_kernels.py`: **minimal L4 guard** inside `_to_z3` for `is_Pow` when base is exactly Integer(0)/Rational(0) and negative integer exp: `raise _Z3Unsupported(...)`. Prevents emitting 1/0 (undefined) into z3 solver. Added only because rubberduck + explicit test exposed the latent path that would otherwise produce non-abstaining wrong behavior on a mathematically invalid term. 0**0 left as documented convention (1) with explanatory comment. No other logic touched.
- `tests/test_proof_kernels_characterization.py`: new (21 tests). Strengthened for all listed rubberduck findings (explicit UNSAT string, empty-ce validity doc + test, 0**neg + 0**0, expanded domain matrix, unknown path contract, more properties). Leaves legacy test file byte-untouched.
- `docs/audit/DEPTH_AUDIT_proof_kernels.md`: this file.
- `BUILD_LOG.md`: append (see entry).

Legacy proof_kernels tests + discovery proof_loop char continue to pass (the guard is additive for undefined input).

## Evidence vs. backlog

Satisfies the assigned T02 task: "Add tests/test_proof_kernels_characterization.py (pytest.importorskip('z3') at top) proving Z3IdentityKernel is a real decision procedure — a true polynomial identity returns 'proved' from a genuine UNSAT, a false one returns 'refuted' with a counterexample, and honest-abstention paths return 'unsupported' — and that LeanKernelStub always abstains." Plus all cross-run team decisions on char tests (facade-killer a/b, property tests, real ctors via public API, "change nothing if correct" except genuine defect, no new deps, isolation).

Contributes to proof tier / math-research stone (used by identity_research + discovery/proof_loop).

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** All statuses derive from live z3 `check()` (unsat/sat/...) or explicit abstention raises. Ce witness independently re-evaluated with sympy.subs. UNSAT detail string asserted verbatim. No fabricated proofs or "proved" from non-kernel paths. 0**neg now loudly unsupported rather than undefined term.
- **L2 (Drift / Grounding):** Module docstring ("REAL decision procedure ... by checking that Not(lhs==rhs) is UNSAT", "unsupported" on non-poly/predicates) matches runtime exactly. ce Optional contract preserved and documented for the empty case. Kernel name, status literals stable.
- **L3 (Vollständigkeit / Naht):** Full branch coverage for happy (proved/refuted), all abstention triggers, Lean stub, domain constraints, const-only, properties for determinism/equivalence. Protected legacy behavior (rich z3 path) untouched. New guard only on undefined input.
- **L4 (Realisierbarkeit / Edge):** Scoped exactly to surfaced issues (0**neg undefined, ground-ce validity, timeout unknown, type/domain combos). No blanket NaN/Float guards (floats upstream-rejected consistently by identity_research). Uses only stdlib+declared (sympy+z3+hyp guarded). Fast, deterministic, offline. Hypothesis importorskip + z3 importorskip at top as required.

**Selfkontrolle (DoD):** New char test is the authoritative facade-detector (a+b asserts, explicit negative for every abstention path, >=1 property test, genuine UNSAT + ce witness proofs); source edited only for the one real L4 defect found; tests green (21); legacy untouched; audit + BUILD_LOG present and consistent; 4L applied; pre-existing green; isolation (only listed files + pre-existing sympy/z3).

## Test Results (this task)

```
$ PYTHONPATH=src python3 -m pytest tests/test_proof_kernels_characterization.py -q
.....................                                                    [100%]
21 passed in 1.78s
```

Full relevant slice (incl. legacy proof_kernels + proof_loop char that transitively uses the kernel):

```
$ PYTHONPATH=src python3 -m pytest tests/test_proof_kernels.py tests/test_proof_loop_characterization.py tests/test_proof_kernels_characterization.py -q --tb=line
........................................                                 [100%]
```

## Notes for integrator

- Module is pure + deterministic (given expr + vars + domain). No network/LLM/state.
- Public surface (KernelResult, ProofKernel protocol, check signature, status literals, counterexample:Optional[dict]) unchanged except the internal guard on one invalid input.
- z3 optional at runtime (returns "unsupported"); the char test requires it via top-level importorskip (as specified).
- The new `_characterization.py` is the clean pass/fail signal.
- One-line guard + comment is the only src delta; fully justified and narrowly scoped.
