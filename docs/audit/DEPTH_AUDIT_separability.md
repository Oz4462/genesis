# Depth Audit — `src/gen/discovery/separability.py`

**Task:** T04 — Depth-audit + harden additive/multiplicative separability.
**Verdict:** **REAL** (with two genuine silent-wrong-value guards added — see Fix).

## What the module claims

AI-Feynman's separability move: before fitting one hard law, test whether the target DECOMPOSES into
independent blocks — `y = g(A) + h(B)` (additive) or `y = g(A)·h(B)` (multiplicative) — so each block is a
simpler problem for the power-law engine. The headline mechanism is the **mixed second difference**
`y(++) − y(+−) − y(−+) + y(−−)`: for an additive target it vanishes across a block boundary
(`∂²y/∂xᵢ∂xⱼ = 0`); multiplicative separability is the SAME test on `log y`. Interacting pairs are unioned
into connected components (groups that must stay together).

## Is the math real, or a canned grouping?

REAL. The characterization test (`tests/test_separability_characterization.py`) proves it three ways:

1. **Input-driven grouping (facade-killer a).** With identical variables, ranges and mode, only the
   *function's coupling* differs and the grouping flips: `a+b` → singletons (`max_interaction == 0.0`),
   `a*b` → one group (`max_interaction > 0`). A canned result could not track this. Partial coupling
   `a·b + c` isolates `{a,b}` from `{c}`; `a·b·c` collapses to a single 3-var group; an unused variable
   splits off — so the connected-component union-find genuinely partitions on the per-pair residual.
2. **The log path is genuinely applied.** The SAME `a*b` is COUPLED under additive mode but SEPARABLE
   under multiplicative mode (opposite verdict, same `f`) — proving the `log` transform changes the
   computation, not a label. Anchored against an independent hand-computed log corner sum
   (`log(a·b)` corners cancel to 0; `log(a+b)` corners do not).
3. **Magnitude is computed.** `max_interaction` scales strictly with coupling strength
   (`1e-3·a·b` < `1.0·a·b`), and property-based tests (Hypothesis) sweep the coefficient/exponent space:
   any `ca·a + cb·b` separates, any added `k·a·b` couples, any positive monomial `a^p·b^q` factors under
   multiplicative mode.

## Fix (genuine defects found)

Two **silent-wrong-value** defects (violating "keine stillen Defaults bei faktischen Dingen — lieber
Exception als geratener Wert") were confirmed empirically and fixed with fail-loud guards in
`analyze_separability`:

- **`n_bases < 1`** → the sampling loop never runs, the mixed difference is never evaluated, and EVERY
  pair is reported separable. A genuinely coupled `a*b` came back as "fully separable" — a fabricated
  verdict. Now raises `ValueError`.
- **`tol < 0`** → a non-negative relative interaction can never satisfy `interaction <= tol`, so EVERY
  pair is reported coupled. A pure sum `a+b` came back as "coupled" — a fabricated verdict. Now raises
  `ValueError`.

Both are covered by negative regression tests. No other behavior changed; the docstring now documents the
new error cases. The only in-repo caller (`engine.discover_new_formulas`) uses the defaults, so the
guards never trip on the existing path — legacy `test_separability.py` and
`test_engine_separability_annotation.py` stay byte-for-byte green.

## 4 Linsen (L1–L4)

- **L1 (Wahrheit):** Every grouping/`max_interaction` is derived from the actual corner sum on the
  queried `f` (or `log f`). No hardcoded grouping. Abstention is honest: out-of-domain multiplicative
  targets and the two new degenerate-parameter cases fail loud instead of emitting a guessed verdict.
- **L2 (Drift):** Determinism asserted (identical inputs → identical groups AND `max_interaction`); the
  seeded `np.random.default_rng` base sampling is reproducible. The mode genuinely switches the math
  (additive vs log), cross-checked by opposite verdicts on the same `f`.
- **L3 (Vollständigkeit/Naht):** Covers the full facade surface — singletons, full coupling, partial
  coupling, ignored variable, magnitude ordering, the log path vs additive path, and every documented
  guard. Ties into the engine annotation seam (legacy test unchanged).
- **L4 (Realisierbarkeit/Edge):** No blanket NaN/inf creep — only the two real silent-wrong cases
  (`n_bases < 1`, `tol < 0`) plus the pre-existing mode/positivity guards. Boundary `interaction <= tol`
  semantics preserved.

No over-scope changes. No new dependencies (numpy + hypothesis already declared). Self-contained: the test
passes using only its own files plus pre-existing repo modules.
