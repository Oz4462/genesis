# GENESIS — STATUS (single source of truth)

**Updated:** 2026-07-15 (Phase F complete)  
**main tip:** see `git log -1`  
**Backlog SSOT:** `docs/SYSTEMATIC_BACKLOG_REPORT_2026-07-15.md`  
**TODO plan:** `docs/BACKLOG_TODO_PLAN.md` (Phases A–F done)

> **Law:** depth claims use L0–L4. Never mark “complete” without evidence.

---

## Backlog campaign (2026-07-15)

| Phase | Sprints | Status |
|-------|---------|--------|
| A HORIZON | H1–H5 | ✅ import split, subgates, Ω receipts, δ⁺ fixture, docs |
| B PRINTFORGE | C1–C4 | ✅ CNC material DFM, PCB layout, CNC/Laser cost, face GCode |
| C Realization | C5–C8 | ✅ structured BOM, harness, drawing_gap, PRINTFORGE inventory |
| D Live Knowledge | W1–W5 | ✅ `--mode sources`, seeds, patents key, ledger/vector honesty |
| E Sim & Caps | S1–S4 | ✅ `--mode caps`, multi-physics, mesh refs, MANIFEST caps |
| F Cleanup | X1–X4 | ✅ stale docs, learning extract, revise_with_learning, this STATUS |

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

**Next open product depth:** multi-axis CAM, GD&T PDF drawings, production vector DB, live lab ingest — see backlog report residual gaps.
