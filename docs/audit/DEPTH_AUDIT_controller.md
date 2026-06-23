# Depth-Audit: `src/gen/discovery/controller.py`

**Verdict: REAL.**

The `ExplorationController` genuinely honours its three knobs (checkpoint/resume, budget, depth
tier). It is not a facade. The new `tests/test_controller_characterization.py` proves the
headline claims with driving-input change-detection, a Hypothesis equivalence property, and the
documented fail-loud guards. **No source edit was required** ("change nothing if correct").

## Headline-Claim (from module docstring / build doc §5 Phase 2 item 3)

> A long exploration is a CAMPAIGN of discovery problems run under three knobs:
> **BUDGET** (cap spent on the expensive tournament, never on the mandatory single-shot solve),
> **DEPTH TIERS** (`fast` / `medium` / `max` pick a coherent compute profile), and
> **CHECKPOINT / RESUME** (the DoD: a run checkpointed mid-campaign and resumed produces the
> IDENTICAL result as an uninterrupted run, because each problem is solved with its OWN seed
> `base_seed + index`, so an outcome never depends on campaign position or prior RNG state).

## Beweis (computed, not canned)

- **Real constructors only:** `DiscoveryProblem` / `Variable` / `Constant` (engine.py),
  `ExplorationController` / `ExplorationState` (controller.py). Deterministic Kepler (fully
  determined → tournament honestly skipped) + free-π (under-determined → tournament can improve)
  problems with explicit `run_id`s. No invented fields.
- **Checkpoint/Resume equivalence (the DoD):** `test_resume_equals_uninterrupted_run` proves a
  `checkpoint_after=2` split then `resume_from` yields a graph (sorted Anhang-C records), a
  `budget_spent`, and a completed set IDENTICAL to one uninterrupted run — and that the split
  genuinely deferred 2 problems. Reinforced by a **Hypothesis property**
  (`test_resume_equals_uninterrupted_property`) over every split point × {None,5,60,5000} budget ×
  {fast,medium,max} tier: resume is byte-identical to uninterrupted for ALL of them. JSON
  round-trip of the checkpoint is proven lossless (`test_resume_state_json_round_trips_losslessly`).
- **Budget changes output:** `test_generous_budget_on_max_spends_more_and_runs_the_tournament`
  shows tight (budget=10) → no tournament node, low spend; generous (budget=None) → tournament
  node present and strictly higher `budget_spent`. A stub ignoring the budget would spend the same.
- **Budget contract pinned precisely:** `test_budget_gates_only_the_tournament_not_the_mandatory_single_shot`
  characterizes the DOCUMENTED behaviour — the single-shot floor (6 evals here) is always paid even
  by a cap below it; the tournament portion (spend above the floor) never pushes spend over the
  budget. This catches both facades: a budget that silently gated single-shots (would defer problems)
  AND a tournament that ran away past the cap.
- **Depth tier changes output:** `test_tier_knob_drives_tournament_presence_and_cost` — `fast`
  records no tournament node and spends below one tournament's cost; `max` records a tournament and
  spends at least one full `generations*population` more.
- **Discovery is real:** `test_controller_really_runs_discovery_and_confirms_a_law` asserts the
  graph contains Kepler's confirmed (`bestaetigt`) power law with the dimensionally-forced exponents
  `a^3/2 · mu^-1/2` — proving real engine work, not an empty stub.

## Fail-loud guards (documented errors actually raise)

- Unknown tier → `ValueError("unknown tier …")` (`test_unknown_tier_raises_value_error`).
- `prioritize_by_information_gain` + `checkpoint_after` → `ValueError("… not supported with
  checkpoint/resume …")` (`test_prioritize_with_checkpoint_after_raises_value_error`).
- `prioritize_by_information_gain` + `resume_from` → same `ValueError`
  (`test_prioritize_with_resume_from_raises_value_error`).
- The InfoBAX guard is an honest *limitation*, not a dead feature: the single-pass prioritized path
  still completes every problem and confirms laws (`test_prioritize_single_pass_is_a_real_working_path`).

## Note on a discarded "defect"

An initial assertion `budget_spent <= cap` for *every* cap failed at `cap=5` (`spent=6`). On
inspection this is **not** a controller bug: the module's docstring and `ControllerResult`
docstring state explicitly that "a budget exhaustion does NOT defer a problem — it only skips its
expensive tournament; the problem still completes on the single-shot solve". The mandatory
single-shot floor is intentionally outside the cap. The test was corrected to assert the real,
documented contract instead of an invariant the module never promises. No source change made.

## Änderungen (scope-respecting)

- **`src/gen/discovery/controller.py`**: **NO EDITS** (verdict REAL — knobs, accounting, guards
  already correct and matched the documented contract; L1 + L4).
- **`tests/test_controller_characterization.py`**: new authoritative facade-detector. Uses only
  real pre-existing constructors/APIs + numpy/hypothesis/pytest (already declared deps). Does not
  touch the legacy `test_discovery_controller.py` / `test_controller_active_search.py` /
  `test_controller_archive.py`.
- **`docs/audit/DEPTH_AUDIT_controller.md`**: this file.

Isolation satisfied: task touches only its three scoped paths. BUILD_LOG.md deliberately untouched
(per the standing team decision to avoid a shared-file merge collision).

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** Every controller output is derived from the real engine
  (`discover_new_formulas`) + tournament (`evolve`) + dedup graph. No hardcoded result. Confirmed
  Kepler exponents asserted against the dimensionally-forced values — provenance is genuine.
- **L2 (Drift / Grounding):** Determinism is the load-bearing invariant; proven both by example and
  by a property over many split/budget/tier combinations. Each problem's seed is `base_seed + index`,
  so resume reproduces the exact spend trajectory and RNG state — no campaign-position dependence.
- **L3 (Vollständigkeit / Naht):** Covers all three knobs plus the discovery sanity floor and the
  three documented guards. The checkpoint seam (deferred set, JSON round-trip, resume==uninterrupted)
  is exercised directly. The InfoBAX single-pass path is proven live so the guard is shown to be a
  limitation, not a removed feature.
- **L4 (Realisierbarkeit / Edge):** Guards fire exactly as documented; the budget-floor edge (cap
  below the mandatory single-shot floor) is pinned to the honest documented behaviour rather than a
  fabricated over-strict bound; every problem completes regardless of cap.

No over-scope changes. No new dependencies. The characterization test is self-contained and passes
using only its file + pre-existing repo modules.

## Test Results (this task)

```
$ PYTHONPATH=src python3 -m pytest tests/test_controller_characterization.py -q
12 passed

$ PYTHONPATH=src python3 -m pytest tests/test_discovery_controller.py \
    tests/test_controller_active_search.py tests/test_controller_archive.py \
    tests/test_controller_characterization.py -q
24 passed
```

Legacy controller tests stayed green (untouched). Verdict stands: **REAL** — the budget/depth/
checkpoint controller genuinely honours all three knobs.
