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

- [ ] **S1** Caps surface matrix across CLI modes
- [ ] **S2** Mini multi-physics co-sim receipt
- [ ] **S3** mesh_convergence + more reference cases
- [ ] **S4** Bundle MANIFEST caps honesty

## Phase F — Cleanup (P2, continuous)

- [ ] **X1** Stale doc claims (e.g. fracture NotImplemented) removed
- [ ] **X2** learning_integrator richer path
- [ ] **X3** boundary_reviser full path
- [ ] **X4** Doc-sync after every P0 sprint

---

## Active sprint

**Phases A–C complete (H1–H5, C1–C8).**  
**Now:** Phase D **W1** — SourceConnectorRegistry health / catalog CLI

## Definition of Done (every sprint)

1. Implementation + unit tests  
2. Smoke or mode demo if CLI-facing  
3. Commit message references sprint id (H1/C1/…)  
4. Check box + SHA in this file  
5. One-line update in SYSTEMATIC_BACKLOG_REPORT  
