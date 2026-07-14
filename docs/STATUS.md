# GENESIS — STATUS (single source of truth)

**Updated:** 2026-07-15  
**main tip:** see `git log -1`  
**Backlog SSOT:** `docs/SYSTEMATIC_BACKLOG_REPORT_2026-07-15.md`  
**TODO plan:** `docs/BACKLOG_TODO_PLAN.md`

> **Law:** depth claims use L0–L4 (doc-only → production). Never mark “complete” without evidence (pytest / CLI smoke / commit).

---

## HORIZON φ → Ω (honest levels)

| Layer | Symbol | Level | Evidence (2026-07-15) | Residual |
|-------|--------|-------|------------------------|----------|
| Seams | ε | **L3** | `process_dream` → `seam_certificate`, `horizon_subgates.epsilon=True` (H1/H2) | Richer multi-domain seams |
| Memory fabric | ζ | **L3** | `memory_fabric` deposits from VERIFIED claims; `zeta=True` (H1) | Dynamics / recall population |
| Coverage | δ⁺ cov | **L3** | `coverage_certificate` attached; gate True (H2) | Richer reviewed modes |
| Inverse design | γ⁺ | **L3** | `pareto_front` + gate True (H2) | Deeper multi-objective |
| Reality | δ⁺ | **L2–L3** | No fixture → `inconclusive` (honest); with `measurement_fixture` → corroborated (H4) | Live lab ingest beyond fixtures |
| Omega | Ω | **L3** | `enforce_omega=True` default; receipts include ε/ζ/γ⁺/coverage (H3) | Not L4 physical sign-off |
| LUMEN entry | — | **L3** | `python -m gen --mode horizon-full`; `process_dream` | — |
| Teacher / Community | caps | **L2–L3** | TeacherMode + agent OpenAlex community (`user_data_required=False`) | Field lab replications never invented |

**Sprint evidence:** H1–H4 commits on `main` (`a6c59c3`, `9959bea`, `a3128bf`, …).

---

## Product blocks (summary)

| Area | Level | Note |
|------|-------|------|
| CadQuery / print path | L3 | `.venv-cad` bridge; multi-part opt-in |
| GCode | L2 | profile + rect pocket; no multi-axis |
| cost_model | L2 | FDM only; CNC/Laser/PCB gaps |
| manufacturing_check | L2 | FDM strong; CNC/Laser/PCB process stubs |
| Realisierungspaket | L2 | mini/realize; not full BOM/harness L4 |
| Materials / Wikidata α | L3 | live density path |
| Live LLM | gated | `GENESIS_ALLOW_LIVE=1` |
| The Well | L2 probe | stream only; never 15 TB bulk |

---

## Active work

**Phase A done:** H1–H4 (+ H5 this doc).  
**Next:** Phase B **C1** — CNC ProcessDFM rules (`docs/BACKLOG_TODO_PLAN.md`).

---

## Policy

1. Agent-sourced public data (OpenAlex, Wikidata, arXiv) — user supplies no community JSON.  
2. No invented measurements.  
3. Failed Ω blocks completion (`OmegaGateNotPassed`).  
4. After every sprint: pytest + commit + push + plan checkbox.
