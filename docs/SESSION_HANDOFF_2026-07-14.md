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

## Still open (next friction) — updated after gap-close

- Full-formula Monte Carlo remains MANUAL (`montecarlo_product` auto-selects)
- The Well: HF package optional (stream/fixture; never 15 TB bulk)
- Multi-part BREP STL via cad-venv: opt-in `GENESIS_CAD_MULTIPART=1`
- Community/TRL/trustcore: stub scores (field data deferred)
- Live α copper (2026-07-14 run): pipeline completed with grok-4.5+claude; registry claims 8960 kg/m³ + k=401 surfaced but skeptic left them **unsupported** (wiki corroboration windows hit electroplating/overview pages without the density number). Offline registry anchor remains the grounded δ-path.

## Closed (do not re-open as bugs)

- CadQuery: PEP 668 + isolated `.venv-cad` + bridge (see `docs/CADQUERY_VENV.md`)
- Creep CheckRecipe landed; invent γ+ `score_recomputable`
- `generate_rect_pocket_gcode` + CLI `.text()` write path
