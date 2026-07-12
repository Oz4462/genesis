# GENESIS — FULL REWORK CAMPAIGN

> **Started:** 2026-07-11  
> **Policy:** Everything previously marked DONE / FIXED / CLOSED / COMPLETE is **OPEN** again.  
> **Goal:** Rework every module, every detail, every line — with 4 lenses, tests, wiring proof.  
> **SSOT for this campaign:** this file. `docs/STATUS.md` remains product truth after re-verification.

## Status legend

| Status | Meaning |
|---|---|
| `OPEN` | Not yet reworked in this campaign |
| `IN_PROGRESS` | Active rework |
| `REWORKED` | Code reworked + tests green + wiring verified |
| `VERIFIED` | Independent review passed (4 lenses) |

## Campaign rules

1. **No prior DONE claim is trusted.** Re-read code, re-run tests, re-prove wiring.
2. **One package/module cluster at a time** (finish-or-fail).
3. **4 lenses per module:** L1 Wahrheit · L2 Drift · L3 Naht · L4 Realisierbarkeit.
4. **Evidence only:** test output, import graph, CLI smoke — no green banners without proof.
5. **Honesty first:** stubs stay stubs until real; no fabrication.
6. After each module: update this file, `docs/STATUS.md` if product truth changed, BUILD_LOG entry.

## Priority order (rework sequence)

1. `core/` — state, interfaces, errors (foundation)
2. `verification/` — gates, cross_model, derivation, units
3. `ledger/` + `llm/` + `tools/`
4. `agents/` — scout, scholar, skeptic, conductor, synthesizer, forge, architect
5. `runner.py` + `pipeline.py` + quality engine
6. Physics stack + CAD + simulation
7. `pipelines/` + `grenzverschiebung/` + `inventor/` + `discovery/`
8. `humanoids/` + web/cli + islands
9. Docs honesty pass (STATUS, CAPABILITIES, HORIZON)

## Module inventory (all OPEN)

**Total modules (excl. `__init__.py`):** 290

### `core/` (3 modules)

- [x] **REWORKED** `gen.core.errors` — re-read; typed fail-loud hierarchy intact; exercised by gate/ledger tests
- [x] **REWORKED** `gen.core.interfaces` — Protocols Tool/Agent/LedgerStore/Gate/SearchBackend + GateResult clean
- [x] **REWORKED** `gen.core.state` — Claim confidence [0,1] finite; non-empty text; SourceRef default SUPPORTS + non-empty url; Measurement retrieved+finite (tests/test_core_state_invariants.py)

### `verification/` (12 modules)

- [x] **REWORKED** `gen.verification.cegis` — suite green (test_cegis)
- [x] **REWORKED** `gen.verification.consensus` — shares cross_model._clamp01 (NaN-safe); panel tests green
- [x] **REWORKED** `gen.verification.constraint_smt` — suite green
- [x] **REWORKED** `gen.verification.cross_model` — _clamp01 NaN/Inf→0; corroborated_confidence safe
- [x] **REWORKED** `gen.verification.derivation` — within_tolerance rejects non-finite
- [x] **REWORKED** `gen.verification.drift_monitor` — suite green
- [x] **REWORKED** `gen.verification.gates` — NONFINITE_CONFIDENCE on VERIFIED+NaN (IEEE poison fix)
- [x] **REWORKED** `gen.verification.geometry` — suite green
- [x] **REWORKED** `gen.verification.smt` — suite green
- [x] **REWORKED** `gen.verification.symbolic` — suite green
- [x] **REWORKED** `gen.verification.trustcore_adapter` — suite green (opt-in seam)
- [x] **REWORKED** `gen.verification.units` — suite green; empty unit = DIMENSIONLESS by design

### `ledger/` (3 modules)

- [x] **REWORKED** `gen.ledger.postgres` — re-verified characterization suite path
- [x] **REWORKED** `gen.ledger.qdrant` — integration suite path
- [x] **REWORKED** `gen.ledger.store` — layer-2 integrity: sources+confidence after mutation

### `llm/` (9 modules)

- [x] **REWORKED** `gen.llm._cli` — suite green
- [x] **REWORKED** `gen.llm.base` — re-verified
- [x] **REWORKED** `gen.llm.claude_cli` — suite green
- [x] **REWORKED** `gen.llm.codex_cli` — suite green
- [x] **REWORKED** `gen.llm.factory` — suite green
- [x] **REWORKED** `gen.llm.grok_cli` — suite green
- [x] **REWORKED** `gen.llm.ollama` — re-verified suite green
- [x] **REWORKED** `gen.llm.parsing` — already rejects NaN JSON; re-verified
- [x] **REWORKED** `gen.llm.schemas` — suite green

### `tools/` (12 modules)

- [x] **REWORKED** `gen.tools.arxiv_backend` — suite green
- [x] **REWORKED** `gen.tools.codata` — suite green
- [x] **REWORKED** `gen.tools.dlmf` — suite green
- [x] **REWORKED** `gen.tools.fetch` — scheme allowlist http/https; re-verified
- [x] **REWORKED** `gen.tools.formula_backend` — static authoritative sources; limit≤0 empty; suite path green
- [x] **REWORKED** `gen.tools.http` — re-verified via fetch suite path
- [x] **REWORKED** `gen.tools.ollama_embedder` — fail-loud LLMTransportError; suite green
- [x] **REWORKED** `gen.tools.rag_backend` — deterministic n-gram RAG; suite green
- [x] **REWORKED** `gen.tools.search` — re-verified suite path
- [x] **REWORKED** `gen.tools.sources.openalex` — no invent id; SearchBackendError loud; tools_sources suite
- [x] **REWORKED** `gen.tools.sources.patents` — key boundary honest; tools_sources suite
- [x] **REWORKED** `gen.tools.wikidata` — SPARQL string escape + Q-id guard; suite green

### `agents/` (8 modules)

- [x] **REWORKED** `gen.agents.architect` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present
- [x] **REWORKED** `gen.agents.conductor` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present
- [x] **REWORKED** `gen.agents.forge` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present
- [x] **REWORKED** `gen.agents.humanoid_researcher` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present
- [x] **REWORKED** `gen.agents.scholar` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present
- [x] **REWORKED** `gen.agents.scout` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present
- [x] **REWORKED** `gen.agents.skeptic` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present
- [x] **REWORKED** `gen.agents.synthesizer` — re-verified suite green; skeptic NaN clamp intact; array-shape guards present

### `cad/` (9 modules)

- [x] **REWORKED** `gen.cad.assembly` — suite green
- [x] **REWORKED** `gen.cad.cadquery_bridge` — restored from campaign; KEEP_OPTIN
- [x] **REWORKED** `gen.cad.cadquery_worker` — restored from campaign; KEEP_OPTIN
- [x] **REWORKED** `gen.cad.cost_model` — fail-loud non-finite volume re-verified
- [x] **REWORKED** `gen.cad.gcode` — re-verified suite path
- [x] **REWORKED** `gen.cad.kicad` — suite green
- [x] **REWORKED** `gen.cad.kicad_cli` — restored; kicad suite path
- [x] **REWORKED** `gen.cad.manufacturing_check` — suite green
- [x] **REWORKED** `gen.cad.prototype_cad_builder` — suite green

### `simulation/` (8 modules)

- [x] **REWORKED** `gen.simulation.backends` — suite green re-verify
- [x] **REWORKED** `gen.simulation.calculix` — restored; integration suite path
- [x] **REWORKED** `gen.simulation.modelica` — restored; integration suite path
- [x] **REWORKED** `gen.simulation.multibody` — suite green
- [x] **REWORKED** `gen.simulation.pybullet_sim` — suite green re-verify
- [x] **REWORKED** `gen.simulation.quantum_opt` — import smoke; KEEP_OPTIN
- [x] **REWORKED** `gen.simulation.runner` — suite green
- [x] **REWORKED** `gen.simulation.surrogate` — suite green re-verify

### `pipelines/` (11 modules)

- [x] **REWORKED** `gen.pipelines.architekt` — suite green re-verify
- [x] **REWORKED** `gen.pipelines.designer` — WIRED via --mode designer (fach_cli)
- [x] **REWORKED** `gen.pipelines.elektriker` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.pipelines.fertigungs` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.pipelines.ingenieur` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.pipelines.integrator` — suite green re-verify
- [x] **REWORKED** `gen.pipelines.physiker` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.pipelines.regulatorik` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.pipelines.software` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.pipelines.techniker` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.pipelines.wirtschaft` — WIRED via --mode wirtschaft (fach_cli)

### `discovery/` (35 modules)

- [x] **REWORKED** `gen.discovery.active_resolution` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.active_search` — suite green re-verify
- [x] **REWORKED** `gen.discovery.archive` — suite green re-verify
- [x] **REWORKED** `gen.discovery.assumption_annihilator` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.benchmark` — suite green
- [x] **REWORKED** `gen.discovery.campaign` — suite green re-verify
- [x] **REWORKED** `gen.discovery.canonical` — suite green re-verify
- [x] **REWORKED** `gen.discovery.composition` — suite green
- [x] **REWORKED** `gen.discovery.concept_utility` — suite green re-verify
- [x] **REWORKED** `gen.discovery.controller` — suite green
- [x] **REWORKED** `gen.discovery.cosmic_insight` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.engine` — suite green
- [x] **REWORKED** `gen.discovery.feynman` — feynman_benchmark suite green
- [x] **REWORKED** `gen.discovery.first_principles` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.graph` — suite green
- [x] **REWORKED** `gen.discovery.knowledge_graph` — suite green re-verify
- [x] **REWORKED** `gen.discovery.multiterm` — suite green
- [x] **REWORKED** `gen.discovery.proof_loop` — suite green
- [x] **REWORKED** `gen.discovery.reality_fork` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.reward` — NaN/Inf r² → 0.0; suite + non-finite tests
- [x] **REWORKED** `gen.discovery.rl_env` — suite green re-verify
- [x] **REWORKED** `gen.discovery.run` — public discover API; engine/controller suite path
- [x] **REWORKED** `gen.discovery.separability` — suite green re-verify
- [x] **REWORKED** `gen.discovery.simulated_data` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.sindy` — suite green
- [x] **REWORKED** `gen.discovery.srbench_hygiene` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.surrogate` — suite green
- [x] **REWORKED** `gen.discovery.symbiosis` — suite green; unbuildable proposals abstain
- [x] **REWORKED** `gen.discovery.symbolic_search` — suite green
- [x] **REWORKED** `gen.discovery.tournament` — suite green
- [x] **REWORKED** `gen.discovery.transcendental` — suite green
- [x] **REWORKED** `gen.discovery.tree_search` — suite green re-verify
- [x] **REWORKED** `gen.discovery.uncertainty` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.universe_bridge` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.validation` — suite green re-verify

### `grenzverschiebung/` (16 modules)

- [x] **REWORKED** `gen.grenzverschiebung.bench_test_runner` — package export + suite path
- [x] **REWORKED** `gen.grenzverschiebung.boundary_reviser` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.breakthrough_watch` — gap-tied frontier; characterization 11p green
- [x] **REWORKED** `gen.grenzverschiebung.capability_gap_analyzer` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.cluster` — readiness ladder export path; CI port
- [x] **REWORKED** `gen.grenzverschiebung.development_front` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.experiment_designer` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.learning_integrator` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.lumencrucible` — optional_skips; claim VERIFIED@1.0; forge out_dir/seed_failed/PLANNED_NOT_EXECUTED
- [x] **REWORKED** `gen.grenzverschiebung.milestone_builder` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.proof_package` — F401 clean; lumen integrity path
- [x] **REWORKED** `gen.grenzverschiebung.readiness_ladder` — integrator readiness_input; package exports
- [x] **REWORKED** `gen.grenzverschiebung.safety_ladder` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.technology_builder` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.technology_roadmapper` — suite green re-verify
- [x] **REWORKED** `gen.grenzverschiebung.teststand_architect` — suite green re-verify

### `inventor/` (14 modules)

- [x] **REWORKED** `gen.inventor.archive` — import smoke + archive suite path
- [x] **REWORKED** `gen.inventor.brief` — InventionBrief fail-loud empty field; suite green
- [x] **REWORKED** `gen.inventor.domains.base` — suite green re-verify (domains suite)
- [x] **REWORKED** `gen.inventor.domains.mechatronics` — suite green re-verify
- [x] **REWORKED** `gen.inventor.domains.thermal` — restored ThermalDomain; invent CLI thermal route
- [x] **REWORKED** `gen.inventor.eval` — suite green re-verify
- [x] **REWORKED** `gen.inventor.evolve_engine` — suite green re-verify
- [x] **REWORKED** `gen.inventor.generate` — suite green re-verify
- [x] **REWORKED** `gen.inventor.loop` — suite green re-verify
- [x] **REWORKED** `gen.inventor.novelty` — suite green re-verify
- [x] **REWORKED** `gen.inventor.optimize` — suite green (inventor_seams Pareto/Pymoo)
- [x] **REWORKED** `gen.inventor.refinement` — suite green re-verify
- [x] **REWORKED** `gen.inventor.safety` — suite green re-verify
- [x] **REWORKED** `gen.inventor.score` — suite green re-verify

### `humanoids/` (29 modules)

- [x] **REWORKED** `gen.humanoids.aethon_hydraulics` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.aethon_mechanics` — suite green (prismatic bar via fem3d)
- [x] **REWORKED** `gen.humanoids.aethon_shells` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.agiloped_feet` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.agiloped_stand` — test-only island suite green
- [x] **REWORKED** `gen.humanoids.asimov_actuators` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.asimov_feet` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.balance_controller` — suite green
- [x] **REWORKED** `gen.humanoids.balance_env` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.catalog` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.coacd_feet` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.genesis_humanoid` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.humanoid_research` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.inertia_repair` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.insim` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.insim_mujoco` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.mj_stand` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.model_parser` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.n1_feet` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.render_util` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.report` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.rl_env` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.rl_train` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.scaling_laws` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.step_controller` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.step_env` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.step_rl` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.validation` — restored from campaign branch; humanoid suite re-verified (169p+)
- [x] **REWORKED** `gen.humanoids.validation_insim` — restored from campaign branch; humanoid suite re-verified (169p+)

### `export/` (10 modules)

- [ ] **OPEN** `gen.export.assembly`
- [x] **REWORKED** `gen.export.brep_stl` — brep_stl suite green
- [ ] **OPEN** `gen.export.build123d`
- [x] **REWORKED** `gen.export.drawing` — drawing integration suite
- [ ] **OPEN** `gen.export.drawing_worker`
- [x] **REWORKED** `gen.export.markdown` — markdown suite green
- [ ] **OPEN** `gen.export.numfmt`
- [x] **REWORKED** `gen.export.openscad` — openscad suite green
- [x] **REWORKED** `gen.export.ros2_package` — ros2 integration suite
- [x] **REWORKED** `gen.export.stl` — stl suite green

### `extensions/` (1 modules)

- [x] **REWORKED** `gen.extensions.breakthrough_bridge` — re-verified non-fabrication path (tests green)

### `external/` (3 modules)

- [ ] **OPEN** `gen.external.oracle`
- [ ] **OPEN** `gen.external.registry`
- [x] **REWORKED** `gen.external.vision` — restored; OpenCV camera test green

### `finalizer/` (1 modules)

- [ ] **OPEN** `gen.finalizer.professional_package`

### `formulas/` (1 modules)

- [ ] **OPEN** `gen.formulas.registry`

### `integration/` (3 modules)

- [ ] **OPEN** `gen.integration.audited_run`
- [ ] **OPEN** `gen.integration.drift`
- [ ] **OPEN** `gen.integration.identity_research_hook`

### `lernmaschine/` (1 modules)

- [x] **REWORKED** `gen.lernmaschine.engine` — lernmaschine suite green

### `mcp/` (1 modules)

- [x] **REWORKED** `gen.mcp.adapter` — KEEP_OPTIN re-verify suite green

### `memory/` (1 modules)

- [x] **REWORKED** `gen.memory.verified_facts` — verified_facts suite green

### `wissensbasis/` (3 modules)

- [ ] **OPEN** `gen.wissensbasis.bio_molecular`
- [ ] **OPEN** `gen.wissensbasis.evidence`
- [x] **REWORKED** `gen.wissensbasis.store` — wissensbasis suite green

### `web/` (2 modules)

- [ ] **OPEN** `gen.web.__main__`
- [x] **REWORKED** `gen.web.app` — webapp tests green

### `visualization/` (1 modules)

- [ ] **OPEN** `gen.visualization.robust_renderer`

### `aero/` (5 modules)

- [ ] **OPEN** `gen.aero.calibration`
- [ ] **OPEN** `gen.aero.drone_catalog`
- [ ] **OPEN** `gen.aero.model_parser`
- [ ] **OPEN** `gen.aero.report`
- [ ] **OPEN** `gen.aero.scaling_laws`

### `_experimental/` (5 modules)

- [ ] **OPEN** `gen._experimental.external.materials_oracle`
- [ ] **OPEN** `gen._experimental.memory_vendor.capture`
- [ ] **OPEN** `gen._experimental.memory_vendor.conformal`
- [ ] **OPEN** `gen._experimental.memory_vendor.retrieve`
- [ ] **OPEN** `gen._experimental.memory_vendor.storage`

### `_root/` (82 modules)

- [ ] **OPEN** `gen.__main__`
- [x] **REWORKED** `gen.actuation` — actuation suite green
- [x] **REWORKED** `gen.bolted_joint` — bolted_joint suite green
- [x] **REWORKED** `gen.bracket_fem` — test-only island suite green
- [x] **REWORKED** `gen.brep` — brep suite green
- [x] **REWORKED** `gen.buckling` — suite green
- [x] **REWORKED** `gen.bundle` — bundle suite green
- [x] **REWORKED** `gen.calibration` — test-only island suite green
- [x] **REWORKED** `gen.cfd` — cfd integration suite
- [x] **REWORKED** `gen.chip_selection` — chip_selection suite green
- [x] **REWORKED** `gen.circuit` — suite green
- [x] **REWORKED** `gen.clarification` — clarification suite green
- [x] **REWORKED** `gen.cli` — section/divergence/invent/chip/training modes smoke green
- [x] **REWORKED** `gen.competitive_humanoid` — suite green
- [x] **REWORKED** `gen.completeness` — completeness suite green
- [ ] **OPEN** `gen.compute`
- [ ] **OPEN** `gen.config`
- [ ] **OPEN** `gen.constraint_consistency`
- [ ] **OPEN** `gen.contact`
- [ ] **OPEN** `gen.costing`
- [ ] **OPEN** `gen.coverage`
- [ ] **OPEN** `gen.creep`
- [x] **REWORKED** `gen.demo` — capstone/protocol fixtures via CLI demos
- [x] **REWORKED** `gen.dfm` — suite green
- [ ] **OPEN** `gen.digital_bus`
- [x] **REWORKED** `gen.dimensional_guard` — re-verified scale invariance; suite green
- [ ] **OPEN** `gen.dynamics`
- [ ] **OPEN** `gen.electronics`
- [ ] **OPEN** `gen.evaluation`
- [x] **REWORKED** `gen.fatigue` — suite green
- [x] **REWORKED** `gen.fem` — suite green
- [x] **REWORKED** `gen.fem3d` — restored APIs + material/solution guards; characterization green
- [x] **REWORKED** `gen.fem3d_quadratic` — material/solution guards wired (parity with fem3d)
- [ ] **OPEN** `gen.flight`
- [ ] **OPEN** `gen.fracture`
- [x] **REWORKED** `gen.frontier` — WIRED via --mode frontier (χ + GATE χ)
- [ ] **OPEN** `gen.future_ideas`
- [ ] **OPEN** `gen.geometry_verification`
- [x] **REWORKED** `gen.goldset` — characterization suite path green
- [ ] **OPEN** `gen.grounding_integrity`
- [x] **REWORKED** `gen.horizon_full` — CLI --demo wires deep discovery + grenz cluster
- [ ] **OPEN** `gen.humanoid_research`
- [ ] **OPEN** `gen.identity_research`
- [ ] **OPEN** `gen.inverse_design`
- [ ] **OPEN** `gen.kinematics`
- [x] **REWORKED** `gen.materials` — suite green
- [ ] **OPEN** `gen.mechanics_formulas`
- [ ] **OPEN** `gen.memory_fabric`
- [ ] **OPEN** `gen.mesh_integrity`
- [x] **REWORKED** `gen.modal` — suite green
- [x] **REWORKED** `gen.montecarlo` — test-only island suite green
- [ ] **OPEN** `gen.notch_fatigue`
- [ ] **OPEN** `gen.omega`
- [ ] **OPEN** `gen.orientation`
- [ ] **OPEN** `gen.physics_selection`
- [x] **REWORKED** `gen.physics_validation` — non-finite safety_factor → error; dimensional_ok NaN=False; gate wire re-proved
- [x] **REWORKED** `gen.pipeline` — optional cert skips recorded in completeness_warnings (no silent pass)
- [ ] **OPEN** `gen.plate_bending`
- [x] **REWORKED** `gen.plate_hole` — test-only island suite green
- [ ] **OPEN** `gen.pressure_vessel`
- [x] **REWORKED** `gen.printability` — suite green
- [ ] **OPEN** `gen.proof_kernels`
- [ ] **OPEN** `gen.ratification`
- [x] **REWORKED** `gen.reality` — re-verified suite green
- [ ] **OPEN** `gen.refinement`
- [x] **REWORKED** `gen.research_promotion` — CLI wired via fach family / research ladder
- [x] **REWORKED** `gen.runner` — re-read; gates wire confidence_threshold correctly; suite green
- [x] **REWORKED** `gen.seams` — fixed NameError in topology text scan; domains_present safe
- [x] **REWORKED** `gen.section_optimizer` — dead ternary fixed (gate fail → nicht_optimiert); StructuralProposal unified
- [ ] **OPEN** `gen.security`
- [ ] **OPEN** `gen.software`
- [x] **REWORKED** `gen.structural` — suite green
- [ ] **OPEN** `gen.telemetry`
- [ ] **OPEN** `gen.thermal`
- [ ] **OPEN** `gen.thermal_stress`
- [ ] **OPEN** `gen.tolerance`
- [x] **REWORKED** `gen.topology_optimizer` — re-verified SIMP proposal honesty (vorschlag_unverifiziert)
- [ ] **OPEN** `gen.torsion`
- [ ] **OPEN** `gen.training_plan`
- [ ] **OPEN** `gen.uncertainty`
- [x] **REWORKED** `gen.urdf_bridge` — test-only island suite green
- [ ] **OPEN** `gen.visionary_ideas`

### `audit/` (1 modules)

- [ ] **OPEN** `gen.audit.run_audit`

---

_Inventory generated 2026-07-11 — 290 open modules._

## Integrity / product claims to re-verify (were marked FIXED/DONE)

- [x] **REWORKED** δ+ reality proof abstains honestly — lumen + phase_delta_plus tests green
- [x] **REWORKED** breakthrough mode no fabricated DFM/STL — test_breakthrough_bridge green
- [x] **REWORKED** lumencrucible provenance claim honesty — VERIFIED@1.0 deterministic (not 0.92)
- [x] **REWORKED** ε seams real + Ω enforce opt-in — seams MECH↔MECH removed; enforce_omega tests green
- [x] **REWORKED** goldset CLI mode wired — characterization suite path
- [x] **REWORKED** divergence CLI mode wired — test_cli_divergence_mode green
- [x] **REWORKED** arXiv/OpenAlex/PatentsView build_live backends — wired in build_live; patents key-gated
- [x] **REWORKED** dimensional_guard in GATE δ-physics — + non-finite SF fail-loud
- [ ] **OPEN** topology_optimizer / section_optimizer integration
- [ ] **OPEN** AETHON humanoid assets + mechanics
- [ ] **OPEN** All WORK_QUEUE deep-review DONE modules
- [ ] **OPEN** All HORIZON φ→Ω letters
- [ ] **OPEN** All CAD TEIL2 stones (DFM CNC/Laser/PCB, cost, gcode, kicad)

## Active work

| Date | Module | Status | Notes |
|---|---|---|---|
| 2026-07-11 | — | CAMPAIGN_START | Full open reset; inventory generated |
| 2026-07-11 | collection errors | REWORKED | restored materials_oracle, anamnesis_mem, fem3d APIs; 3477 collected |
| 2026-07-11 | gen.core.* | REWORKED | Claim/SourceRef invariants + 19 new tests; 191 related green |
| 2026-07-11 | verification/* | REWORKED | NaN clamp + gate NONFINITE_CONFIDENCE; derivation tol; 206+ green |
| 2026-07-11 | ledger.store | REWORKED | layer-2 confidence/url integrity after mutation |
| 2026-07-11 | agents/* + tools.fetch | REWORKED | 57 agent/pipeline green; scheme allowlist confirmed |
| 2026-07-11 | physics+CAD+seams | REWORKED | non-finite SF, section verdict, seams NameError; 70–79p slices |
| 2026-07-11 | lumen + inventor | REWORKED | optional_skips; inventor/integrator 41–59p |
| 2026-07-11 | integrity 3-4 + discovery/hum/cli | REWORKED | ε NameError fix; Ω enforce; 47+47p |
| 2026-07-11 | CLI matrix + islands | REWORKED | 32 modes registered; demos green; ISLAND_TRIAGE doc |
| 2026-07-11 | PRODUCT_WIRE frontier/designer/wirtschaft | REWORKED | CLI modes + tests; islands 67→64 |
| 2026-07-11 | full fach family + research_promotion | REWORKED | 10 pipelines + ladder; CAPABILITIES honesty |
| 2026-07-11 | alpha demos + KEEP_OPTIN + AUTO | REWORKED | report/solution/spec --demo; gen_status; ros2 skip |
| 2026-07-12 | capstone UnboundLocal + integrator wb path | REWORKED | CLI demos green; 98p llm/gamma |
| 2026-07-12 | PR CI green (port gaps) | REWORKED | ruff+full pytest 3.11/3.12 green on PR #1 |
| 2026-07-12 | tools/* remaining + wikidata SPARQL | REWORKED | 6 tools OPEN→REWORKED; SPARQL escape + Q-id guard |
| 2026-07-12 | grenz batch + discovery re-verify | REWORKED | proof/readiness/cluster/bench/dev_front; active_search/archive/campaign |
| 2026-07-12 | discovery/grenz/inventor OPEN sweep | REWORKED | reward NaN→0; almost all discovery+grenz+inventor REWORKED |
| 2026-07-12 | humanoids restore + sim/cad KEEP_OPTIN | REWORKED | full humanoids package from campaign; knee_squat_hold_torque; 169p+ |
