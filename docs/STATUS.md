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
> **Last curated review: 2026-07-12 — main through PR #9; inventory REWORKED; CLAUDE.md re-synced.**

---

## 🟢 FULL REWORK CAMPAIGN (2026-07-11) — MODULE INVENTORY REWORKED

> **Owner directive (original):** Everything previously DONE was re-opened for full rework. Prior green
> banners were not trusted until re-proven.
>
> **Campaign tracker:** [`docs/REWORK_CAMPAIGN.md`](REWORK_CAMPAIGN.md) — **~303 REWORKED / 0 OPEN modules**
> (suite re-verify + wiring notes). Deeper independent **VERIFIED** (4 lenses) remains optional next layer.
> **Local path:** `/home/genesis/genesis` · **Remote:** `https://github.com/Oz4462/genesis`
> **Branches:** `main` tracks `origin/main` (PR #1–#9). SSOT tip: `git rev-parse origin/main`.
>
> **Policy (still applies):**
> 1. No prior DONE claim counts without tests + wiring proof.
> 2. Stubs stay honest stubs; no fabrication.
> 3. Optional assets (`humanoid_assets/`) may be missing — honest structural gaps, not silent success.
> 4. After merges: regenerate AUTO block with `scripts/gen_status.py` when convenient.

**Rework progress:** module inventory **0 OPEN** · WIRED **258** / SCRIPT 9 / ISLAND **26** · CLI **47** modes (matrix auto-sync from cli.py)

**2026-07-12 continue session:**
- PR #1 merged to `main` (integrity, PRODUCT_WIRE, humanoids restore, CI green).
- Aero restore + class-aware T/W floors (`MIN_THRUST_WEIGHT_BY_CLASS`); drawing + professional package.
- Root physics/quality OPEN batch + CAD TEIL2 + HORIZON phase suites re-verified; `validate_pcb_with_kicad_cli` ported.
- `gen.humanoid_research` shim restored; experimental KEEP_OPTIN honesty.
- Handoff: `docs/SESSION_HANDOFF_2026-07-12.md`.


---

## 0 · The one-line truth

GENESIS has a **solid anti-hallucination core direction** (research→spec→δ-physics, claim ledger, hard gates)
**plus a large surface of islands, demos, and over-claimed docs.** Under the full rework campaign, **nothing
is assumed fixed.** Trust only what is re-proven in `docs/REWORK_CAMPAIGN.md` with evidence.

**Maturity (provisional until rework completes):** honest core ≈ **unknown / re-verify** · product vision ≈ **open** ·
blended ≈ **open**. Historical estimate (~50%) is archival only.

---

## 1 · 🟢 INTEGRITY WATCHLIST (rows REWORKED 2026-07-11/12)

These are the lies an *anti-hallucination* engine must not ship. Rows were re-opened 2026-07-11 and
**re-proven** with suite evidence (see table). Keep regression tests green on every merge.

| # | Where | What it fakes / risk | Status |
|---|---|---|---|
| 1 | `agents/conductor.py` `_enrich_delta_plus` + `grenzverschiebung/lumencrucible.py` δ⁺ block | δ⁺ "reality proof" may fabricate corroboration | ✅ **REWORKED 2026-07-11** — re-proved abstention (phase_delta_plus + lumen tests green) |
| 2 | `extensions/breakthrough_bridge.py` | fabricated DFM/STL/volume when CAD missing | ✅ **REWORKED 2026-07-11** — test_breakthrough_bridge green |
| 3 | `grenzverschiebung/lumencrucible.py` | VERIFIED claim framing / confidence honesty | ✅ **REWORKED 2026-07-11** — deterministic provenance VERIFIED@1.0 (tests) |
| 4 | `grenzverschiebung/lumencrucible.py` ε/ζ/coverage + Ω | discarded gates / empty seams / Ω not enforced | ✅ **REWORKED 2026-07-11** — subgates captured; enforce_omega raises; ε suite green |

**Wiring claims (re-proved 2026-07-11/12):**

| Claim | Status |
|---|---|
| `goldset` → `genesis --mode goldset` | ✅ REWORKED |
| φ `run_divergence` → `genesis --mode divergence` | ✅ REWORKED |
| arXiv + OpenAlex (+ keyed PatentsView) → `build_live` | ✅ REWORKED — tools_sources + build_live path |
| `dimensional_guard` → GATE δ-physics | ✅ REWORKED — + non-finite SF fail-loud |
| topology / section optimizer integration | ✅ REWORKED — verdict honesty + seams fix |

---

## 2 · CLI-mode truth table (27+ modes) — re-audited under rework

What each `genesis --mode X` is *claimed* to do. Rows re-smoked under the 2026-07 rework campaign
(demo/offline paths). Live LLM modes remain 🟡 where noted.

| Mode(s) | Prior label (archive) | Rework status |
|---|---|---|
| `report` · `solution` · `spec` | LIVE α/β/γ pipeline | ✅ REWORKED — **`--demo` offline scripted E2E green** (live needs LLMs) |
| `research` | LIVE identity_research | ✅ REWORKED — smoke (x+1)² |
| `discover-ode` | LIVE SINDy | ✅ REWORKED — pendulum demo R²=1 |
| `invent` · `solve` | LIVE loop (canned council offline) | ✅ REWORKED — invent --demo green |
| `council` · `feynman` · `campaign` | LIVE discovery sub-engines | ✅ REWORKED — offline demos green (council gate + Feynman 5/5+3/3 + campaign); `--live` optional |
| `aero-report` · `humanoid-report` · `surface` | catalog reports + product surface | ✅ REWORKED 2026-07-12 — CLI PRODUCT_WIRE (was SCRIPT-only) |
| `section` · `training` · `chip` · `topology` · `structural` | deterministic sub-engines | ✅ REWORKED — demos green |
| `bundle` | artifact emitter | ✅ REWORKED — `--demo` writes MANIFEST/MISSING honest |
| `capstone` · `protocol` · `assess` · `print` · `eval` | DEMO | ✅ REWORKED — capstone UnboundLocal fixed; all demos green |
| `ideas` · `dream` · `humanoid` · `aethon` | CANNED | ✅ REWORKED ideas/dream demos green; aethon suite |
| `realize` | integrator stubs | ✅ REWORKED — wb seeding import fixed; package writes |
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

> Live count 2026-07-12 (continue-4): **modules=327 · WIRED=258 · SCRIPT=9 · ISLAND=26 · INFRA=34**.
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
_Auto-generated by `scripts/gen_status.py` on **2026-07-12**. Do not edit by hand — re-run the script._

### Reachability (via `scripts/find_islands.py`)

| modules | WIRED | SCRIPT (runnable, not wired) | ISLAND (no caller) | INFRA |
|--:|--:|--:|--:|--:|
| 327 | 258 | 9 | 26 | 34 |

**Live test suite:** 2487 collected

**Islands by category** (26 total — real code, no production caller):

- **facade-only** (imported only by a package `__init__` re-export — false liveness): `gen.ledger.postgres`, `gen.mcp.adapter`

- **test-only** (imported only by tests): `gen.cad.cadquery_bridge`, `gen.discovery.rl_env`, `gen.discovery.simulated_data`, `gen.discovery.srbench_hygiene`, `gen.external.materials_oracle`, `gen.humanoids.aethon_hydraulics`, `gen.humanoids.agiloped_stand`, `gen.humanoids.asimov_feet`, `gen.humanoids.insim_mujoco`, `gen.humanoids.mj_stand`, `gen.humanoids.n1_feet`, `gen.integration.identity_research_hook`, `gen.simulation.backends`, `gen.simulation.calculix`, `gen.simulation.modelica`, `gen.simulation.pybullet_sim`, `gen.simulation.surrogate`, `gen.tools.ollama_embedder`

- **transitive** (imported only by other islands): `gen.discovery.reward`, `gen.discovery.validation`, `gen.humanoids.coacd_feet`, `gen.humanoids.rl_env`, `gen.humanoids.step_controller`, `gen.humanoids.step_env`

- **orphan** (imported by nobody at all): _(none)_

**Standalone scripts** (9 — runnable via `__main__`, not pipeline-wired): `gen.cad.cadquery_worker`, `gen.export.drawing_worker`, `gen.humanoids.aethon_shells`, `gen.humanoids.agiloped_feet`, `gen.humanoids.asimov_actuators`, `gen.humanoids.inertia_repair`, `gen.humanoids.rl_train`, `gen.humanoids.step_rl`, `gen.humanoids.validation_insim`

### Technical-debt markers in `src/gen`

| marker | count |
|---|--:|
| `NotImplementedError` | 4 |
| `TODO` | 6 |
| `FIXME` | 0 |
| `first-stone` | 33 |
| `first stone` | 31 |
| `skeleton` | 30 |
| `stub` | 86 |
| `placeholder` | 26 |
| `demo` | 191 |
| `hardcoded` | 9 |
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

## 2026-07-07 Update: SIMP Topology Integration — ✅ REWORKED 2026-07-12
- Prior claim: unified proposer in section_optimizer; CLI modes topology/structural; seams MECH+topology.
- **Rework status:** ✅ **REWORKED** — topology+section suite green (30p); honesty contract `vorschlag_unverifiziert` + delta_path gates.
- Collection note (2026-07-11): historical collect ERRORs repaired via campaign (humanoids/vendor/fem paths); main CI green on PR #1+#2.

