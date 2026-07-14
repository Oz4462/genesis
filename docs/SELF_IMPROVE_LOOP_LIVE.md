# GENESIS Self-Improve Loop — Live Log

**Started:** 2026-07-13  
**Stop condition:** user says stop  
**Running tip:** see `git log -1`

This file is the **living report**. When the loop stops, it is the source for the final detailed report.

---

## Loop policy

1. Pick highest-leverage friction from sweeps / LESSONS / live evidence  
2. Implement minimal honest fix  
3. pytest + offline demos (and live when budget allows)  
4. Commit + append iteration here  
5. Repeat until user stop  

---

## Iteration 0 — Pre-loop baseline (already on main)

| Item | Result |
|------|--------|
| Sweep v2 | 53/53 ok |
| Live α density | VERIFIED (stainless band first) |
| mesh/structural/grok | fixed |
| Optional CAD demo exits | 0 when physics ok |

Commits: `f520100` … `5dc34ee`, `559d750`

---

## Iteration 1 — Materials registry path + ranking polish

**Goal:** Offline grounded STEEL density + better wiki ranking  

**Done:**
- `MaterialsBackend` (`gen-materials://STEEL`)
- Scholar offline claims from registry (UNVERIFIED until skeptic)
- Wired into `build_live`
- Wikipedia re-rank: demote unrelated titles harder
- Hybrid proof: **2 VERIFIED** claims (registry 7850 + wiki 7750–8050)

**Tests:** `test_materials_backend.py` green  

---

## Iteration 2 — Operator visibility + print fallback + research demo

**Done:**
- Conductor logs scout/scholar/skeptic phases
- `GENESIS_PROGRESS=1` + live auto-enable
- Primitive STL fallback when cadquery missing (CSG still refused)
- `research` bare mode defaults to `(x+1)**2|x**2+2*x+1`

**Verify:** research exit 0; humanoid exit 0; printability tests green  

---

## Iteration 3 — (in progress / next)

- Live steel re-check with materials backend (background)  
- Further noise cuts, cost/timeout tuning  
- More materials (copper, titanium) if needed  

---

## Iteration 5 — Live α WIN: 7850 kg/m³ VERIFIED

**Evidence** `/tmp/loop_live_steel2.out` (~12 min):
- verified=2 gaps=0 sources=5
- STEEL/MILD_STEEL registry 7850 kg/m³ + Wikipedia Steel/Carbon steel corroboration
- Progress logs: scout → scholar (materials claims) → skeptic → gate passed
- Commit follow-up: dedupe MILD_STEEL (`685774a`)

## Iteration 6 — Product surface + smoke

- materials + materials_backend anchored (surface: 31 modules)
- `scripts/self_improve_smoke.sh` offline gate green
- Commits: `8fa449c`, `b15f3e7`, `e7071e9`, `e984d5c`

---

## Cumulative metrics

| Metric | Value |
|--------|--------|
| Hard sweep fails | 0 (v2) |
| Offline demo exits humanoid/aethon/… | 0 |
| Hybrid steel VERIFIED claims | 2 (registry + wiki) |
| Live α steel density | **VERIFIED 7850 kg/m³** + wiki sources |
| Product surface anchored | 31 (+materials) |
| Loop commits | e984d5c → b15f3e7 |

---

## Files touched (loop)

- `src/gen/tools/materials_backend.py` (new)
- `src/gen/agents/scholar.py`, `conductor.py`
- `src/gen/tools/search.py`, `runner.py`, `cli.py`, `pipeline.py`, `materials.py`, `product_surface.py`
- `tests/test_materials_backend.py`, `scripts/self_improve_smoke.sh`
- `docs/SELF_IMPROVE_LOOP_LIVE.md`, `LESSONS.md`, `SELF_IMPROVEMENT_2026-07-13.md`

---

*Loop continues until you say stop…*

## Iteration 3 — Live UnboundLocal fix + Cu/Ti + smoke script

**Bug:** Live report crashed immediately: `UnboundLocalError: os` (nested `import os` in `main()`).

**Done:**
- Removed nested `import os` shadows
- COPPER + TITANIUM in materials registry + backend
- `scripts/self_improve_smoke.sh` offline gate (pytest + CLI demos)

**Verify:** smoke PASS; live re-check in flight (`/tmp/loop_live_steel2.*`)

**Commit:** `e7071e9`

---

## Iteration 4 — Offline smoke automation

**Done:** `scripts/self_improve_smoke.sh` executable and green.

---


## Iteration 5 — Live α WIN: 7850 kg/m³ VERIFIED (materials + wiki)

**Evidence** (`/tmp/loop_live_steel2.out`, ~12 min):
- `verified=2 gaps=0 sources=5`
- Claims: MILD_STEEL + STEEL registry 7850 kg/m³
- Independent sources: Wikipedia Steel, Carbon steel, Stainless steel + gen-materials://
- Progress: conductor scout/scholar/skeptic + materials claims logged
- `gate alpha round=0 passed=True`

**Follow-up:** dedupe MILD_STEEL when query only says "steel" (patch in this iter).

---


## Iteration 7–8 — product_surface, sub-q cap, invent live

- product_surface: gen.materials + materials_backend (31 anchors)
- live_tight: max 3 sub-questions
- tools/__init__ exports MaterialsBackend
- invent --live running in background

### Loop commits since e984d5c

```
5afab54 test: build_live backends include materials_registry
0a2634f perf(self-improve): cap sub-questions to 3 under live_tight α
9caf95d feat(self-improve): export MaterialsBackend; update live loop log with α win
b15f3e7 feat(self-improve): wire materials registry into product_surface
685774a fix(self-improve): dedupe MILD_STEEL on plain steel queries; log live α win
8fa449c chore(self-improve loop): offline smoke script + loop log iter 3-4
e7071e9 fix(self-improve loop): live UnboundLocal os; Cu/Ti materials; loop log
e984d5c feat(self-improve loop): materials backend, α progress, print STL fallback
```

---
*Loop still running — say **stopp** for final detailed report freeze.*

## Iteration 9 — print tooling-gap exit 0 + expanded smoke

**Done:**
- `print --demo`: status `unavailable` for missing cadquery → **exit 0** (tooling gap, not product fail); real `not_printable` still fails
- β/γ/φ: `_emit_progress` after solution/spec/divergence
- Materials: IRON added
- Smoke covers print/bundle/ideas/dream/solve/aethon

**Verify:** `print_exit=0`, `SMOKE PASS` (39 pytest + 11 CLI demos)

---


## Iteration 9 — print exit 0 + full smoke (commit `3df7c0f`)

- print tooling-gap (no cadquery) → exit 0
- IRON material; smoke: 11 demos PASS including print
- β/φ/γ progress emit

## Iteration 10 — aluminum hybrid + solve live

- Hybrid aluminum density → VERIFIED 2700 kg/m³ (registry)
- Live solve (quiet 50kg roller cage): 3 grounded concepts, exit 0
- Live invent (previous): 3 grounded concepts, exit 0

### Tip
`3df7c0f` (+ pending docs)

---
*Loop continues until stop…*

## Iteration 11 — The Well stream-only probe (`6ab2386`)

**Done:**
- `gen.tools.the_well_probe` — catalog + stream probe (max 3 batches)
- CLI `--mode well-probe` (demo = catalog; named dataset = stream if package)
- Product surface anchor; tests green; docs/THE_WELL_PROBE.md
- Policy: never 15TB download; HF stream; honest exit 3 without package

**Verify:**
- `well-probe --demo` → exit 0 catalog
- `well-probe active_matter` without package → exit 3 unavailable
- pytest test_the_well_probe + cli matrix green

---

## Iteration 12 — invent materials prior-art + Well fixture (2026-07-14)

**Done:**
- Mechatronics invent: MaterialsBackend + registry RAG cards (STEEL density etc.)
- `GENESIS_WELL_FIXTURE=1` → status=fixture, exit 0, zero fake tensors
- CLI well-probe treats fixture as success (offline CI path)
- STATUS 2026-07-14 continue note

**Verify:** invent --demo 0; invent loop tests; well fixture exit 0; unavailable without package still 3

---

## Iteration 13 — invent novelty_gate wired (2026-07-14)

**Bug:** Materials/RAG prior-art backends existed but invent CLI never passed `novelty_gate` → search never ran.

**Done:**
- `build_novelty_gate(domain.prior_art_sources())` on invent/solve CLI
- Live invent: OpenAlex + materials + RAG
- Print `novelty=` + abgelehnte nicht_neu concepts
- invent --demo: novelty=neu, Quellen up to 2

**Verify:** invent/solve --demo exit 0; inventor tests green

---

## Iteration 13 — invent novelty_gate CLI wiring (`8dadbc2`)

**Bug:** Materials/RAG backends existed but invent CLI never passed `novelty_gate`.

**Done:**
- Wire `build_novelty_gate(domain.prior_art_sources())`
- Live invent: OpenAlex + materials + RAG
- CLI shows novelty= + rejected concepts
- invent --demo: novelty=neu, Quellen 1–2

**Live invent** (`leises 50kg Rollenlager aus Stahl und PETG`):
- 3 proposed, 3 grounded, Pareto 1
- novelty=**neuer_mechanismus**, Quellen=4, verifiziert=True
- Steel races + PETG cage damping concept

**Smoke:** PASS (47 pytest + 12 CLI demos)

---

## Iteration 14 — invent γ+ bridge + thermal δ overtemperature recipe (2026-07-14)

**Friction:**
1. CLI printed `Pareto-Front (γ+): (not attached or empty — honest)` — `InventionRun` never built a HORIZON `ParetoFront`.
2. Thermal invent always **vacuous δ** — `overtemperature` validator existed but was `MANUAL_ONLY` without a `CheckRecipe`, while `scripted_thermal_architect` already emitted matching measurands.
3. Thermal domain lacked materials prior-art parity; MaterialsBackend ignored bare metal names (`copper` alone).

**Done:**
- `inventions_to_pareto_front()` → `InventionRun.pareto_front` with `produced_by=inventor.score_proxy` (honest proxy objectives, not quantity-id recompute)
- CLI prints `cands/evaluated/gaps by=inventor.score_proxy`
- `CheckRecipe` **overtemperature (1-D conduction)**; removed from `MANUAL_ONLY_VALIDATORS`
- ThermalDomain: RAG materials cards + `MaterialsBackend`; live OpenAlex for thermal invent (parity)
- MaterialsBackend property gate: copper/titanium/iron/abs tokens
- Tests: γ+ bridge, thermal prior-art, domains materials list; fix mechatronics prior-art expectation

**Verify:**
- invent --demo: γ+ cands=2 evaluated=2 by=inventor.score_proxy
- invent "Kühlung für 1kW Chip": **2 physik-verifiziert** (was 0), γ+ attached
- SMOKE PASS (47 pytest + 12 CLI)

---

## Iteration 15 — thermal performance axis on 5-score (2026-07-14)

**Friction:** Thermal invents scored `performance=1.0` (neutral) because only modal margin existed — γ+/Pareto could not rank better cold-plates.

**Done:**
- `_thermal_margin_ratio`: Fourier ΔT = P·L/(k·A), performance = max_service/peak (same path as overtemperature_check)
- `_performance`: modal if resonance present, else thermal ratio, else neutral 1.0
- Test: default copper plate ratio ≈ 373.15/326.15

**Verify:** invent thermal still 2 grounded; score test green; SMOKE PASS

---

## Iteration 16 — smoke covers thermal invent + inventor suite (2026-07-14)

**Done:**
- `self_improve_smoke.sh`: pytest adds inventor score/loop/domains
- Explicit **invent thermal** CLI check: ≥1 grounded + `by=inventor.score_proxy` (guards vacuous-δ regression)

**Verify:** SMOKE PASS — 71 pytest + 12 demos + invent-thermal OK

---

## Iteration 17–18 — full-power: materials k + δ recipes + TE2 refine in loop (2026-07-14)

**Friction:**
1. Thermal k was a magic `400` in architect; registry had no thermal conductivity
2. `plate_bending`, `contact`, `thermal_mismatch` still MANUAL_ONLY despite closed-form validators
3. `refine_invention` (TE2) tested in evolve tests but **never wired** into `run_invention` / invent CLI

**Done:**
- `Material.thermal_conductivity_w_mk` (Cu 401, Al 205, steel 50, FDM ~0.1–0.25) + `thermal_conductivity_w_mk()`
- Thermal architect defaults to registry COPPER k; prior-art cards include k
- MaterialsBackend: conductivity tokens + k in relevance / claim text
- CheckRecipes: plate bending, contact pressure, thermal mismatch (bonded bars)
- `run_invention(..., architect_for_round=, max_refine_rounds=)` on δ-fail
- `thermal_strengthening_schedule`; invent CLI max_refine=3 mechatronics+thermal
- Tests: materials k, plate/contact/mismatch select, loop refine recovery

**Verify:** 86 focused pytest; SMOKE PASS (73+ demos + invent-thermal)

---

## Iteration 19 — bolted_joint + fracture recipes + KIc unit (2026-07-14)

**Done:**
- CheckRecipes: `bolted_joint`, `fracture` (LEFM)
- units: opaque atom `KIc` (MPa·√mm numerically) + scale 1.0 — integer exponents cannot express √L
- invent CLI prints TE2-Refine line when any concept was refined
- MANUAL_ONLY now only: `creep`, `montecarlo_uncertainty`

**Verify:** physics_selection gate pass for bolt+fracture specs; SMOKE PASS

---

## Iteration 20 — smoke expands physics suite; MANUAL_ONLY near-empty (2026-07-14)

**Done:**
- Smoke pytest includes `test_physics_selection` + `test_physics_validation` (**119** passed)
- Validator coverage: **44 recipes**, MANUAL_ONLY only `creep` + `montecarlo_uncertainty`
- Copper hybrid anchors: ρ=8960 kg/m³, k=401 W/m·K via MaterialsBackend

**Verify:** SMOKE PASS

---
