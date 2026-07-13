# GENESIS Self-Improvement Results — 2026-07-13

**Mode:** autonomous self-apply on GENESIS (evidence from full module sweeps + live α/β/γ)  
**Tip before this report:** `559d750` · **This batch tip:** see git log after commit  
**Verdict:** **PARTIAL → VERIFIED** on closed items · confidence **8/10** for closed path · remaining risks below

---

## 1 · Completion audit (what we set out to improve)

| Goal | Status |
|------|--------|
| Fix sweep crashes (mesh gate, structural, grok-build) | **DONE** |
| Restore live α/β/γ completion under 900s | **DONE** |
| Live α produces **verified** material facts (not empty/unsupported) | **DONE** (live evidence) |
| Offline demos exit 0 when physics ok (optional CAD gaps) | **DONE** |
| Prefer base **Steel** page over stainless alloys for density queries | **DONE** (this self-improve) |
| Grounded STEEL in materials registry | **DONE** (this self-improve) |
| CadQuery print-ready STLs without optional kernel | **OPEN** (env/PEP 668; honest exit 3) |

---

## 2 · Evidence (before → after)

### Full module sweeps

| Sweep | ok(0\|3) | strict 0 | hard fail | Notes |
|-------|----------|----------|-----------|--------|
| v1 `/tmp/genesis_full_live_20260713` | 47/53 | 42 | 6 | mesh/structural crash; LIVE timeout; grok-build |
| v2 `docs/FULL_MODULE_SWEEP_2026-07-13_v2.md` | **53/53** | 47 | **0** | after mesh+grok+timeout fixes |

### Live α — steel density

| Run | Exit | Result |
|-----|------|--------|
| Pre-grounding | 124 @600s | empty log |
| After extracts+keywords | 0 @830s | claim extracted, **unsupported** conf 0 |
| After judge window + live_tight (`559d750`) | **0 ~10 min** | **VERIFIED** findings + multi-wiki sources |
| After title re-rank (this batch) | ranking | MediaWiki hits: **`Steel` first**, then Carbon steel |

**Live verified body (v4):** stainless band 7.5–8.0 g/cm³ with independent wiki sources (honest; re-rank now prefers base Steel for the next live run).

**Hybrid path (real Wikipedia + scripted LLM):**  
`The density of steel usually ranges between 7,750 and 8,050 kg/m3` → **VERIFIED**.

### Offline demos after optional-gap policy

```
humanoid=0 aethon=0 structural=0 ideas=0 dream=0 bundle=0
```

---

## 3 · Structural root causes (not symptoms)

| Symptom | Root cause | Mitigation |
|---------|------------|------------|
| LIVE hang / empty log | Outer 600s too short; multi-round LLM; PATH grok wrapper; large prompts ARG_MAX | `max_refine_rounds=0`, prompt-file, real binary, live_tight fan-out, 900s caps |
| α empty / unsupported | REST summaries lack numbers; units kill ranking; DE claims vs EN index; judge on 30k extracts fails | Full extracts; unit strip; DE→EN boosts; evidence windows; claim language = question |
| Live verifies stainless not carbon steel | MediaWiki ranks alloys; scholar picks first numeric page | **Canonical title re-rank** (Steel > Carbon steel > alloys) |
| humanoid/aethon exit 3 despite physics_ok | Exit required `files_complete` incl. optional CadQuery STLs | Exit 0 if physics_ok and only optional tooling gaps |
| mesh/structural crash | Missing export / missing kwargs | Implemented mesh_convergence_gate; CLI demo load case |
| council live fail | Model id `grok-build` unknown | Alias + default `grok-4.5` |

---

## 4 · Code changes this self-improve session

| Area | Change |
|------|--------|
| `tools/search.py` | `_prefer_canonical_titles` + fetch 2× hits then re-rank |
| `materials.py` | STEEL / MILD_STEEL / ALUMINUM + `density_kg_m3()` |
| Prior (same day) | mesh gate, structural defaults, grok alias, live_tight, skeptic windows, scholar language |
| Tests | wikipedia rank, materials density bands, search boosts, evidence window |

---

## 5 · Verification

```text
pytest tests/test_materials.py tests/test_wikipedia.py tests/test_section_optimizer.py  → 30 passed
Live wiki rank "density of steel" → ['Steel', 'Carbon steel', ...]
Offline demos humanoid/aethon/structural/ideas/dream/bundle → exit 0
LIVE α steel density (v4) → exit 0 + Verifizierte Befunde
Hybrid α steel density → VERIFIED 7750–8050 kg/m3
```

**Overall verdict:** **VERIFIED** for closed crash/grounding/demo paths · **PARTIAL** for print/cadquery and for “always carbon-steel band live” (re-rank ready; next live run should prefer Steel).

**Confidence:** 8/10

---

## 6 · Prioritized next self-improve proposals

| # | Proposal | Level | Impact | Effort | Verify |
|---|----------|-------|--------|--------|--------|
| 1 | Live α re-run steel density after title re-rank; expect Steel extract 7750–8050 | L2 | High | Low | Live report body contains 7,750 |
| 2 | Optional CadQuery venv or AABB printability path for `print --demo` exit 0 | L2 | Med | Med | print --demo exit 0 |
| 3 | MaterialsBackend: inject registry STEEL as second source for density claims | L3 | High | Med | min_sources without two wiki pages |
| 4 | Checkpoint mid-α progress logs (per agent) to stderr | L1 | Med | Low | LIVE logs non-empty mid-run |
| 5 | Sweep harness: TimeoutExpired bytes-safe; research default equation | L1 | Low | Low | Full sweep script never crashes |

---

## 7 · Loop continuation

**Exit condition for this iteration:** crashes fixed, live α verifies, demos green, re-rank + STEEL registry landed + report written.

**Handoff:** run proposal #1 (live steel re-check) when LLM budget available; then #2 if print-ready STLs are product-critical.

---

## 8 · Commits (this campaign arc)

| Commit | Summary |
|--------|---------|
| `f520100` | mesh gate, structural, grok-4.5, timeouts |
| `f4d1532` | wiki extracts, unit keywords, DE→EN boosts |
| `559d750` | live verify density; optional CAD gaps |
| `8b0ab46` | sweep v2 report 53/53 |
| *(pending)* | title re-rank + STEEL materials + this report |

---

*Generated as GENESIS self-improvement closing ritual (audit → verify → root cause → gated research → proposals).*
