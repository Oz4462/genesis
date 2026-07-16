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

**Phases A–G COMPLETE.** Phase **H (Shop-floor depth)** started 2026-07-16 from user gap matrix.  
**Residual after H1:** full GD&T frames/PDF, multi-axis CAM, assembly constraints, PCB copper+DRC, harness routes, semiconductor/thermal, multi-physics closed-loop, interactive viz, photo montage, Ready-to-Build ZIP.

## Definition of Done (every sprint)

1. Implementation + unit tests  
2. Smoke or mode demo if CLI-facing  
3. Commit message references sprint id (H1/C1/…)  
4. Check box + SHA in this file  
5. One-line update in SYSTEMATIC_BACKLOG_REPORT  

## Phase G — Integrity & CAD depth (Re-Audit 2026-07-15)

- [x] **G1 (P0-1)** assembly.py 0-byte-STL fake fix: real kernel STLs (builder CSG + bridge), real union, honest gaps — SHA in commit `fix(g1)`
- [x] **G2 (P0-2)** Doc re-sync measured 2026-07-15: 2594 collected · 45 validators · 46 recipes · 1 manual-only · 334/266/25 · 51 CLI modes — commit `docs(g2)`
- [x] **G3 (P1-1)** Spec→CAD bridge: `cad/spec_to_cad.py` (γ-Spec→BuildArtifact real kernel STL; PrototypeSpec from real AssemblyConcept; parametric generic plate) — commit `feat(g3)`
- [x] **G4 (P1-3)** Drawings: real top/front DXF sections in packages via export/drawing worker (drawing_gap honest-False; worker stdout+rotation fix) — commit `feat(g4)`

## Phase H — Shop-floor depth (User gap matrix 2026-07-16)

Priority order from manufacturability impact (not existence of modules).

| Sprint | Gap area | Done-Kriterium |
|--------|----------|----------------|
| **H1** | Produktionszeichnungen — overall dims + right view | top/front/right DXF with envelope linear DIMENSION + `.dims.txt`; full GD&T frames still gap |
| **H2** | CAM — 3rd real op or multi-pass freeform honesty | new verified G-code path OR explicit multi-axis gap with one 3D roughing stub that verifies |
| **H3** | Ready-to-Build package ZIP | single archive: BOM+STL+DXF+harness+gcode+MANIFEST; CLI mode or integrator flag |
| **H4** | Harness depth | wire lengths + connector pinouts structured; wiring diagram gap honest |
| **H5** | Assembly constraints first stone | mate/offset constraints on AssemblyPart beyond free position; FreeCAD optional |
| **H6** | KiCad copper path | minimal copper pour or zone OR external DRC handoff doc + test |
| **H7** | Montage visual steps | step list with torque fields + image placeholders; no fake photos |
| **H8** | Multi-physics receipt depth | one FEM/therm/dyn chain with provenance beyond closed-form |

- [x] **H1** Overall envelope dimensions + right (YZ) view on package DXFs — `export/drawing.py` (`section_dxf_dimensioned`, `annotate_overall_dimensions`), worker `section_dxf_with_info`, package top/front/right + sidecars; tests `test_drawing_dimensions.py` + package suite
- [ ] **H2** CAM depth
- [ ] **H3** Ready-to-Build ZIP
- [ ] **H4** Harness lengths/pinouts
- [ ] **H5** Assembly constraints
- [ ] **H6** KiCad copper/DRC
- [ ] **H7** Montage steps structure
- [ ] **H8** Multi-physics depth
