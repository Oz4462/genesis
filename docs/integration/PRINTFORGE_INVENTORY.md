# PRINTFORGE Inventory — code truth (2026-07-15)

**Status:** No external product named PRINTFORGE was found. GENESIS implements manufacturing competence **natively** under `src/gen/cad/` + pipelines.

This document tracks **what exists in code** (not aspirational PLAN prose).

---

## Decision (PLAN §3.7)

| Option | Outcome |
|--------|---------|
| Integrate external PRINTFORGE | **N/A** — no tool found |
| Build native Fertigungs module | **Chosen** — active |

---

## Module map (L-levels)

| Capability | Module | Level | Evidence |
|------------|--------|-------|----------|
| Prototype CAD / STL | `cad/prototype_cad_builder.py` | L2–L3 | Jetpack tether plate, build123d code emit |
| CadQuery bridge | `cad/cadquery_bridge.py` + `.venv-cad` | L3 | Print path / BREP (see `docs/CADQUERY_VENV.md`) |
| Manufacturing gate | `cad/manufacturing_check.py` | L2–L3 | `check_manufacturing`, `check_advanced_dfm` |
| FDM/CNC/Laser/PCB DFM | `dfm.py` + advanced DFM | L2–L3 | C1 material-aware CNC; C2 PCB layout optional |
| Cost models | `cad/cost_model.py` | L2 | FDM + C3 CNC/Laser bands (honest gaps) |
| G-code | `cad/gcode.py` | L2 | Profile, rect pocket, **face mill (C4)** + verifier |
| KiCad skeleton | `cad/kicad.py`, `kicad_cli.py` | L1–L2 | Export helpers; full copper DRC external seam |
| Electronics | `electronics.py` + Elektriker pipeline | L2 | Netlist, harness, placement, internal DRC |
| Realization package | `pipelines/integrator.py` + `realization_package.py` | L2–L3 | **C5 BOM**, **C6 harness**, **C7 drawings gap** |
| Fertigungs pipeline | `pipelines/fertigungs.py` | L2 | Process selection + cost notes |

---

## Package artifacts (`build_full_mini_realization_package`)

On disk under `out/realization_packages/…`:

| File | Sprint | Content |
|------|--------|---------|
| `bom.json` / `BOM.md` | C5 | Structured mech+elec BOM (`genesis-bom-v1`) |
| `harness_package.json` / `HARNESS.md` | C6 | Harness + netlist + placement + gaps |
| `drawings.json` / `DRAWINGS.md` | C7+G4+H1 | Drawing index; real top/front/right DXF + envelope dims when CSG exists; `drawing_gap: false` then |
| `part_*_{top,front,right}.dxf` (+ `.dims.txt`) | G4+H1 | Kernel section drawings with overall linear DIMENSION entities |
| `manifest.json` | — | Includes `bom`, `drawing_gap`, `harness_package`, DFM, fertigungs |
| `part_*.stl`, assembly STLs | — | Geometry |
| `electronics_*.json` | — | Elektriker layer when available |

---

## Honest gaps (still open)

1. Full multi-axis / freeform CAM toolpaths  
2. Full GD&T feature-control frames, surface finish, multi-sheet PDF (H1 closed overall envelope dims + right view)  
3. Full KiCad ERC/DRC sign-off on real copper  
4. Supplier-backed BOM prices (requires claim-grounded `Sourcing`)  
5. Live print farm / machine queue integration  
6. Ready-to-Build single ZIP with all manufacturer artifacts  


---

## How to run

```bash
export PYTHONPATH=src
python -m pytest tests/test_manufacturing_check.py tests/test_gcode.py \
  tests/test_cost_model_cnc_laser.py tests/test_realization_package.py \
  tests/test_integrator.py -q

python -c "
from gen.pipelines.integrator import build_full_mini_realization_package
print(build_full_mini_realization_package(['steel bracket 100N'], run_id='inv-demo'))
"
```

---

## History

- 2026-06-15: Initial inventory — no external PRINTFORGE  
- 2026-07-15: Synced to code after Phase B (C1–C4) + Phase C (C5–C7)  

**Quelle:** live tree under `src/gen/cad`, `src/gen/pipelines`, tests listed above.
