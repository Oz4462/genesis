# Depth-Audit: `gen.discovery.symbolic_search`

**Verdict: REAL** — genuine genetic-programming symbolic-regression search, not a facade.
No behavioural source change was required; only a docstring note was added.

## Headline claim
The module "searches a space of symbolic expressions and returns the expression that fits the
data — genuine search/optimization, not a lookup." It is the open-form (additive / transcendental)
proposer the roadmap calls for, complementing the narrow power-law `engine.py`.

## What the characterization test proves
`tests/discovery/test_symbolic_search_characterization.py` (9 tests, all green):

1. **Rediscovery (facade-killer).** Data from the KNOWN closed form `y = 3·sin(x) + 2` — a
   transcendental law `engine.py` provably cannot represent — is recovered with the correct
   structure (`sin(x)`), the correct affine coefficients (`a = 3`, `b = 2` within `1e-3`), and
   **R² ≈ 1 on fresh out-of-sample points** the search never saw. A lookup/hardcoded guess cannot
   produce this.
2. **Real search progress.** With a deliberately small population (8) the initial random
   generation cannot already contain the answer. Over `y = x²` on a symmetric range a single
   generation gives R² < 0.9 while 60 generations reach R² ≈ 1 — a strict, substantial
   improvement. A separate test pins the fitness trajectory as **monotone non-decreasing** across
   a 1→60 generation sweep (elitism + fixed RNG order), the opposite of a flat hardcoded line.
3. **Honest abstention (negative).** Pure Gaussian noise against an irrelevant input is NOT
   confirmed: the out-of-sample hygiene gate collapses, so the verdict is `unentschieden`
   (`passed == False`, `generalises == False`) — never an over-fit `bestaetigt` (Kernprinzip 4).
4. **Fail-loud (negative).** Empty target, mismatched column length, and zero input columns each
   raise the documented `ValueError` rather than silently returning a fabricated model
   (keine stillen Defaults).
5. **Determinism (property, Hypothesis).** Same seed + same data → byte-identical expression and
   fitness across 25 random seeds (Kernprinzip 5). A second property test confirms arbitrary
   affine laws `y = a·x + b` are recovered to R² ≈ 1.

## 4 Linsen
- **L1 Wahrheit:** every assertion checks real numeric/structural behaviour (recovered structure,
  coefficients, out-of-sample R², ValueError messages) — no `assert True`.
- **L2 Drift:** the negative noise + fail-loud tests guard against silent fabrication; verdict
  strings asserted exactly.
- **L3 Vollständigkeit/Naht:** happy path (rediscovery, progress, determinism) AND every documented
  failure path (noise abstention, three ValueError cases) are covered; the affine refit seam to
  `engine.py`'s power-law arm is respected (this module only widens the candidate space, the gate
  stays the authority).
- **L4 Realisierbarkeit:** runs offline, numpy-only, ~5 s; small populations keep the GP tractable
  in CI; Hypothesis examples bounded with no deadline for determinism.

## Backlog alignment
Satisfies the open-form / transcendental-coupling proposer item in the discovery backlog
(`GENESIS_PLATFORM_PLAN.md` Grenzverschiebungs / Universe-Explorer frontier): a deterministic GP
breadth source gated by the existing FIT + dummy-exclusion + out-of-sample honesty discipline.
Open frontier (out of this task's scope): multiplicative/transcendental constant search by
gradient rather than GP mutation.
