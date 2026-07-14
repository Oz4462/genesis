# GENESIS — HORIZON (φ → Ω) — honest status 2026-07-15

Not “everything complete.” **Wired and enforced where evidence exists.**  
Depth scale: **L0** doc → **L1** skeleton → **L2** tested → **L3** LUMEN/CLI wired → **L4** production sign-off.

## Arc

| Step | What | Level | How to verify |
|------|------|-------|----------------|
| Funke / Dream | `process_dream(raw_dream)` | L3 | `python -m gen --mode dream` / lumen tests |
| Hammer | `LumenHammer` + frontier | L3 | jetpack + steel-bracket tests |
| ε Seams | `build_seam_certificate` + `gate_epsilon` | L3 | `horizon_subgates.epsilon` |
| ζ Memory | `build_memory_fabric_certificate` + `gate_zeta` | L3 | `memory_fabric.deposits` |
| γ⁺ Pareto | `build_pareto_front` + `gate_gamma_plus` | L3 | `run_state.pareto_front` |
| δ⁺ Reality | experiment always; measurement optional | L2–L3 | fixture → corroborated; else inconclusive |
| δ⁺ Coverage | `build_coverage_certificate` | L3 | `coverage_certificate` |
| Ω | `build_omega_certificate` + **enforce default True** | L3 | receipts ε/ζ/γ⁺/coverage + pre |
| Caps | TeacherMode + community_evidence | L2–L3 | agent OpenAlex; no user ledger |
| CLI | `horizon-full` | L3 | `python -m gen --mode horizon-full "…"` |

## Root cause fixed (H1/H2)

A single `try/except` imported missing `derive_goal_from_spec` and nulled **all** HORIZON builders. Imports are now **per-module**. Subgates are no longer silent `None` on steel-bracket dreams.

## What is NOT claimed

- Physical lab production (L4)
- CNC/Laser/PCB manufacturing full depth (see PRINTFORGE backlog Phase B)
- Invented field replications or fake δ⁺ measurements
- “HORIZON complete” without residual gaps

## Entry points

```bash
python -m gen --mode horizon-full "steel bracket 100N"
# with live community discovery:
python -m gen --mode horizon-full --live "compliant gripper"
```

```python
from gen.grenzverschiebung.lumencrucible import process_dream
out = process_dream("…", measurement_fixture={"value": 1.0, "unit": "1", "source": "fixture:x"})
```

## See also

- `docs/SYSTEMATIC_BACKLOG_REPORT_2026-07-15.md`
- `docs/BACKLOG_TODO_PLAN.md`
- `docs/STATUS.md`
