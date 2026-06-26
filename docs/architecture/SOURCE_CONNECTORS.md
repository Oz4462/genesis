# GENESIS Source Connector Contract (per GENESIS_PLATFORM_BUILD_TODO §A4 / B3)

**Core Rule:** Discovery yes, full-text storage no (unless licensed + policy allows).

## Connector Schema

```python
SourceConnector(
    name: str,
    kind: str,  # "arxiv", "patent", "material_db", "component_db", "local", ...
    endpoint_hint: str | None,
    policy: SourcePolicy | None,  # license, cost, rate_limit, store_fulltext, store_snippets
    quelle: str,
)
```

## Required Behavior (fetch)

- `fetch(name, query)` → list[dict] (lightweight discovery records only)
- Never stores fulltext unless `assert_may_store(policy, "fulltext")`
- Always returns `quelle` + provenance hints.
- Offline/deterministic first; live adapters behind guards.

## Current (2026-06)

- arxiv: lightweight metadata (improved stub + registration of ArxivBackend)
- components / material_db: seeded `ComponentRecipe` from electronics, CAD, bio, lern results
- local_out: scans out/ for realization packages
- synthetic + bio_energy + physics_recipe: internal for generalist (no net needed)

## Examples of Good Use

- In lumencrucible / lernmaschine: `reg.fetch("components", idea)` → seed recipes
- Breakthrough: arxiv for diamagnetic prior art (with fallback to known)
- Integrator / inventor: suggest_inverse_design_components

## Policy Enforcement

See `assert_may_store` + `SourcePolicy` in wissensbasis/store.py.

Live connectors (real arxiv search, patents) go through `tools/` backends (ArxivBackend, etc.) and must be injected (no hard-coded keys).

(Initial autonomous fill 2026-06-24.)