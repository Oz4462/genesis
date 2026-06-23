# Depth-Audit: `src/gen/discovery/active_resolution.py`

**Verdict: REAL.**

`propose_resolution` computes a genuine numpy divergence search over a bounded extrapolation grid. It is not a facade. The new `tests/test_active_resolution_characterization.py` proves input consumption and the honest non-discriminating path.

## Headline-Claim (from module + HORIZON / 6.4)

> After an ``unentschieden`` (two dimensionally-valid rivals fit equally well), the module emits a `DecisionSpec` for the measurement that would break the tie. The search is deterministic, LLM-free, uses real `|f_a - f_b|` on an extrapolated linspace grid, selects a *spread* (shape constraint, not single absorbable point), and only declares `discriminating=True` when peak divergence >= min_discrimination * noise floor inside the hard `max_extrapolation` bound. Otherwise: honest "mehr Daten im beobachteten Regime".

## Beweis (computed, not canned)

- Real constructors only: `DiscoveryProblem` / `Variable` / `Constant` (engine.py); `RivalForm` objects obtained exclusively via `discover_rivals(...)` + demonstrated `refit_rival` / `evaluate_rival` (transcendental.py). No invented fields.
- `DecisionSpec.measure_at`, `max_divergence`, `discrimination_ratio` change when the input data (hence rivals + observed range) changes — `test_decision_spec_fields_are_computed_not_canned` (different narrow-range samples produce different peaks and spreads).
- Barely-diverging case (max_extrapolation≈1.01 on the narrow exp-vs-pow regime) produces `discriminating=False` + the exact documented reason text containing "mehr Daten ... Regime sammeln".
- All four documented ValueError guards fire with their messages (None rival, >1 input, max_extrapolation<1.0, degenerate range). Negative test included.
- Property-based (Hypothesis): determinism (`s1 == s2` for identical input), extended_range brackets observed_range, finite outputs, live `evaluate_rival` path.
- Uses the real divergence math:
  ```python
  grid = np.linspace(ext_lo, ext_hi, n_grid)
  fa = evaluate_rival(rival_a, grid_problem)
  fb = evaluate_rival(rival_b, grid_problem)
  divergence = np.abs(fa - fb)
  ...
  ```

A constant-stub implementation would have failed the "changes when data changes" + property determinism + non-discrim reason assertions.

## Änderungen (scope-respecting)

- **`src/gen/discovery/active_resolution.py`**: **NO EDITS**. Guards, docstring, and numpy logic were already present and matched the documented contract exactly (L1 + L4). "change nothing if correct".
- **`tests/test_active_resolution_characterization.py`**: new file (authoritative signal). Uses only real pre-existing constructors/APIs + numpy/hypothesis/pytest (already declared). Does not touch legacy `test_discovery_active_resolution.py`.
- **`docs/audit/DEPTH_AUDIT_active_resolution.md`**: this file.

Legacy tests remain untouched (no churn). Isolation satisfied: task only touches its three scoped paths.

## Evidence vs. backlog

Satisfies the 2026-06-23 assigned task and the 6.4 active-resolution item in discovery/STATUS.md and GENESIS_PLATFORM_PLAN (active instrument after unentschieden; honest gate on extrapolation artefacts; T-optimality spirit via spread + robust sibling).

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** All numeric outputs (divergence, ratio, selected points) are derived from `evaluate_rival` on real fitted `RivalForm`s + np ops on the problem data. No hardcoded experiment. The 'mehr Daten' case is an explicit abstention, not a fabricated result. Matches "keine stillen Defaults".
- **L2 (Drift / Grounding):** Determinism asserted (identical inputs → identical `DecisionSpec`). No RNG, no LLM. Rivals obtained through the same transcendental path used by the rest of discovery. Cross-checked by property test + explicit change-detection.
- **L3 (Vollständigkeit / Naht):** Covers the core facade-risk surface (input consumption for the three headline numeric fields; honest non-discrim path; every documented guard). Ties the passive `discover_transcendental`/`unentschieden` verdict to an actionable next measurement. Jetpack-style rich paths (the spread + robust) are exercised indirectly via real call; the generic divergence path is proven live.
- **L4 (Realisierbarkeit / Edge):** Guards exactly as documented (no blanket NaN; only the four silent-wrong cases). Degenerate range, None rivals, wrong scope, and too-small extrapolation all fail loud. Barely-diverge inside bound correctly returns `discriminating=False`. Property test filters invalid (non-positive/degenerate) inputs per the engine convention.

No over-scope changes. No new dependencies. The characterization test is self-contained and passes using only its files + pre-existing repo modules.

## Test Results (this task)

```
$ python -m pytest tests/test_active_resolution_characterization.py -q --tb=line
<...> 8 passed
```

Full relevant discovery slice stayed green. No regression in legacy active-resolution tests (untouched).

Verdict stands: **REAL** — the active-resolution divergence search is genuine.
