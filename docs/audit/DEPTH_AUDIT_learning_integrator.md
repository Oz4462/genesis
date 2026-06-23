# Depth Audit — `src/gen/grenzverschiebung/learning_integrator.py` (`apply_learning_cycle`)

**Task:** T01 — make the generic LearningDelta genuinely derive from the real
SafetyStagePlan / RevisedFrontMap (kill the canned generic stub).

**Verdict:** **PARTIAL-FACADE (generic else returned one fixed LearningRule, ignoring input) → REAL (input-driven generic path + honest abstention + fail-loud).**

## What was genuinely real before
- The dataclasses (`LearningRule`, `FailureMode`, `WissensEintrag`, `LearningDelta`) and their fields were real and well-typed.
- The **jetpack branch** (`"jetpack" in traum` / `"mensch"+"fliegen"`) produced a rich, hand-authored 8-step delta (3 rules, 2 failure-modes, 2 knowledge entries, 4 proposals). This is genuine demo content and is kept verbatim.
- `run_id` / `quelle` provenance fields existed for A5 reproducibility.

## Facade found and fixed (only in learning_integrator.py)
1. **Hollow generic `else` branch.** Regardless of `safety.stages`, `revised`, or `source_traum`, the non-jetpack path returned exactly **one fixed `LearningRule`**, an empty failures/wissens list, and one canned proposal. Two different non-jetpack inputs produced byte-identical rules — the headline claim ("zieht aus jedem Test neue Regeln/Failure-Modes") was false for every non-jetpack input. Violates "keine stillen Defaults", L2-drift, and PLATFORM_PLAN §3.3/§3.8.
   **Fix:** the generic path now iterates `safety.stages`:
   - one `LearningRule` per real `SafetyStage` (its `gate` is the learned invariant; `name`/`gate`/`safe_form` referenced; `messkriterien` as evidence; `stage.quelle` as provenance), and
   - one `FailureMode` per `abbruch` criterion of that stage (`aus_stufe = stage.name`, gate cited).
   - a `WissensEintrag` summarising the real plan, plus an input-derived improvement proposal.
2. **Silent `"unbekannt"` fabrication when both inputs are None.** Previously `traum` silently fell back to the string `"unbekannt"` and emitted the canned generic rule out of nothing.
   **Fix:** `apply_learning_cycle()` now raises `ValueError` when `safety is None and revised is None` (documented in the docstring) — fail loud, no fabricated content.
3. **No honest abstention.** A signal-free input (SafetyStagePlan with zero stages, or `revised` with zero revisions) still produced a fabricated rule.
   **Fix:** such inputs now yield an empty `rules`/`failure_modes` list plus an explicit `LÜCKE:` marker in `naechste_verbesserungsvorschlaege` and the summary — "Ich weiß es nicht" als gültiger Output (Kernprinzip 4).
4. **`revised`-only path was dead.** When only `revised` was supplied (non-jetpack), the old code still emitted the same canned rule.
   **Fix:** new `elif revised is not None and revised.revisions:` derives one rule per real `BoundaryRevision` (`changed_boundary`, `old_typ → new_typ`, `reason` as evidence, `quelle` carried).

The jetpack rich branch is **unchanged** (protected regression test asserts 3 rules incl. Solid-State, 2 failure-modes, 2 knowledge entries, 4 proposals).

## Evidence (new test: `tests/test_learning_integrator_characterization.py`)
8 tests + 1 hypothesis property test, all green (10/10 incl. the 2 untouched legacy tests):
- `test_two_different_safety_plans_yield_different_deltas` — **facade-killer**: two distinct non-jetpack plans → different rule texts and counts (input is consumed).
- `test_generic_derives_one_rule_per_stage_and_failure_per_abbruch` — provenance check: stage name/gate appear in the derived rule; one failure per abbruch criterion; knowledge entry summarises the plan.
- `test_both_none_raises_valueerror` — fail-loud guard.
- `test_safety_without_stages_and_no_revised_honest_abstention` — empty rules + `LÜCKE` marker, no fabrication.
- `test_only_revised_derives_from_revisions` / `test_only_revised_without_revisions_honest_abstention` — revised-only derivation + its abstention path.
- `test_jetpack_rich_branch_preserved_as_regression` — protected jetpack regression.
- `test_property_rule_and_failure_counts_match_input` — `@given` invariant: `#rules == #stages` and `#failure_modes == Σ len(abbruch)` for arbitrary non-jetpack plans.

Run (in this worktree):
```
PYTHONPATH=src python3 -m pytest tests/test_learning_integrator_characterization.py tests/test_learning_integrator.py -q
```

## 4 Linsen
- **L1 — Wahrheit:** every generic rule/failure now carries the real stage `name`/`gate`/`quelle` as evidence/provenance; nothing is invented. Signal-free input abstains instead of asserting.
- **L2 — Drift/Grounding:** the unconditional canned rule (the L2 violation) is removed; the generic output is now a pure function of `safety.stages` / `revised.revisions`. Jetpack observable output is byte-stable.
- **L3 — Vollständigkeit/Naht:** all documented `LearningDelta` fields are still emitted; the jetpack seam to downstream consumers is regression-protected; legacy `tests/test_learning_integrator.py` left untouched and still passes (the generic summary retains "minimal").
- **L4 — Realisierbarkeit/Verifizierbarkeit:** new test is self-contained (stdlib + hypothesis, both already declared), deterministic, and exercises happy path, both abstention paths, and the fail-loud guard; a property test pins the count invariant.

## Backlog alignment (GENESIS_PLATFORM_PLAN.md §3.3 + §3.8)
Satisfies the §3.3 contract that the learning_integrator "zieht aus jedem Test neue Regeln, Failure-Modes und Wissenseinträge" for arbitrary (not just the canned jetpack) inputs. The full Wissensbasis write-back and live multi-cycle feeding remain future work, as documented in the module header.

## Remainder / out of scope
- No edits outside the three declared paths; `BUILD_LOG.md` deliberately untouched (per 2026-06-23 team decision — this audit doc is the per-module record).
- No new dependency; jetpack branch and all public dataclass signatures byte-stable so downstream importers keep compiling and the full pytest gate stays green (101 related tests + 10 in-scope tests pass).
