# Island Triage — REWORK 2026-07-11

> Generated from `python scripts/find_islands.py` (modules=322, WIRED=210, SCRIPT=11, ISLAND=67, INFRA=34).
> Disposition is human judgement over static import reachability.

## Legend

| Tag | Meaning |
|---|---|
| **KEEP_OPTIN** | Intentional external/optional seam — not dead |
| **PRODUCT_WIRE** | Real product value; needs CLI/web entry (or family wire) |
| **ARCHIVE** | Built-on-spec, not product; stay testable; candidacy for `_experimental/` |
| **TEST_ONLY** | Reached only by tests — OK if intentional harness |
| **VENDOR** | Vendored transitive — not product surface |

## Disposition (67 islands)

### PRODUCT_WIRE (high value when wired)

| Module | Note |
|---|---|
| `gen.pipelines.designer` | ✅ **WIRED 2026-07-11** — `genesis --mode designer` |
| `gen.pipelines.wirtschaft` | ✅ **WIRED 2026-07-11** — `genesis --mode wirtschaft` |
| `gen.frontier` | ✅ **WIRED 2026-07-11** — `genesis --mode frontier` (χ) |
| `gen.research_promotion` | Promotion path — wire when R&D surface ships |

### KEEP_OPTIN (external seams)

| Module | Note |
|---|---|
| `gen.ledger.postgres` | DB optional |
| `gen.ledger.qdrant` | Vector DB optional |
| `gen.mcp.adapter` | MCP optional |
| `gen.export.drawing` / `ros2_package` | Export optional |
| `gen.integration.audited_run` / `drift` / `identity_research_hook` | Integration optional |
| `gen.simulation.backends` / `calculix` / `modelica` / `pybullet_sim` / `surrogate` | External solvers |
| `gen.external.materials_oracle` | GPU ORB optional |
| `gen.verification.trustcore_adapter` | verify-extra parity |
| `gen.tools.ollama_embedder` / `wikidata` | Network/embedder optional |
| `gen.tools` materials path | license-gated |

### ARCHIVE / deep-discovery facade (tests keep green)

| Cluster | Modules |
|---|---|
| discovery facade | `active_resolution`, `assumption_annihilator`, `composition`, `cosmic_insight`, `first_principles`, `reality_fork`, `surrogate`, `universe_bridge` |
| discovery test-only | `proof_loop`, `rl_env`, `simulated_data`, `srbench_hygiene`, `uncertainty`, `reward`, `validation` |
| inventor experiments | `archive`, `evolve_engine`, `refinement` (+ `gen.refinement` transitive) |
| humanoid experiments | `agiloped_stand`, `asimov_feet`, `balance_controller`, `insim_mujoco`, `mj_stand`, `n1_feet`, `coacd_feet`, `rl_env`, `step_*` |
| aero | `model_parser`, `calibration`, `drone_catalog`, `scaling_laws` |
| physics satellites | `bracket_fem`, `cfd`, `montecarlo`, `plate_hole`, `calibration`, `urdf_bridge` |

### VENDOR / memory

| Module | Note |
|---|---|
| `gen.memory.verified_facts` | Used via memory fabric paths; static graph tags transitive |
| `gen.memory._vendor.anamnesis_mem.*` | Vendored ANAMNESIS — keep |

### SCRIPT (11) — runnable `__main__`, not pipeline

`aero.report`, `cad.cadquery_worker`, `export.drawing_worker`, humanoid shells/feet/actuators/report/rl_train/step_rl/inertia_repair/validation_insim.

**Policy:** leave as scripts; promote only with CLI mode + tests.

## Actions this session

1. Document disposition (this file).
2. Re-verify island modules that have tests (discovery facade + humanoids + goldset).
3. Do **not** mass-move to `_experimental/` without re-export audit (prior build-break lesson).
4. PRODUCT_WIRE backlog: designer/wirtschaft CLI family; χ frontier CLI.

## CI recommendation (STATUS §5)

- Fail CI if a **new** ISLAND appears outside `_experimental/` without disposition entry here or in STATUS §4.
- Never move files without updating package `__init__` re-exports + find_islands baseline.

## Update 2026-07-11

Closed PRODUCT_WIRE for designer/wirtschaft/frontier. Islands 67→64, WIRED 210→214.

## Update 2026-07-11 — full Fach family

All 10 pipelines CLI-routed via `fach_cli.run_fach_pipeline`. research_promotion via research mode ladder line. Islands 63, WIRED 215.
