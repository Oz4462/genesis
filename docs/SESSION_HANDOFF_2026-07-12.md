# Session Handoff — 2026-07-12

> **Purpose:** Continue REWORK without losing state if context ends.  
> **Repo:** https://github.com/Oz4462/genesis  
> **Default branch `main`:** `31b2c50` (PR #1 **MERGED**)

## Done (do not re-do)

- Full rework campaign ported onto main via PR #1 (merged).
- CI green on merge tip (3.11 + 3.12).
- Integrity: Claim/SourceRef, NaN gates, seams ISRU/LIFE, cost rollup, reward NaN→0.
- PRODUCT_WIRE: fach_cli, frontier, 10 Fach-Pipelines.
- Tools cluster REWORKED (incl. Wikidata SPARQL escape).
- Discovery/grenz/inventor almost fully REWORKED.
- Humanoids package restored + knee_squat_hold_torque + evidence_level + missing-asset gaps.
- Campaign inventory: **~229 REWORKED / ~74 OPEN** (see `docs/REWORK_CAMPAIGN.md`).

## Branches on GitHub

| Branch | Tip | Note |
|--------|-----|------|
| `main` | `31b2c50` | **SSOT for continued work** |
| `rework/full-open-from-main` | `7641896` | merged into main |
| `rework/full-open-2026-07-11` | `ca8f2a0` | full campaign history (unrelated to old local main) |

## Next OPEN clusters (priority)

1. **Root physics/quality modules with suites** (high product value):  
   `costing`, `completeness`, `constraint_consistency`, `coverage`, `dynamics`, `electronics`,  
   `evaluation`, `flight`, `geometry_verification`, `grounding_integrity`, `kinematics`,  
   `mesh_integrity`, `memory_fabric`, `mechanics_formulas`, `contact`, `creep`, `fracture`, …
2. **export/**: assembly, build123d, drawing_worker, numfmt  
3. **external/**: oracle, registry  
4. **integration/**: audited_run, drift, identity_research_hook  
5. **aero/**, **wissensbasis/** remaining, **visualization**, **web.__main__**  
6. **_experimental/** — KEEP_OPTIN / archive honesty only

## Working rules for next session

1. Branch from **current `main`**: `git checkout main && git pull && git checkout -b rework/continue-YYYY-MM-DD`
2. One cluster at a time; **commit + push often** (do not wait for full 500k context).
3. After each cluster: update `docs/REWORK_CAMPAIGN.md` + short `BUILD_LOG.md` entry.
4. Never force-push `main`; open PR or merge only with CI green.
5. Optional assets (`humanoid_assets/`) may be missing in CI — already treated as honest gaps.

## Quick verify commands

```bash
cd /home/genesis/genesis
git checkout main && git pull origin main
.venv/bin/ruff check .
.venv/bin/python -m pytest -q --tb=line   # full suite ~8 min
```

## Leave-off

- Branch: `rework/continue-2026-07-12` (from main `31b2c50`).
- Root physics/export/integration batch REWORKED; docs updated; push this branch.
- Next: aero/* + remaining OPEN (~30) + PR continue→main when green.
- Optional: restore `gen.finalizer.professional_package` / `export.drawing_worker` from campaign if still needed.
