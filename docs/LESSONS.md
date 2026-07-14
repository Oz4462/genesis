# GENESIS LESSONS

Causal log (self-improvement protocol). Newest first.

## 2026-07-14 — full-power invent/thermal + MANUAL_ONLY recipes + TE2 wire

- **Verdict:** VERIFIED
- **Worked:**
  - Registry `thermal_conductivity_w_mk` ends magic `400` in thermal architect
  - `overtemperature` / `plate_bending` / `contact` / `thermal_mismatch` recipes auto-select from measurands
  - TE2 `refine_invention` only helps when **wired into the invent loop** (tests alone ≠ product)
  - Thermal invent: 0→2 grounded after overtemperature recipe; γ+ score_proxy attached
- **Failed / friction:**
  - fracture stays MANUAL_ONLY: `MPa*sqrt(mm)` not in units parse table
  - First invent ground can pass while refine schedule never runs (OK — refine is fail-path only)
- **Root cause:** Validators existed without CheckRecipe (same class as overtemperature vacuous δ); TE2 module orphaned from `run_invention`
- **Mitigation:** recipe + remove from MANUAL_ONLY; loop hook `architect_for_round` + CLI schedules
- **Lesson:** A validator without a measurand recipe is invisible to invent/spec δ — product looks "vacuous" while the math is fine. Optional modules (refine, novelty, materials backends) must be **CLI-wired** or they are dead code.
- **Operators:** recipe-or-manual-only, wire-to-edge, registry-over-magic-number

## 2026-07-13 — full module sweep + live α grounding + self-improve

- **Verdict:** VERIFIED (confidence 8/10) for crash/demo/live-verify path; PARTIAL for print/cadquery
- **Worked:**
  - Full extracts + unit-free keywords surface Steel density text
  - Judge evidence windowing stops conf=0 from LLM timeouts on 30k pages
  - live_tight fan-out finishes α under ~900s
  - Optional CAD gaps no longer hard-fail physics-ok demos
  - Hybrid α proves 7750–8050 kg/m³ VERIFIED end-to-end
- **Failed / friction:**
  - Live α first verified stainless band (7.5–8.0 g/cm³) not carbon-steel kg/m³
  - Full wiki extracts slow multi-LLM pipelines
  - CadQuery uninstallable system-wide (PEP 668)
- **Root cause:**
  - Discovery ranked *alloys* and generic Density above base **Steel**
  - Judge saw entire article → transport/timeout → silent irrelevant
  - Exit codes conflated optional tooling with product failure
- **Mitigation:**
  - Wikipedia `_prefer_canonical_titles` re-rank
  - `_evidence_for_judge` windows + skip reformulation when EN boosts exist
  - `_bundle_demo_ok` / optional tooling gap policy
  - STEEL in materials registry for offline δ-path
- **Component:** `tools/search.py`, `agents/skeptic.py`, `agents/scholar.py`, `runner.py`, `cli.py`, `materials.py`
- **Lesson:** Anti-hallucination needs *retrieval geometry* (which page, how much text, which language) as much as gates; optional tooling absence must be a gap, not a crash.
- **Operators:** retrieve-rerank, evidence-bound, fail-loud-optional, registry-grounding

## 2026-07-13 — live CLI model id drift

- **Verdict:** VERIFIED
- **Failed:** LIVE-council `unknown model id grok-build`
- **Root cause:** Product nickname left as default after CLI catalog changed to `grok-4.5`
- **Mitigation:** Alias map + default_council/GrokCLI default `grok-4.5`
- **Component:** `llm/grok_cli.py`, `discovery/symbiosis.py`
- **Lesson:** Live model ids must be validated against `grok models` / vendor catalog at the edge.
