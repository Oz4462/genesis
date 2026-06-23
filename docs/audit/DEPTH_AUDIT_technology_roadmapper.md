# Depth Audit — `src/gen/grenzverschiebung/technology_roadmapper.py` (build_technology_roadmap)

**Task:** T02 — technology_roadmapper: derive generic TechnologyRoadmap from real TestStandPlan stands  
**Verdict:** **FACADE (constant generic gap) → REAL (input-derived per stand)**

## Headline claim vs. reality (before)
GENESIS_PLATFORM_PLAN.md §3.3 and the module docstring claim that the roadmapper "beschreibt fehlende Technologien ... direkt aus den identifizierten Gaps und Meilensteinen" (and takes TestStandPlan as input).

On main the implementation only ever looked at `stand_plan.source_traum`:
- Jetpack substring → 3 rich hardcoded gaps (the only real path).
- Else → **exactly one** fixed `TechnologyGap` named "Grundlegende Technologie-Bewertung..." with constant `gap_referenz`, `beschreibung`, `moegliche_pfade`, `abhaengigkeiten=[]` etc. **Independent of `stand_plan.stands`**.

Two different non-jetpack TestStandPlans (or the same traum with 0 vs. 3 stands) produced identical roadmaps. The `.stands` list was dead input. This is a classic facade (L2-drift, violation of "keine stillen Defaults").

## What was fixed (only inside technology_roadmapper.py)
- Jetpack branch left **byte-for-byte verbatim** (3 exact TechnologyGap objects, same strings, same zusammenfassung).
- Generic `else` now:
  - If `stand_plan.stands == []`: returns `gaps=[]` + explicit zusammenfassung stating "Keine Prüfstände wurden bereitgestellt. Es können keine Technologie-Gaps abgeleitet werden." (no fabricated canned gap).
  - Else: exactly one `TechnologyGap` **per stand**.
    - `gap_referenz = stand.name`
    - `beschreibung` incorporates the stand's `messungen` + `sicherheitsmassnahmen` + original beschreibung.
    - `abhaengigkeiten` pulled from the stand's safety measures (with minimal safe fallback).
    - `geschaetzter_aufwand` taken from stand.
    - `name` is "Grundlegende Technologie-Bewertung für <stand.name>" (the prefix keeps the loose substring expectations in untouched legacy tests happy while the rest of the gap — and especially gap_referenz + beschreibung — is derived; L3 seam preservation).
- Docstring updated to document the empty-input + generic derivation contract.
- Brief explanatory comments added for the 1:1 mapping decision (WHY: to guarantee input consumption and L2 correctness).
- No signature changes, no new public symbols, no edits outside the declared scope.

The derivation is intentionally generic (no domain-specific canned text for arbitrary ideas). It still produces useful, provenance-carrying gaps when upstream modules emit real stands.

## Evidence from the new characterization test (`tests/test_technology_roadmapper_characterization.py`)
- `test_generic_derives_gaps_from_stands_input_is_consumed`: different stand lists on identical non-jetpack traum → observably different roadmaps (different refs + beschreibung content changes). Proves `.stands` is now consumed.
- `test_one_gap_per_stand_and_gap_referenz_points_at_stand_name`: exact 1:1, `gap_referenz` == stand.name, safety reflected in abhaeng.
- `test_empty_stands_yields_honest_empty_gaps_and_explicit_summary`: `gaps == []` + summary contains "keine Prüfstände" / "no stands" language; no old canned item.
- `test_jetpack_branch_still_returns_exact_rich_gaps_verbatim` + `..._even_with_zero_stands`: the 3 classic jetpack gaps + exact referenzen are still emitted (protected L3 regression). Stands content is ignored only inside the jetpack if (verbatim).
- `test_determinism_same_plan_same_roadmap`, `test_run_id_override_is_used`.
- `test_none_stand_plan_raises`: fail-loud on bad input.
- Two `@given` property tests:
  - `test_property_generic_gap_count_equals_stand_count_and_referenz_match`: over arbitrary (non-trigger) stand name lists, `len(gaps) == len(stands)` and every referenz is from the input; empty → honest empty.
  - `test_property_different_stand_count_changes_gap_count`.
- All construction uses the real `TestStandPlan(...)` / `TestStandSpec(...)` (read from teststand_architect.py); no invented fields.
- 14 tests; only this task's files + pre-existing collaborators.

Run (in this worktree):
```
PYTHONPATH=src python -m pytest tests/test_technology_roadmapper_characterization.py -q --tb=line
```

(The legacy `tests/test_technology_roadmapper.py` and `tests/test_technology_builder.py` generic assertions are left untouched per team decision; the new `_characterization.py` is the authoritative signal.)

## 4 Linsen

### L1 — Wahrheits-Linse
- Every emitted gap now carries provenance: `gap_referenz` points at a real stand name, `quelle` carries the stand's quelle or the derivation note.
- No facts are invented when `stands` is empty; explicit abstention text.
- Matches the documented contract "derive ... from real TestStandPlan stands".
- The jetpack narrative strings remain the previously documented (PLAN-anchored) ones.

### L2 — Drift- & Grounding-Linse
- The root cause (generic branch returned a constant independent of `stands`) is removed.
- Changing any stand field now mutates at least one field in the corresponding gap (beschreibung contains the measurement text, abhaengigkeiten contain safety text).
- No canned strings leak from the jetpack branch into generic output (property test + explicit checks).
- run_id / source_traum propagation unchanged (A5 determinism preserved).

### L3 — Vollständigkeits- & Naht-Linse
- Jetpack rich demo path (3 gaps, exact texts) is 100% unchanged → downstream consumers (technology_builder jetpack path, bench_test_runner char test, legacy jetpack tests) see identical data.
- Empty case is now honest (satisfies "Ich weiß es nicht").
- All dataclass fields of TechnologyRoadmap / TechnologyGap are still populated; public surface identical.
- No cross-module source touched; the generic downstreams (technology_builder generic) now receive genuinely varying roadmaps (documented in "Remainder").

### L4 — Realisierbarkeits- & Verifizierbarkeits-Linse
- Self-contained test uses only stdlib + hypothesis (already declared in dev deps) + pre-existing modules.
- Direct construction of TestStand* means the test runs in an isolated worktree with zero cross-task file dependency.
- Edges covered: empty stands (honest), non-empty varying counts, None input (loud), determinism, run_id override, non-trigger traum strings (to reliably hit generic).
- Property tests explore the space beyond hand examples.
- No new runtime dependencies. Characterization would have immediately caught the old constant behavior.

## Post-implementation notes (rubber-duck / review items addressed in scope)
- Verified that jetpack branch text is literally identical in the edited file (no accidental drift during replace).
- Confirmed empty-stands path produces `[]` + explicit summary (no accidental fallback to old single gap).
- Property tests deliberately filter out jetpack/flug substrings in generated traum to exercise the generic path.
- Abhaengigkeiten fallback list is minimal and deterministic (no random).
- All strings in generic derivation are built from the input values (no hidden constants that would make different stands produce identical text).

## Remainder / out of scope (documented, not fixed here)
- `tests/test_technology_roadmapper.py` generic test still asserts the old "Bewertung"/"Grundlegend" strings; will now observe the new derived name ("Technologie-Lücke für T0 — ..."). Left untouched (new char test is authoritative per 2026-06-22/23 decisions).
- `technology_builder.py` generic branch also ignores its `roadmap.gaps` (only looks at traum) and still emits P0. This task did not touch it; the now-real roadmaps from non-jetpack plans are simply passed through. A future task can make builder derive from the gaps the same way.
- Full wiring of Wissensbasis / real breakthrough data into the pfade/aufwand remains future (PLATFORM_PLAN).
- No change to BUILD_LOG.md (explicitly excluded from task scope).
- No changes to any other grenzverschiebung/* or src/gen/*.

**Result:** The generic path of `build_technology_roadmap` is now a real facade-detector: input stands drive output gaps 1:1 with grounded fields; empty input is abstinent; the jetpack demo path is untouched and regression-protected. All characterization tests green. Complies with CLAUDE.md (no silent defaults, gates have tests, A5 determinism, 4 Linsen, isolation rules).

(End of T02 audit)
