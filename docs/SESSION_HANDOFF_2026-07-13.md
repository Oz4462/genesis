# Session Handoff — 2026-07-13 (full audit)

> **main tip:** `97a078f` (+ this metrics bump if merged)

## Audit result (2026-07-13)

| Check | Result |
|-------|--------|
| Source tree committed | **YES** — no uncommitted `.py`/docs (only local `__pycache__` + `__main__*_out`) |
| main == origin/main | **YES** |
| Open PRs | **0** |
| REWORK OPEN modules | **0** / ~303 REWORKED |
| product_surface import | **OK** (29 anchors) |
| CLI modes | **47** including aero/humanoid-report/surface/horizon-full |
| Reachability | modules 327 · WIRED 258 · SCRIPT 9 · ISLAND 26 · INFRA 34 |
| Tests collected | **2494** |
| Validators / recipes | **44** / **38** |

## Intentional non-product islands (26)

KEEP_OPTIN: postgres, mcp, materials_oracle, sim solvers, ollama_embedder, humanoid experimental SCRIPT, discovery RL harness.

## Local junk (not for git)

`__main__*_out/` OpenMDAO reports · `tests/__pycache__/*`
