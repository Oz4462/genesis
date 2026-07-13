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

