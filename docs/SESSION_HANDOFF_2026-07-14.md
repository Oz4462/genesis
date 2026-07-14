# Session Handoff — 2026-07-14 (full-power self-improve)

**main tip:** `git rev-parse HEAD` (see `49d24d4` … latest)

## Full-power batch (iters 14–20)

| Area | Result |
|------|--------|
| Invent γ+ | `pareto_front` via `inventor.score_proxy` |
| Thermal δ | `overtemperature` recipe — invent Kühlung 2 grounded |
| Thermal score | max_service/peak Fourier margin |
| Materials k | Cu 401, Al 205, steel 50, FDM ~0.1–0.25 |
| TE2 refine | wired into `run_invention` + invent CLI |
| δ recipes | plate, contact, mismatch, bolt, fracture (+ overtemp) |
| MANUAL_ONLY | only `creep`, `montecarlo_uncertainty` |
| Smoke | 119 pytest + 12 demos + invent-thermal |

## Smoke

```bash
export PYTHONPATH=src
bash scripts/self_improve_smoke.sh
```

## Living log

`docs/SELF_IMPROVE_LOOP_LIVE.md`

## Still open (next friction)

- Creep recipe needs Larson-Miller tables (honest MANUAL_ONLY)
- Monte Carlo remains formula-driven MANUAL_ONLY
- Live α copper density (network) optional budget
- CadQuery system install still blocked (PEP 668)
