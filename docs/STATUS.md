# GENESIS — STATUS (single source of truth)

**Updated:** 2026-07-16 (Phase H started — H1 drawings depth)  
**main tip:** see `git log -1`  
**Backlog SSOT:** `docs/SYSTEMATIC_BACKLOG_REPORT_2026-07-15.md`  
**TODO plan:** `docs/BACKLOG_TODO_PLAN.md` (Phases A–G done; Phase H in progress)

> **Law:** depth claims use L0–L4. Never mark “complete” without evidence.

---

## Backlog campaign (2026-07-15 → 2026-07-16)

| Phase | Sprints | Status |
|-------|---------|--------|
| A HORIZON | H1–H5 | ✅ import split, subgates, Ω receipts, δ⁺ fixture, docs |
| B PRINTFORGE | C1–C4 | ✅ CNC material DFM, PCB layout, CNC/Laser cost, face GCode |
| C Realization | C5–C8 | ✅ structured BOM, harness, drawing_gap, PRINTFORGE inventory |
| D Live Knowledge | W1–W5 | ✅ `--mode sources`, seeds, patents key, ledger/vector honesty |
| E Sim & Caps | S1–S4 | ✅ `--mode caps`, multi-physics, mesh refs, MANIFEST caps |
| F Cleanup | X1–X4 | ✅ stale docs, learning extract, revise_with_learning, this STATUS |
| G Integrity & CAD depth (Re-Audit 2026-07-15) | G1–G4 | ✅ no-0-byte-STL fix + real kernel STLs, Spec→CAD bridge (`cad/spec_to_cad.py`), parametric plates, real top/front DXF sections (`drawing_gap` honest-False) |
| H Shop-floor depth (User gap matrix 2026-07-16) | H1–H8 + residual | ✅ **H1–H8 + residual L4 stones** (2026-07-16): GD&T FCF+PDF, waterline CAM, FreeCAD mates macro, Manhattan copper, step diagrams, materials CTE/SN, interactive STL viewer. Honest: not PE-stamped / not 5-axis / not coupon-certified |

---

## HORIZON φ → Ω (levels)

| Layer | Level | Evidence |
|-------|-------|----------|
| ε/ζ/γ⁺/coverage/Ω | L3 | process_dream subgates True; enforce_omega default |
| δ⁺ | L2–L3 | inconclusive without fixture; corroborated with measurement_fixture |
| Caps | L2–L3 | assess/bundle/realize; `python -m gen --mode caps` |

---

## CLI modes (selected)

| Mode | Purpose |
|------|---------|
| `horizon-full` | Full HORIZON arc + discovery + grenz |
| `sources` | Connector catalog health |
| `caps` | Platform caps matrix |
| `multi-physics` | Elec→thermal + beam tip receipt |
| `realize` / `bundle` | Packages with structured BOM + caps |

---

## Policy

1. Agent-sourced public data — no user community ledger  
2. No invented measurements  
3. PatentsView only with `PATENTSVIEW_API_KEY`  
4. Production Qdrant/pgvector **not wired** (anamnesis vendor only)  
5. After each sprint: test + commit + push  

**Next open product depth (true factory L4):** PE-stamped multi-sheet GD&T release, simultaneous 5-axis freeform CAM kernel, FreeCAD Assembly WB solver, production autorouter+DRC, coupon-certified SN/CTE, photographic build docs, semiconductor pin-compat + thermal CFD. Package now ships working first stones for each former residual.

### Audit 2026-07-16 (priority fixes)

| ID | Status |
|----|--------|
| A1 integrator gcode dict key | ✅ process name keys |
| A2 cli verbose dead condition | ✅ removed |
| B1 exec()+fake volumes 42/48.5 | ✅ bbox/kernel volume; no exec |
| D1 SIMP dense linalg | ✅ scipy.sparse + spsolve |
| E3 tempfile.mktemp | ✅ NamedTemporaryFile |
| C1 lernmaschine L1 honesty | ✅ scripted proposal labeled |
| C4 config.yaml orphan | ✅ `load_default_yaml()` wired |
| C5 trust_core install note | ✅ README Installation |
