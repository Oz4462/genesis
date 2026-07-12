# Session Handoff — 2026-07-12

> **Purpose:** Continue REWORK without losing state if context ends.  
> **Repo:** https://github.com/Oz4462/genesis  
> **Default branch `main`:** `31b2c50` (PR #1 **MERGED**)  
> **Continue branch:** `rework/continue-2026-07-12` (PR #2)

## Done (do not re-do)

- Full rework campaign ported onto main via PR #1 (merged).
- CI green on merge tip (3.11 + 3.12).
- Integrity: Claim/SourceRef, NaN gates, seams ISRU/LIFE, cost rollup, reward NaN→0.
- PRODUCT_WIRE: fach_cli, frontier, 10 Fach-Pipelines.
- Tools cluster REWORKED (incl. Wikidata SPARQL escape).
- Discovery/grenz/inventor almost fully REWORKED.
- Humanoids package restored + knee_squat_hold_torque + evidence_level + missing-asset gaps.
- Root physics/export/integration batch REWORKED on continue branch.
- **Aero restore:** `gen.aero.*` + `MIN_THRUST_WEIGHT_BY_CLASS` / `min_thrust_weight_for_class` in `flight.py`.
- **Deliverables restore:** `export.drawing` + `drawing_worker`, `finalizer.professional_package`, `visualization.robust_renderer`.
- Evidence: ruff clean on touched paths; **48 passed** (`test_aero_drone_calibration`, `test_flight`, `test_drawing_integration`, `test_professional_package`).
- Campaign inventory: see `docs/REWORK_CAMPAIGN.md` (aero/drawing/finalizer/visualization REWORKED).

## Branches on GitHub

| Branch | Tip | Note |
|--------|-----|------|
| `main` | `31b2c50` | merged PR #1 SSOT baseline |
| `rework/continue-2026-07-12` | **active** | PR #2 continue work |
| `rework/full-open-2026-07-11` | `ca8f2a0` | full campaign history (source for restores) |

## Next OPEN clusters (priority)

1. Remaining root modules with suites: `physics_selection`, `plate_bending`, `pressure_vessel`, `proof_kernels`, `ratification`, `refinement`, `security`, `software`, `telemetry`, `thermal*`, `tolerance`, `torsion`, `training_plan`, `uncertainty`, `visionary_ideas`, `audit.run_audit`, …
2. `gen.web.__main__`, `gen.omega`, `gen.orientation`, `gen.humanoid_research`
3. `_experimental/*` — KEEP_OPTIN / archive honesty only
4. Islands / AETHON assets honesty; topology/section optimizer integration
5. Merge PR #2 when CI green

## Working rules (autonomous)

1. Stay on **`rework/continue-2026-07-12`**; push often; **never force-push main**.
2. One cluster at a time; after each: update `REWORK_CAMPAIGN.md` + short `BUILD_LOG` entry.
3. **Context window:** commit + push + refresh handoff **before ~500k**; do not wait for user.
4. User authorized continuous autonomy after each task without asking.

## Quick verify commands

```bash
cd /home/genesis/genesis
git checkout rework/continue-2026-07-12 && git pull
.venv/bin/ruff check src/gen/aero src/gen/flight.py src/gen/finalizer src/gen/export/drawing.py src/gen/export/drawing_worker.py
.venv/bin/python -m pytest tests/test_aero_drone_calibration.py tests/test_flight.py tests/test_drawing_integration.py tests/test_professional_package.py -q --tb=line
```

## Leave-off

- Aero + drawing + professional package restored and green (48p).
- Next autonomous batch: remaining OPEN root physics/quality modules + suites.
- PR #2 should include this commit; merge when CI green.
