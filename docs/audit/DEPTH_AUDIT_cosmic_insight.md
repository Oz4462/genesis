# Depth-Audit: `src/gen/discovery/cosmic_insight.py`

**Verdict: REAL.** No source defect found; no source edits made ("change nothing if correct").

The Cosmic Insight Engine genuinely detects cross-domain structural analogies by abstracting
away variable names and units and clustering CONFIRMED graph nodes by the multiset of their
exponents. It is not a facade. The new `tests/test_cosmic_insight_characterization.py` proves
the headline claim by asserting that outputs change with the driving inputs (the graph's
confirmed laws and their domains) and that the documented fail-loud path raises.

## Headline-Claim (from module + build doc 4.1)

> `structural_signature` reduces a law to the sorted multiset of its non-zero exponents (the
> *shape*), so Newton `{m1:1,m2:1,r:-2,G:1}` and Coulomb `{q1:1,q2:1,r:-2,k:1}` map to the
> identical `(-2,1,1,1)`. `find_analogies` reports a shared shape ONLY when ≥`min_members`
> confirmed laws span ≥2 distinct ideas (domains). `cross_domain_hypotheses` surfaces a hint
> only for a confirmed law from a DIFFERENT domain than the target, never confirming a law,
> and fails loud (ValueError, via the engine) on empty/bad target data.

## Beweis (computed, not canned)

- **Real construction path only.** Confirmed nodes are built through
  `discover_new_formulas(problem)` → `graph.add_result(..., target_name=...)`; a node only
  reaches `graph.confirmed()` if it actually passed the discovery gate (verdict
  `bestaetigt`). `DiscoveryProblem` / `Variable` / `Constant` come from the real engine
  constructors; the same-domain variants are produced via `dataclasses.replace(problem,
  idea=...)`. No node is hand-forged into the confirmed bucket.
- **(1) Signature abstracts names + units.** Newton and Coulomb shapes (different names/units)
  collapse to the same `(-2,1,1,1)`; Kepler's `(-0.5,1.5)` is a *different* tuple — the
  signature tracks the actual exponents, it is not a constant. Near-zero exponents are
  dropped. A **Hypothesis** property test pins the core invariant the whole engine rests on:
  the signature depends only on the multiset of (rounded, non-near-zero) exponent VALUES,
  never on the names or insertion order, and is sorted.
- **(2) Cross-domain requirement is real, not just a member count.**
  `test_no_analogy_for_two_laws_in_the_SAME_domain` builds two structurally-identical
  `(-2,1,1,1)` laws (distinct variable names → distinct nodes) under the SAME idea and asserts
  **no** analogy — sanity-checking first that both really confirmed, share one shape, and sit
  in one domain. A member-only stub would falsely report a bridge here. Driving-input check:
  one domain → `[]`, the same graph plus a second domain of the same shape → one analogy.
  `min_members` is exercised as a real knob (bridge at 2, none at 3).
- **(3) Hypotheses only cross domains, fail loud on bad data.** A known gravity law + a new
  electrostatics target → one hypothesis pointing at the OTHER domain; the SAME idea on both
  sides → `[]` (the same-idea `continue` guard); a non-matching shape → `[]` (no fabricated
  bridge). Empty target data and a non-positive target magnitude each raise `ValueError`
  through `symbolic_regress` — the documented negative path.

A constant-stub implementation would have failed the "changes when domain/shape/min_members
changes" assertions, the same-domain facade killers, and the property-based invariant.

## Änderungen (scope-respecting)

- **`src/gen/discovery/cosmic_insight.py`**: **NO EDITS**. The signature math, the
  `len(nodes) >= min_members and len(domains) >= 2` gate, the same-idea `continue`, and the
  ValueError-via-engine path already match the documented contract exactly (L1 + L4).
- **`tests/test_cosmic_insight_characterization.py`**: new authoritative facade-detector.
  Uses only real pre-existing constructors/APIs + numpy/hypothesis/pytest (all already
  declared deps). Leaves the legacy `test_discovery_cosmic_insight.py` untouched (no churn).
- **`docs/audit/DEPTH_AUDIT_cosmic_insight.md`**: this file.

## 4 Linsen

- **L1 (Wahrheit):** every confirmed node is gate-verified; the engine reads only
  `confirmed()`, so an analogy is built on verified laws, not speculation. Tests assert the
  real verdict bucket, not a mock.
- **L2 (Drift):** no silent defaults — bad target data raises rather than returning a guessed
  candidate; a non-matching shape returns an honest empty list.
- **L3 (Vollständigkeit/Naht):** the new file complements, not replaces, the legacy test; the
  cross-domain seam (signature → cluster → domain split → hypothesis) is covered end to end.
- **L4 (Realisierbarkeit):** all inputs constructed via real signatures; tests run offline,
  deterministic (Hypothesis seeded by default), no network/subprocess.

## Evidence vs. backlog

Satisfies the 2026-06-23 assigned task (T05) and the Cosmic-Insight / cross-domain-analogy
item (build doc 4.1) in the discovery STATUS / GENESIS_PLATFORM_PLAN: an honest transfer layer
that PROPOSES cross-domain bridges from verified laws and never confirms one itself.

## Run

```
PYTHONPATH=src python3 -m pytest tests/test_cosmic_insight_characterization.py -q
# 14 passed
```
