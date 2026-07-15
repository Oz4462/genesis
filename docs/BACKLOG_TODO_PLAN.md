# GENESIS Backlog — Sequential TODO Plan

**SSOT report:** `docs/SYSTEMATIC_BACKLOG_REPORT_2026-07-15.md`  
**Rule:** One sprint at a time. Check boxes only with commit SHA + test evidence.

---

## Phase A — HORIZON Trust (P0)

- [x] **H1** ζ `memory_fabric` populate + attach — `a6c59c3` (import split root cause)
- [x] **H2** ε / coverage / γ⁺ attach — `a6c59c3` (same fix; all subgates True)
- [x] **H3** Ω receipts include ε/ζ/γ⁺/coverage — `9959bea`
- [x] **H4** δ⁺ measurement fixture ingest — `a3128bf`
- [x] **H5** Doc-Sync HORIZON/STATUS L0–L4 — this commit

## Phase B — PRINTFORGE Core (P0/P1)

- [x] **C1** CNC material-aware ProcessDFM — `3d7e126` (+ resolve/evaluate_cnc_wall)
- [x] **C2** PCB layout evaluation + laser rules already L2 — same commit family
- [x] **C3** CNC/Laser cost ranges (`estimate_cnc_cost` / `estimate_laser_cost`)
- [x] **C4** Face-mill GCode + advanced DFM surface face_mill details

## Phase C — Realization Package (P1)

- [x] **C5** Structured BOM mech+elec (`realization_package.py` + bom.json)
- [x] **C6** Harness / placement / netlist (`harness_package.json`)
- [x] **C7** Drawings index + explicit `drawing_gap`
- [x] **C8** PRINTFORGE inventory = code truth

## Phase D — Live Knowledge (P1)

- [x] **W1** Source catalog + CLI `--mode sources` (`tools/source_catalog.py`)
- [x] **W2** Electronics/improvement recipes in `seed_electronics_components`
- [x] **W3** PatentsView key-gated status (no fake empty search)
- [x] **W4** Ledger status: DSN / in-memory honesty + smoke pointer
- [x] **W5** Vector status: anamnesis local vendor; production Qdrant/pgvector not wired

## Phase E — Simulation & Caps (P1/P2)

- [x] **S1** Caps matrix CLI `--mode caps` (`platform_caps.py`)
- [x] **S2** Mini multi-physics receipt CLI `--mode multi-physics`
- [x] **S3** More reference cases + synthetic mesh_series fixture
- [x] **S4** Bundle MANIFEST caps fields (proof/readiness/teacher/community)

## Phase F — Cleanup (P2, continuous)

- [x] **X1** Stale fracture NotImplemented claims fixed in OPEN_MODULES + DOC_CODE_DRIFT
- [x] **X2** learning_integrator extracts safety.stages + revised.revisions; `run_grenz_learning_loop`
- [x] **X3** `revise_with_learning` + `apply_delta_to_front` (no fake Grenztyp upgrades)
- [x] **X4** STATUS/BACKLOG synced — Phases A–F complete

---

## Active sprint

**Phases A–F COMPLETE** (H1–X4).  
**Residual product depth:** multi-axis CAM, GD&T PDF, prod vector DB, live lab ingest — see SYSTEMATIC_BACKLOG_REPORT.

## Definition of Done (every sprint)

1. Implementation + unit tests  
2. Smoke or mode demo if CLI-facing  
3. Commit message references sprint id (H1/C1/…)  
4. Check box + SHA in this file  
5. One-line update in SYSTEMATIC_BACKLOG_REPORT  

## Phase G — Integrity & CAD depth (Re-Audit 2026-07-15)

- [x] **G1 (P0-1)** assembly.py 0-byte-STL fake fix: real kernel STLs (builder CSG + bridge), real union, honest gaps — SHA in commit `fix(g1)`
- [ ] **G2 (P0-2)** Doc re-sync measured block 2026-07-15 (tests/validators/recipes/islands)
- [ ] **G3 (P1-1)** Spec→CAD bridge for realize path (Specification.components → CSG → kernel STL, template only as gap-noted fallback)
- [ ] **G4 (P1-3)** Drawings: enable real DXF/SVG section path in packages (reduce drawing_gap for prism parts)
