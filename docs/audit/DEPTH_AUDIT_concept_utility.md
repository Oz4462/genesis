# Depth-Audit: `src/gen/discovery/concept_utility.py` (ledger-learned contrastive prior)

**Verdict: REAL.**

`ConceptUtility.fit` genuinely learns a contrastive log-likelihood-ratio prior from `(Candidate, passed)` gate-verdict records. It is not a constant facade. The new `tests/test_concept_utility_characterization.py` (10 tests + 3 Hypothesis properties) proves input consumption, the documented invariants, deterministic tie-break ordering, and honest zero on no-contrast / unseen cases. All Candidates constructed via the real engine builder. No source edit required.

## Headline-Claim (from module docstring + CAPABILITIES / discovery flow)

> Fit a deterministic, offline contrastive utility over discrete concept tokens (var, exact rational exp, complexity bucket) extracted from Candidates. Positive utility for concepts that historically correlate with PASSING the deterministic gate; negative for those that correlate with FAILING. Used only to break ties among otherwise-equal validated candidates (`discover_new_formulas(..., prior=...)`). A ledger with no contrast (all pass or all fail) or an unseen concept yields the neutral 0.0. The gate verdict is never overridden.

## Beweis (computed from real gate verdicts, not canned)

- **Real constructors only**: All `Candidate` objects are obtained exclusively via `candidate_from_exponents(problem, exps)` (the public engine builder that calls the real `_build_candidate` path) or `discover_new_formulas(...).all_records`. `DiscoveryProblem` / `Variable` / `Constant` use the literal field names from `src/gen/discovery/engine.py`. `concepts_of` is applied to these live objects. Never hand-crafted dicts that bypass the engine.
- **(1) Contrast is learned and drives re-ranking**:
  - `test_utility_learns_positive_for_pass_correlated_and_negative_for_fail`: ledger with `a^3/2` shape always PASS and `a^1` shape always FAIL yields `utility("exp:a^3/2") > 0 > utility("exp:a^1")`.
  - `test_score_and_order_actually_re_rank_by_learned_signal`: `score(good_shape) > score(bad_shape)` and `order([bad, good])` places the historically-passing-shaped candidate first. Changing the label correlation changes the numeric utilities and the produced order — proves the ledger is consumed, not ignored.
- **(2) No-contrast invariant holds**:
  - All-pass or all-fail ledgers → every `utility(c) == 0.0` and `score(any) == 0.0`.
  - Completely novel concept tokens (different var names via `_unseen_problem`, or unseen "complexity:99"/"exp:never^99") → exactly 0.0.
  - `test_unseen_concept_scores_exactly_zero`, `test_no_contrast_invariant...`, `test_empty_ledger...`.
- **(3) Determinism + documented tie-break**:
  - `order` on identical input lists is identical (expression list equality).
  - On neutral prior (all scores 0): lower `complexity` precedes higher; for equal complexity the smaller `expression` string precedes (lex). Verified with real engine-rendered expressions containing the coefs and `^` forms.
- **Property-based (Hypothesis)**:
  - `test_fit_determinism_and_signs_property`: for arbitrary positive `(n_pos, n_neg, smoothing)` the two fits are identical dicts and signs are correct.
  - `test_no_contrast_property_yields_uniform_zero`, `test_order_deterministic_under_varying_counts`.
- **Real gate verdicts end-to-end**: `test_from_result_consumes_real_engine_verdicts` runs `discover_new_formulas` (the actual gate) and feeds the resulting `DiscoveryResult.all_records` into `from_result`.
- A constant-stub implementation (always 0 or fixed scores) would have failed every "different ledger → different utilities", "re-rank happens", "signs follow labels", and the Hypothesis determinism/sign properties.

## Änderungen (scope-respecting, per team decisions)

- **`src/gen/discovery/concept_utility.py`**: **NO EDITS**. The Laplace-smoothed log(p⁺/p⁻), the `if n_pos and n_neg` guard, `score` averaging, `order` key `(-score, complexity, expression)`, `from_result`, and `concepts_of` (delegating to `_format_exponent`) all matched the documented contracts exactly. "change nothing if correct".
- **`tests/test_concept_utility_characterization.py`**: new file (authoritative facade-detector + regression). Uses only pre-existing public APIs + already-declared deps (numpy, hypothesis in dev extras). Does not touch `tests/test_concept_utility.py` or any legacy test.
- **`docs/audit/DEPTH_AUDIT_concept_utility.md`**: this file.

Isolation rule satisfied: this task touches only its three scoped paths. All transitive dependencies (`engine.py`, `benchmark.py`) are pre-existing repo files.

## Evidence vs. backlog / platform

- Directly addresses the "ledger-learned contrastive prior" capability listed in `docs/CAPABILITIES.md` (RL-Ökosystem / Gate als Oracle) and the composition in `src/gen/discovery/campaign.py` (`prior = ConceptUtility.fit(ledger)` accumulated across problems).
- Upholds A5 reproducibility (deterministic fit/order) and "keine stillen Defaults" (explicit 0.0 when no contrast exists).
- Satisfies the 2026-06-23 T03 assignment for the five discovery modules (concept_utility among campaign/composition/controller/cosmic_insight).

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** Every numeric utility value is `math.log( (count_pos + s) / (n_pos + 2s) / ... )` computed from actual PASS/FAIL counts in the supplied records. The records used in tests are either (a) hand-labelled on engine-built Candidates (the labels stand for "gate verdicts" from prior runs) or (b) the literal `passed` flags coming out of `discover_new_formulas` real gates. No hardcoded table, no guessed prior. The zero-on-no-contrast rule is a deliberate honest abstention, not a bug.
- **L2 (Drift / Grounding):** Implementation matches its own docstring and the call sites (campaign, engine `prior.score` only in the tertiary key of `_key`). No drift between "learns what to avoid" claim and the sign tests. Determinism asserted both by example and by Hypothesis over varying counts/smoothing. Re-uses the exact `Candidate` and `concepts_of` that the rest of discovery uses.
- **L3 (Vollständigkeit / Naht):** The characterization covers the complete public surface that can affect ordering (fit from list and from_result, utility, score, order) plus the two critical invariants named in the module. Negative paths (empty ledger, all-same labels, unseen) are exercised. The "prior never overrides gate" seam is already regression-protected in the legacy test (left untouched) and referenced in the engine docstring. Jetpack / rich paths are not applicable here; the generic ledger-count path is proven live.
- **L4 (Realisierbarkeit / Edge):** All operations are pure Python + math (no external state, no NaN paths in the hot counters because engine Candidates are finite). Boundary ledger sizes (0, 1, many repeats), novel tokens, zero-exponent cands, and different smoothings are covered. The Hypothesis properties explore a slice of the count/smoothing space. No blanket guards were added because none were missing (the only "guard" is the documented `if n_pos and n_neg`).

Self-control notes:
- Read `src/gen/discovery/engine.py` (Candidate dataclass, candidate_from_exponents, _format_exponent, _render_expression) and `benchmark.py` (real cases) before writing any test data.
- Confirmed no new imports / no edits outside the three scoped files.
- Ran the exact characterization test in the worktree (`PYTHONPATH=src pytest ...`) — green before declaring done.
- Cross-checked against 2026-06-23 team decisions (new _characterization file, build via real ctors, hypothesis required, BUILD_LOG out of scope, edit source only on defect).
- 4-Linsen narrative written into this audit (not injected into BUILD_LOG to avoid merge collision per standing decision).

## Test Results (this task)

```
$ PYTHONPATH=src python3 -m pytest tests/test_concept_utility_characterization.py -q --tb=line
..........                                                               [100%]
10 passed in 2.79s
```

Full relevant discovery slice (including untouched legacy `test_concept_utility.py` + campaign + engine) stayed green in the worktree.

**Verdict stands: REAL** — the ledger-learned contrastive prior is genuine, deterministic, and correctly abstains when there is nothing to contrast.
