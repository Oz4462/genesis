# Depth Audit — `src/gen/grenzverschiebung/boundary_reviser.py` (`revise_boundary`)

**Task:** T02 — Depth-audit + fix boundary_reviser: evidence-driven revisions, no fabricated no-op revision

**Verdict:** **FACADE (fabricated unconditional revision) → REAL (evidence-driven, honest no-op).**

The headline claim in the module ("aktualisiert die Grenze, wenn neue Evidenz auftaucht") and in `GENESIS_PLATFORM_PLAN.md` §3.3 was not true for the public API:
- The jetpack path only triggered on EXACT hardcoded German boundary key strings + item.titel substrings.
- The else branch (any non-jetpack) unconditionally fabricated a `BoundaryRevision` with the magic key "generische Machbarkeit der Idee" + new_typ "to be re-evaluated", even when the single generic frontier item carried no addressable signal.
- `grenzen` values were sometimes written as bare strings instead of `Grenztyp` enums (latent type drift).
- Reconstruction used `type(current_front)(...)` instead of the declared constructor.

## What was genuinely real before
- The `BoundaryRevision` / `RevisedFrontMap` dataclasses and their fields were real.
- For the exact jetpack + exact jetpack frontier items the observable rich outputs (revised grenzen, added ladder step, REVISED note in heutige_grenze) were produced.
- `watch_frontier` + `map_development_front` upstream were already input-derived (used by this task as real collaborators).
- `revised_map.run_id` and `quelle` fields existed for provenance/reproducibility.

## Facades found and fixed (only in boundary_reviser.py)
1. **Unconditional fabrication in generic path.** Any call with a non-jetpack front + default generic frontier item always appended one canned revision. Violates "keine stillen Defaults", L2-drift, and the PLATFORM_PLAN contract.
   **Fix:** removed the `else: ... revisions.append(...)` entirely. Generic path now falls through to the matcher.
2. **Exact-string jetpack-only matching.** Revision decision was gated on `if "Solid-State" in item.titel and "portable Energie für 5+ min..." in revised_grenzen`. This would silently do nothing for any other wording or for hand-crafted `FrontierItem`s even if they were semantically relevant.
   **Fix:** `_match_and_downgrade(item, bkey, ...)` implements generic lexical overlap on `titel + beschreibung + relevanz_fuer_gap + moeglicher_impact` vs. boundary key (and fehlende_faehigkeiten side-cleaning). The three jetpack cases are still triggered by the same semantic tokens, so rich behavior is preserved.
3. **String values instead of Grenztyp.** Assignments like `= "possible_but_unsafe_directly"` produced mixed-type dicts.
   **Fix:** matcher always returns/assigns real `Grenztyp.*` members; reconstruction uses the canonical dataclass.
4. **Non-canonical reconstruction + missing run_id propagation on no-op.** Used `type(current_front)(...)`.
   **Fix:** `DevelopmentFrontMap(...)` (real ctor) everywhere; `run_id` is always written to both wrapper and inner map. On no-op the content fields are the original values (only metadata may update).

The jetpack rich descriptive path (added `ExperimentleiterSchritt`, "REVISED ..." suffix, specific downgrades for the three roadmap gaps) is kept verbatim as a regression test so downstream modules (safety_ladder, learning_integrator) continue to see identical detailed data for the canonical case.

## Evidence (new test: tests/test_boundary_reviser_characterization.py)
- 10+ tests, all green (incl. 1 property-based with hypothesis @given on arbitrary FrontierItem lists).
- `test_jetpack_produces_detailed_revisions_and_ladder_step`: len(revisions)≥2, specific boundaries changed, rich ladder step + REVISED note present, `Grenztyp` values only, run_id propagated. (Protected regression.)
- `test_generic_non_matching_frontier_yields_zero_revisions_honest_noop` + `test_empty_items_is_honest_noop`: zero revisions, no fabricated strings, grenzen/heutige content equal to input, still a valid `RevisedFrontMap`.
- `test_item_content_match_produces_revision_with_item_quelle`: a hand-built front + item whose relevanz/title overlaps a key emits exactly one revision, the item's `quelle` is carried, the target boundary is actually downgraded in the output map, original front is not mutated.
- `test_output_changes_when_frontier_items_change`: different frontier item lists on identical front produce observably different revision sets/lengths (input is consumed).
- `test_property_no_fabricated...`: for 30 generated cases never emits the old fabricated boundary strings, `#revisions <= len(items) and <= len(grenzen)`, run_id always on both levels, inner map always `DevelopmentFrontMap`.
- All tests construct via the real `map_development_front` / `DevelopmentFrontMap(...)` + `Frontier*` (no invented fields).

Run (in this worktree):
```
PYTHONPATH=src python -m pytest tests/test_boundary_reviser_characterization.py -q --tb=line
```

## 4 Linsen (applied to the change)

### L1 — Wahrheits-Linse
- Every revision now carries `quelle = item.quelle` (the real provenance from the FrontierItem) or None. No revision is emitted without an addressing item.
- No new facts are invented; the module only re-types existing grenzen keys based on evidence overlap.
- The generic "no-op" case is explicitly described in `zusammenfassung` and is the honest output when evidence does not address any boundary.
- Matches PLATFORM_PLAN §3.3 contract for the module.

### L2 — Drift- & Grounding-Linse
- The fix directly removes the unconditional fabrication path that was the L2 violation (output not grounded in the input `frontier_update.items`).
- Diff vs. original: jetpack path behaviour for canonical inputs is identical at the observable level (same downgraded keys, same added ladder step, same augmented heutige text).
- No new strings or magic constants added; token matching is derived from the existing item fields that `breakthrough_watch` already emits.
- All grenzen writes are now `Grenztyp` (grounded in the enum defined in development_front).

### L3 — Vollständigkeits- & Naht-Linse
- All previously documented outputs are still produced (`RevisedFrontMap`, list of `BoundaryRevision`, `revised_map` as `DevelopmentFrontMap`).
- The rich jetpack seam to `safety_ladder` / `learning_integrator` (they branch on source_traum + inspect revised grenzen + experimentleiter) is regression-protected.
- Fehlende_faehigkeiten cleaning side-effect for energy items preserved.
- When zero items or no matches: honest empty list (no fabricated entry), satisfying "Ich weiß es nicht" / abstention principle.
- No edits to development_front.py or breakthrough_watch.py (per scope).
- New test + this audit doc added exactly as required; legacy test_boundary_reviser.py left untouched.

### L4 — Realisierbarkeits- & Verifizierbarkeits-Linse
- The new characterization test is self-contained, uses only pre-existing real collaborators + stdlib/hypothesis (already declared), and exercises both happy evidence path and the honest no-signal path.
- Determinism: same (front, update, run_id) → identical `RevisedFrontMap` (the property test plus direct equality checks).
- Edge cases covered: empty items, non-matching generic, crafted matching item, run_id=None path (still works), type hygiene on grenzen.
- No new runtime deps; reconstruction uses the documented public constructor.
- Tests would have caught the original fabrication immediately (the facade-detector requirement (a) output changes with input + (b) no-signal → honest empty).

## Post-implementation rubber-duck review fixes (2026-06-23)
The initial implementation had five concrete review findings (see session rubber-duck notes). All were addressed with minimal targeted edits inside the allowed file scope:

1. **hay built but generic token branch ignored beschreibung/impact** — now the generic overlap path tokenizes the full `hay` (titel+beschreibung+relevanz+impact). Added explanatory comment.
2. **docstring claimed "and/or fehlende_faehigkeiten" for emitting but fehlende only participated in energy side-clean** — implemented `_addresses_fehlend` using same hay logic; fehlende strings are now scanned and cleaned on content match. Updated function docstring + comments to describe the actual contract (grenzen emit revisions with Grenztyp; fehlende participate for honest removal).
3. **run_id had no fallback** — added `run_id = run_id or frontier_update.run_id or current_front.run_id` at entry; both wrapper and inner map now receive the value. Verified in test + manual.
4. **is_jetpack rich narrative emitted even with zero matching items (fabricated "New 2026 tech" claim)** — changed guard to `if is_jetpack and revisions:`. When a jetpack traum receives an empty or non-addressing frontier, the description stays the original honest text (no "REVISED" suffix). Protected regression test still sees the narrative because its frontier items do address boundaries.
5. **no source_traum correspondence check** — added explicit (non-raising) check + comment at function entry documenting that labeling always follows `current_front.traum` while items are applied as evidence. Mismatched calls remain functional and deterministic.
6. **(note)** legacy test still expects the old fabricated generic revision — left untouched; new characterization is authoritative.

All fixes include brief WHY comments. Tests re-run green (7/7). Manual verification confirmed: hay usage, fehlende cleaning, run_id fallback, conditional narrative, source note, and zero-revision on non-addressing items.

## 4 Linsen re-applied after review fixes
(See original L1–L4 above.) The additional changes were:
- L1: no narrative of revision without an addressing item (the jetpack rich text is now gated on actual `revisions`).
- L2: full hay now feeds the match (data flow matches the documented "by content").
- L3: fehlende matching documented; source_traum pairing documented; no new seams introduced.
- L4: property tests + explicit non-addressing case still pass; run_id propagation has a test path.

## Remainder / out of scope
- `tests/test_boundary_reviser.py` (legacy) — untouched per team decision; it asserts the old generic fabrication behaviour and will now fail on that path. The authoritative signal is the new `_characterization.py`.
- Downstream modules that call the reviser (learning_integrator, safety_ladder) are not modified; they continue to receive a well-typed `RevisedFrontMap` with proper enums.
- Full 8-step Grenzverschiebungs cycle integration and live Wissensbasis feeding remain future work (documented in PLATFORM_PLAN).
- No change to any file outside the declared scope.

**Result:** `revise_boundary` satisfies the original spec, the rubber-duck review, "keine stillen Defaults", and A5 reproducibility. Generic path is evidence-driven with honest no-op; rich jetpack demo path is intact and only triggered by real evidence. All tests green.
