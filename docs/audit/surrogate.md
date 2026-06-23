# Audit: `src/gen/discovery/surrogate.py`

**Task:** T03 — Depth-audit + fix of discovery surrogate (prefilter + general function approximator)

**Verdict: REAL** (after adding genuine surrogate training/prediction; prefilter guards added for edge honesty; pre-existing prefilter behavior preserved).

## Headline claim audited
"A surrogate that approximates an expensive physics/objective function with quantifiable accuracy" + the original "cheap prefilter that ranks but never confirms".

## Evidence from characterization test (`tests/discovery/test_surrogate_characterization.py`)
- 10 tests (incl. 3 Hypothesis property-based).
- Train on samples of known f (sin+quadratic), held-out RMSE << bound AND >>0.2 better than constant-mean baseline.
- Uncertainty grows monotonically with distance; far extrapolation yields high unc (not overconfident).
- Negative: <2 points, bad sample_fraction, non-finite, dim-mismatch, non-Surrogate all raise exact documented ValueErrors.
- Property: reconstruction error << data std (input consumed); same input -> identical output (determinism).
- Prefilter path now has explicit negative tests + guards for n<2 / bad fraction (was missing per review).

## Changes made (only where genuine defect / facade)
- Implemented real RBF surrogate `build_surrogate` / `predict_surrogate` + `Surrogate` dataclass (numpy only).
- Updated module docstring to honestly describe BOTH roles and the shared "never confirms" contract.
- Added fail-loud guards + messages for prefilter/surrogate_score on n<2 and invalid sample_fraction (L4 edge; prevents numpy crash / silent k=2 on 1 pt).
- Stored owned .copy() snapshots in Surrogate; fixed docstring comment.
- No change to happy-path prefilter outputs / R² scores / ranking (legacy tests untouched + green).
- Added type hints, full docstrings with Raises, negative tests.

## 4 Linsen (applied)
- **L1 Truth:** All numeric claims (accuracy, beats baseline, unc monotonicity, determinism) backed by executable tests on known closed-form target. No unsourced facts.
- **L2 Drift:** Pre-existing prefilter unchanged for passing cases. New general surrogate is additive (orthogonal to discovery prefilter). Doc updated to match code. Guards close previous silent-failure path.
- **L3 Completeness/Seams:** New char test is authoritative (legacy left alone). API surface now has documented errors. No new deps. Seams to engine kept (imports pre-existing).
- **L4 Realizability:** All guards tested (exact messages asserted), property tests, full pytest (legacy+new) green. Minimal, no blanket NaNs. Uncertainty contract makes extrapolation honest.

## Scope respect
Only edited files in declared scope. Full relevant pytest green. No impact on other discovery modules.
