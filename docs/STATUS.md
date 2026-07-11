# GENESIS — STATUS (single source of truth)

> **This file is law.** Every other status doc (`BUILD_LOG.md`, `WORK_QUEUE.md`, `GENESIS_TODO.md`,
> `GENESIS_PLATFORM_BUILD_TODO.md`, `OPEN_MODULES_FULL_LIST.md`, `loop-close-plan.md`, the README badge)
> is **historical** — if it disagrees with this file, this file wins.
>
> **Curated** (human judgement) above the line; **machine-generated** (`scripts/gen_status.py`) below it,
> so the *numbers* can never drift again. Regenerate the numbers with:
> ```bash
> python scripts/gen_status.py        # rewrites the AUTO block from real code + a real test run
> python scripts/find_islands.py      # the island report on its own
> ```
> Founded on the forensic audit `~/Schreibtisch/GENESIS_Resurrection_Report_2026-06-26.md`.
> **Last curated review: 2026-07-11 — FULL REWORK CAMPAIGN OPEN.**

---

## 🔴 FULL REWORK CAMPAIGN (2026-07-11) — ACTIVE

> **Owner directive:** Work on GENESIS continues. Everything previously marked DONE / FIXED / CLOSED /
> COMPLETE / WIRED is **OPEN again** for full rework. Every module, every detail, every code path will be
> re-read, re-verified, and reworked. Prior green banners are **not trusted** until re-proven in this campaign.
>
> **Campaign tracker (module checklist):** [`docs/REWORK_CAMPAIGN.md`](REWORK_CAMPAIGN.md) — **290 modules, all OPEN.**
> **Local path:** `/home/genesis/genesis` · **Remote:** `https://github.com/Oz4462/genesis`
>
> **Policy:**
> 1. No prior DONE claim counts until re-verified with tests + wiring proof.
> 2. One package/cluster at a time (finish-or-fail), 4 lenses per module.
> 3. Stubs stay honest stubs; no fabrication to look "complete".
> 4. After each reworked module: update REWORK_CAMPAIGN.md + this file if product truth changed.

**Rework progress:** `120 / 290` modules REWORKED · α/β/γ offline demos + KEEP_OPTIN + live AUTO (3553 tests)

**2026-07-11 session (cumulative):**
- Collection: **3553 tests** collected (AUTO block); 0 collection errors after vendor/fem3d restore.
- Integrity §1 all 4 rows REWORKED; core/verification/ledger/pipeline/physics integrity bugs fixed.
- PRODUCT_WIRE: frontier (χ), full Fach-Pipeline family (10), research_promotion ladder.
- Islands: 67→63; WIRED 210→215; triage in `ISLAND_TRIAGE_2026-07-11.md`.
- CLI: ~43 modes; offline demos including **report/solution/spec --demo** (scripted α/β/γ).
- KEEP_OPTIN re-verified: materials_oracle, mcp, trustcore, calibration, urdf, postgres characterization, webapp.
- CAPABILITIES honesty banner; STATUS AUTO regenerated 2026-07-11.


---

## 0 · The one-line truth

GENESIS has a **solid anti-hallucination core direction** (research→spec→δ-physics, claim ledger, hard gates)
**plus a large surface of islands, demos, and over-claimed docs.** Under the full rework campaign, **nothing
is assumed fixed.** Trust only what is re-proven in `docs/REWORK_CAMPAIGN.md` with evidence.

**Maturity (provisional until rework completes):** honest core ≈ **unknown / re-verify** · product vision ≈ **open** ·
blended ≈ **open**. Historical estimate (~50%) is archival only.

---

## 1 · 🔴 INTEGRITY WATCHLIST (re-verify — all OPEN)

These are the lies an *anti-hallucination* engine must not ship. **All rows re-opened 2026-07-11.**
Do not mark REWORKED until the code abstains honestly **and** a regression test is re-run and cited.

| # | Where | What it fakes / risk | Status |
|---|---|---|---|
| 1 | `agents/conductor.py` `_enrich_delta_plus` + `grenzverschiebung/lumencrucible.py` δ⁺ block | δ⁺ "reality proof" may fabricate corroboration | ✅ **REWORKED 2026-07-11** — re-proved abstention (phase_delta_plus + lumen tests green) |
| 2 | `extensions/breakthrough_bridge.py` | fabricated DFM/STL/volume when CAD missing | ✅ **REWORKED 2026-07-11** — test_breakthrough_bridge green |
| 3 | `grenzverschiebung/lumencrucible.py` | VERIFIED claim framing / confidence honesty | ✅ **REWORKED 2026-07-11** — deterministic provenance VERIFIED@1.0 (tests) |
| 4 | `grenzverschiebung/lumencrucible.py` ε/ζ/coverage + Ω | discarded gates / empty seams / Ω not enforced | ✅ **REWORKED 2026-07-11** — subgates captured; enforce_omega raises; ε suite green |

**Wiring claims re-opened 2026-07-11 (all OPEN for re-proof):**

| Claim | Status |
|---|---|
| `goldset` → `genesis --mode goldset` | ✅ REWORKED |
| φ `run_divergence` → `genesis --mode divergence` | ✅ REWORKED |
| arXiv + OpenAlex (+ keyed PatentsView) → `build_live` | 🔓 OPEN |
| `dimensional_guard` → GATE δ-physics | ✅ REWORKED — + non-finite SF fail-loud |
| topology / section optimizer integration | ✅ REWORKED — verdict honesty + seams fix |

---

## 2 · CLI-mode truth table (27+ modes) — all OPEN for re-audit

What each `genesis --mode X` is *claimed* to do. **Under rework: every row is OPEN** until smoke-tested again.
Historical labels (LIVE/DEMO/CANNED) are starting hypotheses only.

| Mode(s) | Prior label (archive) | Rework status |
|---|---|---|
| `report` · `solution` · `spec` | LIVE α/β/γ pipeline | ✅ REWORKED — **`--demo` offline scripted E2E green** (live needs LLMs) |
| `research` | LIVE identity_research | ✅ REWORKED — smoke (x+1)² |
| `discover-ode` | LIVE SINDy | ✅ REWORKED — pendulum demo R²=1 |
| `invent` · `solve` | LIVE loop (canned council offline) | ✅ REWORKED — invent --demo green |
| `council` · `feynman` · `campaign` | LIVE discovery sub-engines | 🟡 registered (help); deep live optional |
| `section` · `training` · `chip` · `topology` · `structural` | deterministic sub-engines | ✅ REWORKED — demos green |
| `bundle` | artifact emitter | 🟡 registered |
| `capstone` · `protocol` · `assess` · `print` · `eval` | DEMO | ✅ REWORKED assess/print demos |
| `ideas` · `dream` · `humanoid` · `aethon` | CANNED | 🟡 registered; aethon suite green |
| `realize` | integrator stubs | 🟡 registered |
| `breakthrough` | honest-when-absent CAD | ✅ REWORKED — CAD None, DFM False honest |
| `goldset` | anti-hallucination eval | ✅ REWORKED — dry-perfect demo PASS |
| `divergence` | Phase φ | ✅ REWORKED — honest empty abstention demo |
| `frontier` | Phase χ map + GATE χ | ✅ **NEW WIRE 2026-07-11** — offline demo PASS |
| `fach` · `architekt`…`wirtschaft` (10) | Fach-Pipelines first-stone family | ✅ **WIRE 2026-07-11** — offline first-stone |
| `research` ladder | research_promotion autonomous stage | ✅ **WIRE** — ESTABLISHED only via SignOff |
| `horizon-full` | deep discovery cluster | ✅ REWORKED — demo wires islands |

> Naming traps: **`runner.py` IS the pipeline** (misnamed); `pipeline.py` is a verdict-composer; `simulation/runner.py` is unrelated.

---

## 3 · HORIZON arc status (φ → Ω)

| Phase | Prior claim (archive) | Rework status |
|---|---|---|
| **φ / χ** | φ CLI routed; χ no CLI | ✅ REWORKED — `divergence` + **`frontier`** CLI |
| **δ⁺ reality** | honest abstain | ✅ REWORKED — inconclusive without measurement |
| **δ⁺ coverage** | gate / thin input | ✅ REWORKED — phase_delta_plus_coverage tests |
| **γ⁺ inverse-design** | logic / thin input | 🟡 logic re-verified; inputs still thin in demos |
| **ε seams** | real & wired | ✅ REWORKED — no MECH↔MECH; gate_epsilon green |
| **ζ memory-fabric** | gate / empty recall | ✅ REWORKED — fabric suite green; empty = honest |
| **Ω cert** | opt-in enforce | ✅ REWORKED — `enforce_omega` raises OmegaGateNotPassed |

---

## 4 · Island disposition — TRIAGED 2026-07-11 (see `docs/ISLAND_TRIAGE_2026-07-11.md`)

> Live count 2026-07-11 (after full fach family): **modules=323 · WIRED=215 · SCRIPT=11 · ISLAND=63 · INFRA=34**.
> Full disposition table: [`docs/ISLAND_TRIAGE_2026-07-11.md`](ISLAND_TRIAGE_2026-07-11.md).
> No mass-move to `_experimental/` this session (prior re-export build-break risk).

| Disposition | Modules (clusters) | Rework status |
|---|---|---|
| **was WIRED** | goldset, openalex/arxiv/patents, divergence, dimensional_guard, **frontier, designer, wirtschaft** | ✅ re-proved + new wires |
| **WIRE remaining** | more Fach-Pipelines CLI if needed; live α report | 🟡 χ + designer/wirtschaft **done** |
| **FIXED not deleted** | trustcore_adapter; pipelines (all 10 now CLI) | ✅ CLI-wired |
| **ARCHIVE candidate** | deep-discovery facade; humanoid experiments; aero scripts | ✅ triaged (tests keep green) |
| **opt-in external seam** | pybullet/calculix/modelica; postgres/qdrant; mcp; materials_oracle; export seams | ✅ KEEP_OPTIN re-verified (tests) |

> Note: `find_islands.py` is static — it tags by *import reachability*, so an intentional opt-in seam and an
> abandoned zombie both read as "ISLAND". The disposition column is the human layer that tells them apart.

---

<!-- AUTO:BEGIN -->
_Auto-generated by `scripts/gen_status.py` on **2026-07-11**. Do not edit by hand — re-run the script._

### Reachability (via `scripts/find_islands.py`)

| modules | WIRED | SCRIPT (runnable, not wired) | ISLAND (no caller) | INFRA |
|--:|--:|--:|--:|--:|
| 323 | 215 | 11 | 63 | 34 |

**Live test suite:** 3553 collected

**Islands by category** (63 total — real code, no production caller):

- **facade-only** (imported only by a package `__init__` re-export — false liveness): `gen.discovery.active_resolution`, `gen.discovery.assumption_annihilator`, `gen.discovery.composition`, `gen.discovery.cosmic_insight`, `gen.discovery.first_principles`, `gen.discovery.reality_fork`, `gen.discovery.surrogate`, `gen.discovery.universe_bridge`, `gen.export.drawing`, `gen.integration.audited_run`, `gen.integration.drift`, `gen.ledger.postgres`, `gen.ledger.qdrant`, `gen.mcp.adapter`, `gen.tools.wikidata`, `gen.wissensbasis.evidence`

- **test-only** (imported only by tests): `gen.aero.model_parser`, `gen.bracket_fem`, `gen.calibration`, `gen.cfd`, `gen.discovery.proof_loop`, `gen.discovery.rl_env`, `gen.discovery.simulated_data`, `gen.discovery.srbench_hygiene`, `gen.discovery.uncertainty`, `gen.export.ros2_package`, `gen.external.materials_oracle`, `gen.humanoids.agiloped_stand`, `gen.humanoids.asimov_feet`, `gen.humanoids.balance_controller`, `gen.humanoids.insim_mujoco`, `gen.humanoids.mj_stand`, `gen.humanoids.n1_feet`, `gen.integration.identity_research_hook`, `gen.inventor.archive`, `gen.inventor.evolve_engine`, `gen.inventor.refinement`, `gen.montecarlo`, `gen.plate_hole`, `gen.simulation.backends`, `gen.simulation.calculix`, `gen.simulation.modelica`, `gen.simulation.pybullet_sim`, `gen.simulation.surrogate`, `gen.tools.ollama_embedder`, `gen.urdf_bridge`, `gen.verification.trustcore_adapter`

- **transitive** (imported only by other islands): `gen.aero.calibration`, `gen.aero.drone_catalog`, `gen.aero.scaling_laws`, `gen.discovery.reward`, `gen.discovery.validation`, `gen.humanoids.coacd_feet`, `gen.humanoids.rl_env`, `gen.humanoids.step_controller`, `gen.humanoids.step_env`, `gen.memory._vendor.anamnesis_mem.capture`, `gen.memory._vendor.anamnesis_mem.conformal`, `gen.memory._vendor.anamnesis_mem.retrieve`, `gen.memory._vendor.anamnesis_mem.storage`, `gen.memory.verified_facts`, `gen.refinement`, `gen.verification.drift_monitor`

- **orphan** (imported by nobody at all): _(none)_

**Standalone scripts** (11 — runnable via `__main__`, not pipeline-wired): `gen.aero.report`, `gen.cad.cadquery_worker`, `gen.export.drawing_worker`, `gen.humanoids.aethon_shells`, `gen.humanoids.agiloped_feet`, `gen.humanoids.asimov_actuators`, `gen.humanoids.inertia_repair`, `gen.humanoids.report`, `gen.humanoids.rl_train`, `gen.humanoids.step_rl`, `gen.humanoids.validation_insim`

### Technical-debt markers in `src/gen`

| marker | count |
|---|--:|
| `NotImplementedError` | 4 |
| `TODO` | 6 |
| `FIXME` | 0 |
| `first-stone` | 35 |
| `first stone` | 34 |
| `skeleton` | 38 |
| `stub` | 104 |
| `placeholder` | 32 |
| `demo` | 201 |
| `hardcoded` | 11 |
| `HACK` | 5 |
<!-- AUTO:END -->

---

## 5 · Prevention (so this never rots again)

1. **This file is the only status doc.** Regenerate the AUTO block (`python scripts/gen_status.py`) on every
   meaningful change; never hand-write a test count anywhere else.
2. **An un-gameable CI gate** (before the crew loop is ever turned back on): the *full* suite with **no
   `--ignore` / `--deselect`**, plus `find_islands.py` failing CI if a **new** ISLAND appears outside
   `src/gen/_experimental/`, plus a lint banning `except Exception: pass` around result/verdict construction in
   `agents/`, `extensions/`, `pipelines/`.
3. **Weekly human Return Gate:** read §1 + §4 here, spot-check one "done" claim against code.
4. **Forbid "COMPLETE / fertig / ✓ bewiesen"** in commit messages and logs; a claim is true only if it's in this file.

_The autonomous crew loop is currently **HALTED** (`projects/crew/HALTED`) — keep it off until items 1–2 exist._

## 2026-07-07 Update: SIMP Topology Integration — 🔓 OPEN for rework
- Prior claim: unified proposer in section_optimizer; CLI modes topology/structural; seams MECH+topology.
- **Rework status:** 🔓 OPEN (2026-07-11) — re-prove honesty ("vorschlag_unverifiziert"), gates, tests, CLI smoke.
- Collection note (2026-07-11 smoke): pytest collect hit **6 ERROR** files (`test_external_materials_oracle`, `test_fem3d_*`, `test_humanoids_aethon_mechanics`, `test_phase_zeta`, `test_verified_facts`) — first repair targets in campaign.

