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
- Follow-up round (rubber-duck review): covered + fixed remaining boundary gaps (see below).

## Changes made (only where genuine defect / facade)
- Implemented real RBF surrogate `build_surrogate` / `predict_surrogate` + `Surrogate` dataclass (numpy only).
- Updated module docstring to honestly describe BOTH roles and the shared "never confirms" contract.
- Added fail-loud guards + messages for prefilter/surrogate_score on n<2 and invalid sample_fraction (L4 edge; prevents numpy crash / silent k=2 on 1 pt).
- Stored owned .copy() snapshots in Surrogate; fixed docstring comment.
- No change to happy-path prefilter outputs / R² scores / ranking (legacy tests untouched + green).
- Added type hints, full docstrings with Raises, negative tests.

## Follow-up fixes (rubber-duck round 2 — all within surrogate module scope)
Review flagged remaining gaps in uniform "fails loud" contract:
- Hyperparam NaN (length_scale/reg) slipped past <=0 / <0 comparisons (NaN cmp == False) → now explicit `np.isfinite(...) or ...` before use.
- Ragged X to build/predict gave raw numpy "inhomogeneous" instead of documented ValueError → wrapped with clean message.
- discover_prefiltered delegated n<2 error (named "prefilter") → added explicit guard that names the called entrypoint.
- _subsample_problem (if called directly) could hit numpy error → added clean ValueError.
- Package re-exports (`from gen.discovery import build_surrogate ...`) were missing from __all__ + __getattr__ lazy (documented symbols not importable) → added (minimal registration).
- Data finite checks + hyper checks made uniform across prefilter, discover_*, build, predict.

All new cases have tests in the characterization file. No behavior change on valid inputs. Pre-existing prefilter paths untouched.

## 4 Linsen (applied, including follow-up)
- **L1 Truth:** All numeric claims (accuracy, beats baseline, unc monotonicity, determinism) backed by executable tests on known closed-form target. No unsourced facts.
- **L2 Drift:** Pre-existing prefilter unchanged for passing cases. New general surrogate is additive (orthogonal to discovery prefilter). Doc updated to match code. Guards close previous silent-failure path. Package exports now match documented public surface.
- **L3 Completeness/Seams:** New char test is authoritative (legacy left alone). API surface now has documented errors across *all* entrypoints. No new deps. Seams to engine kept (imports pre-existing). __init__ registration is the minimal exposure of the surrogate module's own public names.
- **L4 Realizability:** All guards tested (exact messages asserted), property tests, full pytest (legacy+new) green. Minimal, no blanket NaNs. Uncertainty contract makes extrapolation honest. Direct private helper also safe.

## Scope respect
Only edited files in declared scope + the package __init__ registration needed to make the surrogate module's documented names importable from the package (review finding). Full relevant pytest green. No impact on other discovery modules.
