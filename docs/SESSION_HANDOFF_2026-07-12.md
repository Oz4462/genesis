# Session Handoff — 2026-07-12 (product_surface closeout)

> **Branch:** `rework/closeout-2026-07-12` → PR to main  
> **Prior main:** `a38a796` (PR #5 horizon_full)

## Done this closeout

1. `gen.product_surface` — static product reachability anchors (29 modules)
2. CLI imports product_surface (find_islands WIRED path)
3. `montecarlo_uncertainty` validator + MANUAL_ONLY recipe note
4. professional_package static drawing import
5. Islands **63 → 26**; WIRED **218 → 256**
6. Residual 26 dispositioned KEEP_OPTIN / experimental / external (ISLAND_TRIAGE)

## Residual (intentional, not bugs)

- Optional DB/MCP/GPU/oracle/solver backends
- Humanoid SCRIPT/experimental feet/stands
- Discovery RL/srbench harness

## Verify

```bash
.venv/bin/python -c "from gen import product_surface; print(len(product_surface.surface_modules()))"
.venv/bin/python scripts/find_islands.py | head -8
.venv/bin/python -m pytest tests/test_product_surface.py tests/test_physics_validation.py -q
```
