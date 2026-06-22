# Depth Audit — `src/gen/inventor/loop.py` (γ+ bridge)

**Task:** T03 — *inventor loop: make γ+ bridge derive + attach to RunState*
**Verdict:** **PARTIAL-FACADE → REAL** (one genuine defect found + fixed; the rest was already real)
**Test:** `tests/test_inventor_loop_characterization.py` (9 example/property tests, all green)
**Source edit:** `src/gen/inventor/loop.py` only.

## Headline claim under audit

`run_invention` claims to *genuinely run the γ+ inverse-design bridge in-loop* on the
δ-grounded specification: `derive_goal_from_spec` → `build_pareto_front` → `gate_gamma_plus`,
producing a `ParetoFront` that is set on the result and attached to a passed `RunState`.

## What was genuinely REAL before the fix (evidence)

- **The derived goal is computed from the live spec, not canned.** `derive_goal_from_spec`
  reads the grounded `Specification.quantities`; the goal id is `f"inv-gp-{brief.run_id}"`
  and the objectives carry the spec's REAL `quantity_id`s (`q_excite`, `q_fn`), never the
  legacy proxy `"performance"` axis.
  - *Input-sensitivity proven two ways*: changing `run_id` changes `goal.id`
    (`test_goal_id_tracks_run_id_input_sensitivity`); a custom architect that renames its
    quantity ids makes the derived objectives track them
    (`test_objectives_track_spec_quantities_input_sensitivity` → `{q_eigen, q_drive}`).
  - *Property invariant*: for any goal id, the derived goal echoes it verbatim and every
    `objective.quantity_id` is one the spec actually carries — never invented
    (`test_property_derive_goal_id_roundtrip_and_qids_subset_of_spec`, 60 Hypothesis cases).
- **`build_pareto_front` + `gate_gamma_plus` are exercised without crashing** and
  `result.pareto_front` is set.
- **The fail-loud guard is real, not a rubber stamp.** An objective referencing a quantity
  absent from the spec raises `ObjectiveEvaluationError` rather than inventing a value
  (`test_gamma_plus_objective_evaluation_fails_loud_on_missing_quantity`).
- **The M1 proxy 5-axis front still works** (`pareto_inventions`), additively — the bridge
  did not break back-compat (`test_proxy_five_axis_front_still_works_backcompat`).

## The genuine defect (the facade seam)

The attach to `RunState` was gated:

```python
if (pf.evaluated_candidates or pf.candidates):   # conditional only if evaluated >0
    state.pareto_front = pf
```

In the real inventor flow this branch **never fires**. `build_pareto_front` re-validates each
candidate through the FULL `gate_gamma` (C-1…C-18), which requires the spec's grounded
quantities to reference **VERIFIED claims present in the run ledger**. The inventor grounds via
prior-art search + the δ-physics gate; it never registers skeptic-verified `Claim`s for those
grounding ids into the `RunState`. So every candidate is rejected with
`VALUE_UNKNOWN_CLAIM`, `pf.evaluated_candidates` is always empty, and `state.pareto_front`
stayed `None` forever. The bridge computed a real goal but **silently dropped** its own output —
a partial facade. (The pre-existing legacy test `test_inventor_loop.py::test_gamma_plus_bridge_…`
was in fact RED on `main` for exactly this reason.)

## The fix (honest, minimal, `loop.py`-only)

Attach the real `ParetoFront` to the `RunState` **unconditionally** when `state` is passed. An
empty front here is an **honest abstention**, and its `gaps` carry the reason (the δ-grounded
spec is not γ-complete because its prior-art claims were never skeptic-verified). The honest log
line records `evaluated`/`front`/`gaps` counts.

**Why not force `evaluated>0`?** The only way to make the full γ gate pass would be to fabricate
`VERIFIED` claims whose text contains the quantity values — manufacturing evidence. That violates
GENESIS core principle #1 (*kein faktischer Output ohne Quelle*). Surfacing the abstention is the
correct behavior; hiding the front was the bug. (Real callers that pass a γ-complete `RunState`
with a verified ledger still get `evaluated>0` — the bridge already supports that path via
`rs = state or RunState(...)`.)

## Backlog item

Satisfies the HORIZON γ+ "inverse design as a validated Pareto front" integration for the
inventor arm (`docs/HORIZON.md` §γ+): the inventor now genuinely derives a real inverse-design
goal from its δ-grounded spec and surfaces the validated (or honestly abstaining) front on the
run state. **Open remainder** (out of scope, documented not silently dropped): the inventor does
not yet emit a γ-complete, skeptic-verified claim ledger, so `evaluated_candidates` is empty in
the offline scripted flow — closing that requires wiring the cross-model skeptic into the
inventor grounding path, not a change in `loop.py`.

## 4 Linsen

- **L1 Wahrheit:** the attached front reports its abstention honestly via `gaps`; no fabricated
  candidates, no invented qids (property-checked).
- **L2 Drift:** docstrings/comments updated to match the new always-attach contract (the old
  "conditional on evaluated>0 (CRITICAL)" wording was the drift that hid the bug).
- **L3 Vollständigkeit/Naht:** the result-side `pareto_front` and the state-side `pareto_front`
  are now the SAME object (`state.pareto_front is result.pareto_front`) — the seam is closed.
- **L4 Realisierbarkeit:** change is `state`-gated, so CLI/web/eval callers (which pass no
  `state=`) are byte-for-byte unaffected; full inventor + γ+ suites green (78 passed).
