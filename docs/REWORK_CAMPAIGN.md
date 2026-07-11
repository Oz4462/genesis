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

- [ ] **OPEN** `gen.llm._cli`
- [x] **REWORKED** `gen.llm.base` — re-verified
- [ ] **OPEN** `gen.llm.claude_cli`
- [ ] **OPEN** `gen.llm.codex_cli`
- [ ] **OPEN** `gen.llm.factory`
- [ ] **OPEN** `gen.llm.grok_cli`
- [x] **REWORKED** `gen.llm.ollama` — re-verified suite green
- [x] **REWORKED** `gen.llm.parsing` — already rejects NaN JSON; re-verified
- [ ] **OPEN** `gen.llm.schemas`

### `tools/` (12 modules)

- [ ] **OPEN** `gen.tools.arxiv_backend`
- [ ] **OPEN** `gen.tools.codata`
- [ ] **OPEN** `gen.tools.dlmf`
- [x] **REWORKED** `gen.tools.fetch` — scheme allowlist http/https; re-verified
- [ ] **OPEN** `gen.tools.formula_backend`
- [x] **REWORKED** `gen.tools.http` — re-verified via fetch suite path
- [ ] **OPEN** `gen.tools.ollama_embedder`
- [ ] **OPEN** `gen.tools.rag_backend`
- [x] **REWORKED** `gen.tools.search` — re-verified suite path
- [ ] **OPEN** `gen.tools.sources.openalex`
- [ ] **OPEN** `gen.tools.sources.patents`
- [ ] **OPEN** `gen.tools.wikidata`

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
- [ ] **OPEN** `gen.cad.cadquery_bridge`
- [ ] **OPEN** `gen.cad.cadquery_worker`
- [x] **REWORKED** `gen.cad.cost_model` — fail-loud non-finite volume re-verified
- [x] **REWORKED** `gen.cad.gcode` — re-verified suite path
- [x] **REWORKED** `gen.cad.kicad` — suite green
- [ ] **OPEN** `gen.cad.kicad_cli`
- [x] **REWORKED** `gen.cad.manufacturing_check` — suite green
- [x] **REWORKED** `gen.cad.prototype_cad_builder` — suite green

### `simulation/` (8 modules)

- [ ] **OPEN** `gen.simulation.backends`
- [ ] **OPEN** `gen.simulation.calculix`
- [ ] **OPEN** `gen.simulation.modelica`
- [ ] **OPEN** `gen.simulation.multibody`
- [ ] **OPEN** `gen.simulation.pybullet_sim`
- [ ] **OPEN** `gen.simulation.quantum_opt`
- [ ] **OPEN** `gen.simulation.runner`
- [ ] **OPEN** `gen.simulation.surrogate`

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
- [ ] **OPEN** `gen.discovery.active_search`
- [ ] **OPEN** `gen.discovery.archive`
- [x] **REWORKED** `gen.discovery.assumption_annihilator` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.benchmark` — suite green
- [ ] **OPEN** `gen.discovery.campaign`
- [ ] **OPEN** `gen.discovery.canonical`
- [x] **REWORKED** `gen.discovery.composition` — suite green
- [ ] **OPEN** `gen.discovery.concept_utility`
- [x] **REWORKED** `gen.discovery.controller` — suite green
- [x] **REWORKED** `gen.discovery.cosmic_insight` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.engine` — suite green
- [ ] **OPEN** `gen.discovery.feynman`
- [x] **REWORKED** `gen.discovery.first_principles` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.graph` — suite green
- [ ] **OPEN** `gen.discovery.knowledge_graph`
- [x] **REWORKED** `gen.discovery.multiterm` — suite green
- [x] **REWORKED** `gen.discovery.proof_loop` — suite green
- [x] **REWORKED** `gen.discovery.reality_fork` — island re-verify suite green
- [ ] **OPEN** `gen.discovery.reward`
- [ ] **OPEN** `gen.discovery.rl_env`
- [ ] **OPEN** `gen.discovery.run`
- [ ] **OPEN** `gen.discovery.separability`
- [x] **REWORKED** `gen.discovery.simulated_data` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.sindy` — suite green
- [x] **REWORKED** `gen.discovery.srbench_hygiene` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.surrogate` — suite green
- [ ] **OPEN** `gen.discovery.symbiosis`
- [x] **REWORKED** `gen.discovery.symbolic_search` — suite green
- [x] **REWORKED** `gen.discovery.tournament` — suite green
- [x] **REWORKED** `gen.discovery.transcendental` — suite green
- [ ] **OPEN** `gen.discovery.tree_search`
- [x] **REWORKED** `gen.discovery.uncertainty` — island re-verify suite green
- [x] **REWORKED** `gen.discovery.universe_bridge` — island re-verify suite green
- [ ] **OPEN** `gen.discovery.validation`

### `grenzverschiebung/` (16 modules)

- [ ] **OPEN** `gen.grenzverschiebung.bench_test_runner`
- [ ] **OPEN** `gen.grenzverschiebung.boundary_reviser`
- [ ] **OPEN** `gen.grenzverschiebung.breakthrough_watch`
- [ ] **OPEN** `gen.grenzverschiebung.capability_gap_analyzer`
- [ ] **OPEN** `gen.grenzverschiebung.cluster`
- [ ] **OPEN** `gen.grenzverschiebung.development_front`
- [ ] **OPEN** `gen.grenzverschiebung.experiment_designer`
- [ ] **OPEN** `gen.grenzverschiebung.learning_integrator`
- [x] **REWORKED** `gen.grenzverschiebung.lumencrucible` — optional_skips surface; δ+ abstain re-proved; more silent-except backlog
- [ ] **OPEN** `gen.grenzverschiebung.milestone_builder`
- [ ] **OPEN** `gen.grenzverschiebung.proof_package`
- [ ] **OPEN** `gen.grenzverschiebung.readiness_ladder`
- [ ] **OPEN** `gen.grenzverschiebung.safety_ladder`
- [ ] **OPEN** `gen.grenzverschiebung.technology_builder`
- [ ] **OPEN** `gen.grenzverschiebung.technology_roadmapper`
- [ ] **OPEN** `gen.grenzverschiebung.teststand_architect`

### `inventor/` (14 modules)

- [ ] **OPEN** `gen.inventor.archive`
- [ ] **OPEN** `gen.inventor.brief`
- [ ] **OPEN** `gen.inventor.domains.base`
- [ ] **OPEN** `gen.inventor.domains.mechatronics`
- [ ] **OPEN** `gen.inventor.domains.thermal`
- [ ] **OPEN** `gen.inventor.eval`
- [ ] **OPEN** `gen.inventor.evolve_engine`
- [ ] **OPEN** `gen.inventor.generate`
- [x] **REWORKED** `gen.inventor.loop` — suite green re-verify
- [ ] **OPEN** `gen.inventor.novelty`
- [ ] **OPEN** `gen.inventor.optimize`
- [ ] **OPEN** `gen.inventor.refinement`
- [x] **REWORKED** `gen.inventor.safety` — suite green re-verify
- [x] **REWORKED** `gen.inventor.score` — suite green re-verify

### `humanoids/` (29 modules)

- [ ] **OPEN** `gen.humanoids.aethon_hydraulics`
- [x] **REWORKED** `gen.humanoids.aethon_mechanics` — suite green (prismatic bar via fem3d)
- [ ] **OPEN** `gen.humanoids.aethon_shells`
- [ ] **OPEN** `gen.humanoids.agiloped_feet`
- [x] **REWORKED** `gen.humanoids.agiloped_stand` — test-only island suite green
- [ ] **OPEN** `gen.humanoids.asimov_actuators`
- [ ] **OPEN** `gen.humanoids.asimov_feet`
- [x] **REWORKED** `gen.humanoids.balance_controller` — suite green
- [ ] **OPEN** `gen.humanoids.balance_env`
- [ ] **OPEN** `gen.humanoids.catalog`
- [ ] **OPEN** `gen.humanoids.coacd_feet`
- [ ] **OPEN** `gen.humanoids.genesis_humanoid`
- [ ] **OPEN** `gen.humanoids.humanoid_research`
- [ ] **OPEN** `gen.humanoids.inertia_repair`
- [ ] **OPEN** `gen.humanoids.insim`
- [ ] **OPEN** `gen.humanoids.insim_mujoco`
- [ ] **OPEN** `gen.humanoids.mj_stand`
- [ ] **OPEN** `gen.humanoids.model_parser`
- [ ] **OPEN** `gen.humanoids.n1_feet`
- [ ] **OPEN** `gen.humanoids.render_util`
- [ ] **OPEN** `gen.humanoids.report`
- [ ] **OPEN** `gen.humanoids.rl_env`
- [ ] **OPEN** `gen.humanoids.rl_train`
- [ ] **OPEN** `gen.humanoids.scaling_laws`
- [ ] **OPEN** `gen.humanoids.step_controller`
- [ ] **OPEN** `gen.humanoids.step_env`
- [ ] **OPEN** `gen.humanoids.step_rl`
- [ ] **OPEN** `gen.humanoids.validation`
- [ ] **OPEN** `gen.humanoids.validation_insim`

### `export/` (10 modules)

- [ ] **OPEN** `gen.export.assembly`
- [ ] **OPEN** `gen.export.brep_stl`
- [ ] **OPEN** `gen.export.build123d`
- [x] **REWORKED** `gen.export.drawing` — drawing integration suite
- [ ] **OPEN** `gen.export.drawing_worker`
- [ ] **OPEN** `gen.export.markdown`
- [ ] **OPEN** `gen.export.numfmt`
- [ ] **OPEN** `gen.export.openscad`
- [x] **REWORKED** `gen.export.ros2_package` — ros2 integration suite
- [ ] **OPEN** `gen.export.stl`

### `extensions/` (1 modules)

- [x] **REWORKED** `gen.extensions.breakthrough_bridge` — re-verified non-fabrication path (tests green)

### `external/` (3 modules)

- [ ] **OPEN** `gen.external.oracle`
- [ ] **OPEN** `gen.external.registry`
- [ ] **OPEN** `gen.external.vision`

### `finalizer/` (1 modules)

- [ ] **OPEN** `gen.finalizer.professional_package`

### `formulas/` (1 modules)

- [ ] **OPEN** `gen.formulas.registry`

### `integration/` (3 modules)

- [ ] **OPEN** `gen.integration.audited_run`
- [ ] **OPEN** `gen.integration.drift`
- [ ] **OPEN** `gen.integration.identity_research_hook`

### `lernmaschine/` (1 modules)

- [ ] **OPEN** `gen.lernmaschine.engine`

### `mcp/` (1 modules)

- [x] **REWORKED** `gen.mcp.adapter` — KEEP_OPTIN re-verify suite green

### `memory/` (1 modules)

- [ ] **OPEN** `gen.memory.verified_facts`

### `wissensbasis/` (3 modules)

- [ ] **OPEN** `gen.wissensbasis.bio_molecular`
- [ ] **OPEN** `gen.wissensbasis.evidence`
- [ ] **OPEN** `gen.wissensbasis.store`

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
- [ ] **OPEN** `gen.actuation`
- [ ] **OPEN** `gen.bolted_joint`
- [x] **REWORKED** `gen.bracket_fem` — test-only island suite green
- [ ] **OPEN** `gen.brep`
- [x] **REWORKED** `gen.buckling` — suite green
- [ ] **OPEN** `gen.bundle`
- [x] **REWORKED** `gen.calibration` — test-only island suite green
- [x] **REWORKED** `gen.cfd` — cfd integration suite
- [ ] **OPEN** `gen.chip_selection`
- [x] **REWORKED** `gen.circuit` — suite green
- [ ] **OPEN** `gen.clarification`
- [x] **REWORKED** `gen.cli` — section/divergence/invent/chip/training modes smoke green
- [x] **REWORKED** `gen.competitive_humanoid` — suite green
- [ ] **OPEN** `gen.completeness`
- [ ] **OPEN** `gen.compute`
- [ ] **OPEN** `gen.config`
- [ ] **OPEN** `gen.constraint_consistency`
- [ ] **OPEN** `gen.contact`
- [ ] **OPEN** `gen.costing`
- [ ] **OPEN** `gen.coverage`
- [ ] **OPEN** `gen.creep`
- [ ] **OPEN** `gen.demo`
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
- [ ] **OPEN** arXiv/OpenAlex/PatentsView build_live backends
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
