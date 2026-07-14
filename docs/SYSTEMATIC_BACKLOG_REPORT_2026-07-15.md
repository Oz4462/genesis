# GENESIS — Systematischer Backlog-Bericht + Abarbeitungsplan

**Datum:** 2026-07-15  
**Tip bei Erstellung:** siehe `git log -1` (`main`)  
**Methode:** Code-Evidenz (Import, Zeilenzahl, Live-Probe `process_dream` / `horizon-full`), kein Doc-Overclaim  
**Zweck:** Alle genannten offenen Kategorien ehrlich einordnen und **nacheinander** abarbeitbar machen  

---

## 0. Leitprinzipien (für jede Iteration)

1. **Ein Sprint = ein messbarer Stein** (Tests grün + Smoke + Commit + Docs-Update)  
2. **First-stone ≠ fertig** — Status immer: `exists` / `wired` / `depth` / `production`  
3. **Keine erfundenen Messdaten** — private Lab / 15 TB Well / unkeyed APIs bleiben ehrlich gated  
4. **Agent-sourced public data** (OpenAlex, Wikidata, arXiv…) — User liefert keine Ledgers  
5. **Doc-Sync** am Ende jedes Sprints: `STATUS.md` + dieser Report + betroffene OPEN/HORIZON-Zeilen  

**Depth-Skala**

| Level | Bedeutung |
|-------|-----------|
| L0 | Doc-only / kein Modul |
| L1 | Datei existiert (skeleton / first stone) |
| L2 | Getestet, offline nutzbar, ehrliche Gaps |
| L3 | In LUMEN/CLI/Bundle verdrahtet |
| L4 | Produktions-/Sign-off-Niveau (selten) |

---

## 1. Executive Summary

| Kategorie | Claim „offen“ | Evidenz-Korrektur | Strategische Priorität |
|-----------|---------------|-------------------|------------------------|
| **1 HORIZON** | ζ/Ω/δ⁺ dünn, Doc-Drift | **Bestätigt für Tiefe.** Ω *enforce* ist da; **Subgates ε/ζ/γ⁺/cov oft `None`**, `memory_fabric`/`seam` oft unattached | **P0** |
| **2 CAD/PRINTFORGE** | CNC/Laser/PCB, multi-axis, Full Package | **Bestätigt.** Module da (L1–L2); FDM starker; Rest Stubs/Gaps | **P0/P1** |
| **3 Wissensbasis/Live** | full connectors, qdrant prod | **Teilweise.** OpenAlex/arXiv/Patents existieren; prod vector/live tables dünn | **P1** |
| **4 Simulation/Caps** | multi-physics closed-loop, full caps | **Teilweise.** Caps exist + partial Assessment; closed-loop nicht L4 | **P1/P2** |
| **5 Sonstiges** | fracture NotImplemented, grenz depth | **fracture:140 veraltet** (Paris m=2 implementiert); grenz/doc-sync real | **P2** |

**Wichtig:** Fast nichts ist „nur Doc ohne Datei“. Offen ist **Produkt-Tiefe (L3–L4)**, nicht Existenz.

---

## 2. Kategorie 1 — HORIZON-Bogen (P0)

### 2.1 ζ `memory_fabric`

| | |
|--|--|
| **Datei** | `src/gen/memory_fabric.py` (~234 LOC) |
| **API** | `build_memory_fabric_certificate`, `gate_zeta`, Deposits/Recalls types |
| **Level** | **L1–L2** (Gate-Logik), **nicht L3 consumer-full** |
| **Live-Probe 2026-07-15** | `process_dream("steel bracket 100N")` → `memory_fabric is None` |
| **Offen** | Richer population (deposits from claims/runs), dynamics/health over time, **attach in LUMEN return + RunState**, gate_zeta surface in `horizon_subgates.zeta` ≠ `None` |

### 2.2 Ω Exoskelett

| | |
|--|--|
| **Datei** | `src/gen/omega.py` (~518 LOC) + LUMEN wiring |
| **Bereits geschlossen** | `gate_omega`, `build_omega_certificate`, **`enforce_omega=True` default** (commit `c920b37`), `horizon-full` enforced path (`771cd80`) |
| **Live-Probe** | `Ω.passed=True (enforced)`; subgates `epsilon/zeta/gamma_plus/coverage = None`, only `omega=True` |
| **Offen** | Full subgate attach (ε/ζ/γ⁺/δ⁺ coverage) **before** Ω; dynamic learning notes from real failures; E2E cert chain assertions in tests; no silent `None` subgates when builders exist |

### 2.3 δ⁺ Reality ingest

| | |
|--|--|
| **Datei** | `src/gen/reality.py` (~144 LOC) |
| **API** | `evaluate_reality`, `gate_delta_plus`, `Measurement`, `FalsificationExperiment` |
| **Level** | **L2** honest abstention when no measurement |
| **Live-Probe** | `δ⁺=inconclusive` (korrekt, keine Messung) |
| **Offen** | **Live ingest path** (CSV/sensor/fixture → `Measurement` → non-inconclusive when real data present); external lab seams; never invent readings |

### 2.4 Doc-Sync HORIZON-Tabelle

| | |
|--|--|
| **Problem** | STATUS/Council-Texte „HORIZON complete“ vs. first-stone Subgates `None` |
| **Offen** | Tabelle in `docs/HORIZON.md` + `STATUS.md`: pro Gate **Level L0–L4** + Evidence-Commit; keine „✓ bewiesen“ ohne `horizon-full`/pytest Anker |

### Sprint-Ziele Cat1 (sequenziell)

| Sprint | Ziel | Done-Kriterium |
|--------|------|----------------|
| **H1** | ζ attach in LUMEN | **DONE** `a6c59c3` — import split; `memory_fabric` + zeta=True |
| **H2** | ε/coverage/γ⁺ attach | **DONE** `a6c59c3` — all subgates True |
| **H3** | Ω notes from real subgate set | **DONE** `9959bea` — receipts ε/ζ/γ⁺/coverage |
| **H4** | δ⁺ ingest fixture | **DONE** `a3128bf` — fixture → corroborated |
| **H5** | Doc-Sync HORIZON | **DONE** — STATUS/HORIZON L-levels (no overclaim) |

---

## 3. Kategorie 2 — CAD / Fertigung / PRINTFORGE / Realisierung (P0/P1)

### 3.1 Inventar (existiert)

| Modul | LOC (ca.) | Level | Residual |
|-------|-----------|-------|----------|
| `cad/manufacturing_check.py` | 457 | L2 FDM; L1 CNC/Laser/PCB | Viele `_gaps` / ProcessDFM Stubs |
| `dfm.py` | 266 | L2 | Nicht alle Prozesse |
| `cad/cost_model.py` | 175 | **L2 FDM only** | CNC/Laser/PCB costs = **gaps by design** (docstring) |
| `cad/gcode.py` | 400 | L2 profile + rect pocket | Kein multi-axis / full 3D / slicer |
| `pipelines/fertigungs.py` | 205 | L1–L2 | datei/toolpath gaps |
| `cad/kicad.py` + `kicad_cli.py` | 291+205 | L1–L2 skeleton | Full copper/DRC external |
| `electronics.py` | 1156 | L2 rich internal | `route_harness` thin; kicad stub helpers |
| `pipelines/integrator.py` | 1609 | L2–L3 mini package | Full BOM/harness/drawings/persist |
| CadQuery bridge / `.venv-cad` | — | **L3** print path | Multi-part STL opt-in |

### 3.2 Claims vs. Evidence

| Claim | Verdict |
|-------|---------|
| CNC/Laser/PCB ProcessDFM unvollständig | **Wahr** (explizite stubs/gaps im Code) |
| cost_model nur FDM voll | **Wahr** (`estimate_fdm_cost` only) |
| gcode nur 2.5D + pocket angefangen | **Wahr** (`generate_profile_gcode`, `generate_rect_pocket_gcode`) |
| Full Realisierungspaket | **Wahr als L4-Lücke**; mini/realize **existiert** |
| Assembly/STEP Produktionsniveau | **Wahr offen** |

### Sprint-Ziele Cat2

| Sprint | Ziel | Done-Kriterium |
|--------|------|----------------|
| **C1** | CNC ProcessDFM rules (sourced gaps honest) | `manufacturing_check` CNC path: pass/fail + tests, no fake costs |
| **C2** | Laser + PCB process rules (minimal set) | same pattern; tests |
| **C3** | `estimate_cnc_cost` / laser ranges | ranged + gaps API parity with FDM; tests |
| **C4** | GCode: second real feature (e.g. facing or slot) | emit + `verify_gcode` + fertigungs wire |
| **C5** | BOM mech+elec structure in realize package | JSON schema + integrator emit + test |
| **C6** | Harness/netlist package section | structured artifacts or explicit gap list |
| **C7** | Drawings non-stub path OR honest “drawing_gap” | no silent empty files |
| **C8** | PRINTFORGE inventory doc sync | `PRINTFORGE_INVENTORY.md` = code truth |

---

## 4. Kategorie 3 — Wissensbasis / Live Layer (P1)

| Baustein | Status | Level | Offen |
|----------|--------|-------|-------|
| OpenAlex | live keyless | L3 | — |
| PatentsView | key-gated | L2 | key + probes |
| arXiv backend | exists | L2–L3 | query richness |
| Wikidata density | live VERIFIED path | L3 | more props |
| Materials registry | offline | L3 | — |
| `external/registry.py` | exists | L1–L2 | full SourceConnectorRegistry UX |
| Component/supplier connectors | partial | L1 | seeding + live |
| Improvement recipes | partial invent/δ | L2 | electronics-rich recipes |
| Ledger postgres | exists | L2 | production tables |
| pgvector / qdrant | partial/vendor | L1 | **live production pending** |
| Community evidence | OpenAlex agent-sourced | L3 offline/live flag | literature≠field |

### Sprint-Ziele Cat3

| Sprint | Ziel | Done |
|--------|------|------|
| **W1** | Registry catalog of all connectors + health probe CLI | one command lists backends + live/offline |
| **W2** | Electronics component seed pack | N recipes + invent/prior-art use |
| **W3** | Patents live path documented + skip-without-key | tests |
| **W4** | Ledger schema migration notes + smoke | `scripts/postgres_smoke` green or honest skip |
| **W5** | Vector store: one production path OR explicit “not wired” | no half-claims in STATUS |

---

## 5. Kategorie 4 — Simulation / Co-Design / Platform Caps (P1/P2)

| Baustein | Status | Offen |
|----------|--------|-------|
| Multi-domain in LUMEN | pieces exist | closed-loop mech+therm+elec+control not L4 |
| mesh_convergence / refs | first-stone | fuller reference cases |
| ProofPackage | exists + LUMEN/assess | deeper package contents |
| ReadinessLadder | L2–L3 | TRL only with real evidence |
| TeacherMode | L3 in LUMEN | richer notes from failures |
| CommunityEvidence | agent OpenAlex | store/persist agent cache optional |
| Assessment/Bundle/CLI caps | partial | 100% depth in all modes |

### Sprint-Ziele Cat4

| Sprint | Ziel |
|--------|------|
| **S1** | Caps surface matrix: which CLI modes show proof/readiness/teacher/community |
| **S2** | One closed-loop mini co-sim receipt (therm+mech) with provenance |
| **S3** | mesh_convergence_gate + 2 more reference cases |
| **S4** | Bundle MANIFEST always lists caps honestly (present/absent) |

---

## 6. Kategorie 5 — Sonstige Lücken (P2)

| Claim | Evidence 2026-07-15 |
|-------|---------------------|
| `fracture.py:140 NotImplemented` | **VERALTET** — Zeile 140 ist Paris m=2 closed form (`math.log(...)`); kein NotImplemented |
| `learning_integrator` richer | Datei ~179 LOC, L2 — Vertiefung offen |
| `boundary_reviser` full | ~174 LOC, L2 — Vertiefung offen |
| Doc-Sync HORIZON/BUILD_LOG/DOC_CODE_DRIFT | **offen** (Council vs. first-stone Drift) |
| Owner-gated live runs | **by design** (`GENESIS_ALLOW_LIVE`) — kein Bug |
| Production Wissensbasis | partial — siehe Cat3 |

### Sprint-Ziele Cat5

| Sprint | Ziel |
|--------|------|
| **X1** | Remove stale “NotImplemented” claims from docs |
| **X2** | learning_integrator: one richer cycle test + wire note |
| **X3** | boundary_reviser: one full revision path test |
| **X4** | Doc-sync pass after every P0 sprint (H*/C*) |

---

## 7. Bereits geschlossen (nicht erneut als „offen“ führen)

| Item | Evidence |
|------|----------|
| CadQuery PEP 668 + `.venv-cad` bridge | `docs/CADQUERY_VENV.md` |
| Ω `enforce_omega=True` default | LUMEN + tests integrity |
| `horizon-full` CLI + LUMEN surface | `gen.horizon_full`, mode in `cli.py` |
| Community evidence agent-sourced | OpenAlex; `user_data_required=False` |
| Rect pocket GCode | `generate_rect_pocket_gcode` |
| Materials k / thermal invent plate_k | smoke invent-thermal |
| Wikidata density live path | α copper VERIFIED history |
| Paris m=2 fracture closed form | `fracture.py` |

---

## 8. Sequenzieller Master-Plan (Abarbeitung)

Reihenfolge ist **strategisch** (HORIZON Vertrauen → Produkt CAD → Wissen → Sim → Polish).

```
Phase A — HORIZON Trust (Cat1)
  H1 ζ attach → H2 subgates → H3 Ω receipts → H4 δ⁺ fixture → H5 Doc-Sync
Phase B — PRINTFORGE Core (Cat2 partial)
  C1 CNC DFM → C2 Laser/PCB DFM → C3 multi-process cost → C4 GCode feature
Phase C — Realization Package (Cat2 rest)
  C5 BOM → C6 harness/netlist → C7 drawings honesty → C8 inventory sync
Phase D — Live Knowledge (Cat3)
  W1 registry → W2 seeds → W3 patents → W4 ledger → W5 vector honesty
Phase E — Sim & Caps depth (Cat4)
  S1 matrix → S2 co-sim → S3 mesh refs → S4 bundle caps
Phase F — Cleanup (Cat5)
  X1–X4 continuous with each phase end
```

### Stop / Freeze Regeln

- User sagt **stopp** → Freeze-Report + tip commit  
- Jeder Sprint: pytest der berührten Suite + mind. 1 CLI smoke  
- Kein Sprint endet mit „✓ complete“ ohne Evidence-Zeile  

### Effort-Richtwerte (grob, agent-days)

| Phase | Sprints | Grob |
|-------|---------|------|
| A HORIZON | H1–H5 | 3–5 |
| B PRINTFORGE core | C1–C4 | 4–6 |
| C Realization | C5–C8 | 4–6 |
| D Knowledge | W1–W5 | 3–5 |
| E Sim/Caps | S1–S4 | 3–4 |
| F Cleanup | laufend | +1 |

**Gesamt:** ~20–30 fokussierte Sprints bis L3-„product honest complete“ — **nicht** L4 physische Fabrik.

---

## 9. Nächster konkreter Schritt (Start)

**Sofort startbar: Sprint H1 — ζ memory_fabric attach**

1. In `lumencrucible.process_dream`: nach Claims `build_memory_fabric_certificate` + `gate_zeta`  
2. In Return: `memory_fabric`, `horizon_subgates.zeta`  
3. Test: `test_lumen_memory_fabric_attached`  
4. `horizon-full` surface zeigt `zeta` ≠ None  
5. Docs: eine Zeile in STATUS + diesem Report „H1 done“  

Danach H2 ohne Pause, bis Phase A grün.

---

## 10. Checkliste „Owner-gated / never fake“

| Thema | Policy |
|-------|--------|
| Live LLM | `GENESIS_ALLOW_LIVE=1` |
| Community OpenAlex | `GENESIS_COMMUNITY_LIVE` / `ALLOW_LIVE` |
| PatentsView | API key |
| δ⁺ real lab | Measurement object — never invent |
| The Well | stream/probe only, no 15 TB |
| Trustcore private | optional companion |
| User data | **not required** for public TRL steps |

---

## 11. Referenzen (Code-Anker)

- `src/gen/memory_fabric.py`  
- `src/gen/omega.py`  
- `src/gen/reality.py`  
- `src/gen/grenzverschiebung/lumencrucible.py`  
- `src/gen/horizon_full.py`  
- `src/gen/cad/manufacturing_check.py`, `cost_model.py`, `gcode.py`  
- `src/gen/electronics.py`, `src/gen/pipelines/integrator.py`  
- `docs/OPEN_MODULES_FULL_LIST.md`, `docs/HORIZON.md`, `docs/STATUS.md`  
- `docs/integration/PRINTFORGE_INVENTORY.md`  

---

*Dieser Report ist die SSOT für die sequenzielle Abarbeitung ab 2026-07-15. Nach jedem Sprint: Abschnitt 8 abhaken + Evidence-Commit.*
