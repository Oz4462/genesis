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
> **Last curated review: 2026-06-26.**

---

## 0 · The one-line truth

GENESIS has a **genuinely good, tested anti-hallucination core** (research→spec→δ-physics, with a real
sourced-claim ledger and hard gates) **buried under island modules (~75 and shrinking) and demo-depth "HORIZON"
bolt-ons.** The two fabrication paths (δ⁺ reality + `breakthrough` DFM) were **FIXED 2026-06-26** — the §1
watchlist is now all ✅. The code is more honest than the docs; the docs over-claim. Trust the green tests and
the gates; distrust every "✓ bewiesen / COMPLETE / DFM PASSED" banner until it's listed here.

**Maturity:** honest core ≈ **80% & working** · full product vision ≈ **35%** · blended ≈ **50%**
(the missing half is mostly *real-code-not-wired*, not greenfield).

---

## 1 · 🔴 INTEGRITY WATCHLIST (fix before anything else)

These are the lies an *anti-hallucination* engine must not ship. **Do not remove a row until the code abstains
honestly and a regression test guards it.**

| # | Where | What it fakes | Status |
|---|---|---|---|
| 1 | `agents/conductor.py` `_enrich_delta_plus` + `grenzverschiebung/lumencrucible.py` δ⁺ block | δ⁺ "reality proof" lied `retrieved=True` on a measurement whose value equalled the prediction → always "corroborated", could never refute | ✅ **FIXED 2026-06-26** — both now ABSTAIN: no fabricated `Measurement`, `reality_verdict=None`, `delta_plus_result.status="inconclusive"` (honest, HORIZON §2B; the `Measurement` invariant `state.py:441` is no longer defeated). Guarded by `test_delta_plus_abstains_honestly_without_a_measurement`; 130 + 8 aethon tests green. |
| 2 | `extensions/breakthrough_bridge.py` | mode `breakthrough` wrote *"DFM PASSED / Real STL / Not mock"* with `real_stl=None`, `volume=48.5` hardcoded (build123d failure swallowed) | ✅ **FIXED 2026-06-26** — `volume=None` when not built; DFM runs ONLY on real geometry; report/gates/manifest branch on `built` → when build123d is absent it honestly says "NOT BUILT / DFM NOT EVALUATED" (verified: `CAD STL: None`, `DFM passed: False`). `test_breakthrough_bridge` rewritten to assert non-fabrication (2 green). |
| 3 | `grenzverschiebung/lumencrucible.py` (~462) | minted `status=VERIFIED, confidence=0.92` Claim with in-repo file-path "sources", as if cross-model-verified | ✅ **FIXED 2026-06-26 (clarified)** — it's a **deterministic provenance claim** (the code provably produced this hammer; sourced to the real code paths). Now `confidence=1.0` + explicit note: VERIFIED-by-execution, NOT cross-model. The arbitrary 0.92 + "Gate+Frontier carry verification" framing are gone. (Owner design note: whether process-claims share the VERIFIED enum with world-facts is a deliberate choice; ζ deposit still works.) |
| 4 | `grenzverschiebung/lumencrucible.py` ε/ζ/coverage + Ω | (a) gate results DISCARDED (`_ = gate_…`); (b) ε cert from EMPTY seams + `complete=False` → ε failed by construction; (c) Ω computed but not enforced | ✅ **FIXED 2026-06-26** — (a) captured + surfaced; (b) ε uses real `detect_cross_domain_seams` + `complete=True`; (c) `process_dream(..., enforce_omega=True)` now raises `OmegaGateNotPassed` on a failed/absent Ω (opt-in, default off until γ⁺/ζ inputs are rich; `test_omega_enforcement_opt_in_passes_on_normal_flow`). |

**✅ Wired 2026-06-26:** `goldset.py` (the hallucination-eval harness, formerly **0 callers** — GENESIS never
measured its own central claim) is now reachable via **`genesis --mode goldset`**: it runs all 24 cases through
the REAL α pipeline and scores fact-accuracy / abstention-recall / trap-resistance / fabrications (**exit 3 on any
fabrication**). The per-case runner + Report→outcome mapper are offline-testable (17 tests); a full LIVE run needs
real LLMs/backends (owner-gated, as the module always intended). Note: the α pipeline cannot produce a confident
*unsourced* answer (GATE α), so the run primarily *verifies* the no-fabrication property holds + measures fact-accuracy.

---

## 2 · CLI-mode truth table (27 modes)

What each `genesis --mode X` actually does today. Only the 🟢 modes drive the live cross-model agent pipeline.

| Mode(s) | Reality |
|---|---|
| `report` · `solution` · `spec` | 🟢 **LIVE** — the real α/β/γ pipeline (`runner.py`→`conductor`→agents→gates). The product. |
| `research` | 🟢 LIVE — `identity_research` (mpmath→sympy→z3); verified: proves (x+1)², refutes x²=x³ (x=−3) |
| `discover-ode` | 🟢 LIVE — real SINDy; recovers exact pendulum ODE |
| `invent` · `solve` | 🟢 LIVE loop (safety→council→δ-gate→Pareto); **offline default uses canned council** unless `--live` |
| `council` · `feynman` · `campaign` | 🟢 LIVE discovery sub-engines (real cross-model / rediscovery / MAP-Elites) |
| `section` · `training` · `chip` | 🟢 LIVE deterministic sub-engines (real gates) |
| `bundle` | 🟡 real artifact emitter over a given spec (honest MANIFEST + MISSING.md) |
| `capstone` · `protocol` · `assess` · `print` · `eval` | 🟡 **DEMO** — run over built-in demo specs, not your input |
| `ideas` · `dream` · `humanoid` · `aethon` | 🟡 **CANNED** — prebuilt specs/catalogs (+ `aethon` copies assets from `/home/genesis/humanoid_assets`) |
| `realize` | ⚠️ `integrator` — ships `_generate_*_stub` markdown as deliverables |
| `breakthrough` | 🟡 honest now — reports "NOT BUILT / DFM NOT EVALUATED" when build123d absent (no fabrication; #2 fixed 2026-06-26) |
| `goldset` | 🟢 **NEW** — scores GENESIS's own anti-hallucination claim over the 24-case set via the real α pipeline (runner offline-tested; full live run needs LLMs; exit 3 on any fabrication) |

> Naming traps: **`runner.py` IS the pipeline** (misnamed); `pipeline.py` is a verdict-composer; `simulation/runner.py` is unrelated.

---

## 3 · HORIZON arc status (φ → Ω)

The project's own `HORIZON.md` is honest here ("first-stone / guarded skeleton"); this row-by-row matches the code.

| Phase | Status | Reality |
|---|---|---|
| **φ / χ** | ✅ real, gated, tested | (φ has **no CLI route** — dangling capability) |
| **δ⁺ reality** | ✅ honest abstain | #1 fixed — abstains (`inconclusive`) when no independent measurement; no longer fabricates corroboration |
| **δ⁺ coverage** | ✅ gate / ⚠️ input | hard gate; `reviewed_failure_modes` empty in demo |
| **γ⁺ inverse-design** | ✅ logic / ⚠️ input | real objective-recompute; fed a trivial 1-point front |
| **ε seams** | ✅ real & wired | the strongest HORIZON letter (in `assess_specification`) |
| **ζ memory-fabric** | ✅ gate / ⚠️ input | real gate; `recall_results` always empty (honest abstain) |
| **Ω cert** | 🟡 enforceable (opt-in) | #4 fixed — `enforce_omega=True` raises `OmegaGateNotPassed` on failure; default off in weak-mode until γ⁺/ζ inputs are rich |

---

## 4 · Island disposition (what to DO with the islands)

> **Progress 2026-06-26:** islands **89 → 75**. A new `genesis --mode horizon-full` (`src/gen/horizon_full.py`)
> now wires the deep-discovery core (`ExplorationController`, `discover_multiterm`/`discover_transcendental`,
> `run.discover`) **and the full grenz capability cluster** (new `grenzverschiebung/cluster.py` chains all 7) —
> these moved island → WIRED. ⚠️ **Reachable ≠ trustworthy:** they run on **canonical example inputs**.
> Verdicts are now more honest (watchlist #1 fixed: δ⁺ abstains → `inconclusive`; #4(b) fixed: ε passes on
> real seams) but Ω is still computed-not-**enforced** and γ⁺/ζ inputs are thin — so a green run still does not
> mean "validated". The §1 watchlist — not more wiring — is what makes the verdicts trustworthy.

The **complete mechanical island list is in the AUTO block below** (`scripts/find_islands.py`). This is the curated
*decision* for each remaining cluster. Rule going forward: **speculative modules live in `src/gen/_experimental/`;
promotion to `gen/` requires a real wire + a CLI/web entry point** (see §5 prevention).

| Disposition | Modules (clusters) | Why |
|---|---|---|
| 🟢 **WIRE** (real product value, just unplugged) | `goldset`→`--mode eval`; `tools/sources/openalex` + `tools/arxiv_backend` + `tools/sources/patents`→`build_live`; φ `runner.run_divergence`→a CLI mode; `dimensional_guard`→`physics_validation.VALIDATORS` (it's a real check the docs already claim is "automatic") | high value, low effort |
| 🟠 **FIX or DELETE** (dead **and** misleading) | `verification/trustcore_adapter` (dead + false "no duplicate"); `pipelines/designer` + `pipelines/wirtschaft` (facade-only mappers) | actively misleads |
| 📦 **ARCHIVE → `_experimental/`** (real, built-on-spec, not product yet) | deep-discovery stack (`controller, run, surrogate, tournament, reality_fork, cosmic_insight, assumption_annihilator, first_principles, universe_bridge, active_resolution, composition, multiterm, transcendental, proof_loop, rl_env, simulated_data, srbench_hygiene`); grenz cluster (`bench_test_runner, capability_gap_analyzer, experiment_designer, milestone_builder, technology_builder, technology_roadmapper, teststand_architect`); `inventor/{archive,evolve_engine,refinement}`; humanoid experiments (`aethon_hydraulics, asimov_feet, agiloped_stand, mj_stand, *_feet, *_controller`) | green tests stay; intent becomes honest |
| 🔌 **KEEP as opt-in external seam** (intentional, just **label**, don't treat as dead) | `simulation/{pybullet_sim,backends,calculix,modelica}`; `ledger/{postgres,qdrant}`; `integration/{audited_run,drift,identity_research_hook}`; `external/materials_oracle`; `mcp/adapter`; `export/{ros2_package,drawing}` | by-design import-gated |

> Note: `find_islands.py` is static — it tags by *import reachability*, so an intentional opt-in seam and an
> abandoned zombie both read as "ISLAND". The disposition column is the human layer that tells them apart.

---

<!-- AUTO:BEGIN -->
_Auto-generated by `scripts/gen_status.py` on **2026-06-26**. Do not edit by hand — re-run the script._

### Reachability (via `scripts/find_islands.py`)

| modules | WIRED | SCRIPT (runnable, not wired) | ISLAND (no caller) | INFRA |
|--:|--:|--:|--:|--:|
| 316 | 199 | 11 | 74 | 32 |

**Live test suite:** 3441 collected

**Islands by category** (74 total — real code, no production caller):

- **facade-only** (imported only by a package `__init__` re-export — false liveness): `gen.agents.humanoid_researcher`, `gen.discovery.active_resolution`, `gen.discovery.assumption_annihilator`, `gen.discovery.composition`, `gen.discovery.cosmic_insight`, `gen.discovery.first_principles`, `gen.discovery.reality_fork`, `gen.discovery.surrogate`, `gen.discovery.universe_bridge`, `gen.export.drawing`, `gen.integration.audited_run`, `gen.integration.drift`, `gen.ledger.postgres`, `gen.ledger.qdrant`, `gen.mcp.adapter`, `gen.pipelines.designer`, `gen.pipelines.wirtschaft`, `gen.research_promotion`, `gen.tools.arxiv_backend`, `gen.tools.sources.openalex`, `gen.tools.sources.patents`, `gen.tools.wikidata`, `gen.wissensbasis.evidence`

- **test-only** (imported only by tests): `gen.aero.model_parser`, `gen.bracket_fem`, `gen.calibration`, `gen.cfd`, `gen.dimensional_guard`, `gen.discovery.proof_loop`, `gen.discovery.rl_env`, `gen.discovery.simulated_data`, `gen.discovery.srbench_hygiene`, `gen.discovery.uncertainty`, `gen.export.ros2_package`, `gen.external.materials_oracle`, `gen.frontier`, `gen.humanoids.aethon_hydraulics`, `gen.humanoids.agiloped_stand`, `gen.humanoids.asimov_feet`, `gen.humanoids.balance_controller`, `gen.humanoids.insim_mujoco`, `gen.humanoids.mj_stand`, `gen.humanoids.n1_feet`, `gen.integration.identity_research_hook`, `gen.inventor.archive`, `gen.inventor.evolve_engine`, `gen.inventor.refinement`, `gen.montecarlo`, `gen.plate_hole`, `gen.simulation.backends`, `gen.simulation.calculix`, `gen.simulation.modelica`, `gen.simulation.pybullet_sim`, `gen.simulation.surrogate`, `gen.tools.ollama_embedder`, `gen.urdf_bridge`, `gen.verification.trustcore_adapter`

- **transitive** (imported only by other islands): `gen.aero.calibration`, `gen.aero.drone_catalog`, `gen.aero.scaling_laws`, `gen.audit.run_audit`, `gen.discovery.reward`, `gen.discovery.validation`, `gen.humanoids.coacd_feet`, `gen.humanoids.rl_env`, `gen.humanoids.step_controller`, `gen.humanoids.step_env`, `gen.memory._vendor.anamnesis_mem.capture`, `gen.memory._vendor.anamnesis_mem.conformal`, `gen.memory._vendor.anamnesis_mem.retrieve`, `gen.memory._vendor.anamnesis_mem.storage`, `gen.memory.verified_facts`, `gen.refinement`, `gen.verification.drift_monitor`

- **orphan** (imported by nobody at all): _(none)_

**Standalone scripts** (11 — runnable via `__main__`, not pipeline-wired): `gen.aero.report`, `gen.cad.cadquery_worker`, `gen.export.drawing_worker`, `gen.humanoids.aethon_shells`, `gen.humanoids.agiloped_feet`, `gen.humanoids.asimov_actuators`, `gen.humanoids.inertia_repair`, `gen.humanoids.report`, `gen.humanoids.rl_train`, `gen.humanoids.step_rl`, `gen.humanoids.validation_insim`

### Technical-debt markers in `src/gen`

| marker | count |
|---|--:|
| `NotImplementedError` | 4 |
| `TODO` | 5 |
| `FIXME` | 0 |
| `first-stone` | 26 |
| `first stone` | 33 |
| `skeleton` | 38 |
| `stub` | 104 |
| `placeholder` | 31 |
| `demo` | 190 |
| `hardcoded` | 10 |
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
