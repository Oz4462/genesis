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
| H Shop-floor depth (User gap matrix 2026-07-16) | H1–H8 | ✅ **H1–H8 done** (2026-07-16): drawings dims, CAM helical+nc, RTB ZIP, harness lengths/pinouts, assembly constraints, KiCad zones+clearance, montage torque, multi-physics depth. Residual L4: full GD&T PDF, FreeCAD mates, copper autoroute, real photos, full FEM |

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

**Next open product depth (after Phase H):** full GD&T feature-control frames + multi-sheet PDF, multi-axis freeform CAM, FreeCAD mate solver, full copper autoroute + KiCad DRC, graphical wiring diagrams, certified material SN/CTE, interactive 3D/exploded video, real montage photos, semiconductor pin-compat + thermal CFD — L4 factory sign-off, not L2–L3 first stones.
