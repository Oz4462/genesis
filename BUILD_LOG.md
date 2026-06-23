# BUILD_LOG

## T04 — Depth-audit + harden `separability.py` (additive/multiplicative separability)

**Verdict: REAL** — `analyze_separability` genuinely evaluates the mixed second difference
`y(++) − y(+−) − y(−+) + y(−−)` (and its `log y` form for multiplicative mode); the grouping is
computed from the per-pair residual, not canned.

- **Added** `tests/test_separability_characterization.py`: facade-killer proving (a) the grouping/
  `max_interaction` changes meaningfully when the function's coupling changes (additive→singletons,
  product→one group, partial `a·b+c` isolates `{a,b}` from `{c}`, magnitude scales with coupling
  strength), (b) the log path genuinely flips `a*b`'s verdict between modes (anchored to a hand-computed
  log corner sum), and (c) every documented guard raises. Includes Hypothesis property tests sweeping the
  coefficient/exponent space.
- **Fixed** `src/gen/discovery/separability.py`: two confirmed silent-wrong-value defects (no-silent-
  defaults). `n_bases < 1` skipped the sampling loop → fabricated "fully separable" (a coupled `a*b` read
  as separable); `tol < 0` → fabricated "all coupled" (a pure sum read as coupled). Both now raise
  `ValueError`; docstring updated. The only repo caller uses defaults, so legacy paths are unchanged.
- **Tests:** `tests/test_separability_characterization.py` + legacy `test_separability.py` +
  `test_engine_separability_annotation.py` → 28 passed. `test_discovery_engine.py` → 6 passed.
- Full audit + 4 Linsen in `docs/audit/DEPTH_AUDIT_separability.md`.
