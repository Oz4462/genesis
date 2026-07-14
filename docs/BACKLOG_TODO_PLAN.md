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

- [ ] **C5** Full structured BOM (mech+elec) in realize package
- [ ] **C6** Harness / placement / netlist section
- [ ] **C7** Drawings non-stub or explicit drawing_gap
- [ ] **C8** PRINTFORGE inventory = code truth

## Phase D — Live Knowledge (P1)

- [ ] **W1** SourceConnectorRegistry health / catalog CLI
- [ ] **W2** Electronics / components richer seeding
- [ ] **W3** Patents path key-gated honest
- [ ] **W4** Ledger/postgres production smoke
- [ ] **W5** Vector (pgvector/qdrant) one path or explicit not-wired

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

**Phase A complete (H1–H5). Phase B complete (C1–C4).**  
**Now:** Phase C **C5** — structured BOM (mech+elec) in realize package

## Definition of Done (every sprint)

1. Implementation + unit tests  
2. Smoke or mode demo if CLI-facing  
3. Commit message references sprint id (H1/C1/…)  
4. Check box + SHA in this file  
5. One-line update in SYSTEMATIC_BACKLOG_REPORT  
