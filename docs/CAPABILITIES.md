# CAPABILITIES — GENESIS Fähigkeits-Inventar

> **⚠️ HONESTY (REWORK 2026-07-12):** This inventory was historically over-optimistic
> (test counts, CLI mode counts, “fully wired” banners). **Authoritative product truth:**
> [`docs/STATUS.md`](STATUS.md). Island disposition: [`docs/ISLAND_TRIAGE_2026-07-11.md`](ISLAND_TRIAGE_2026-07-11.md).
> Campaign checklist: [`docs/REWORK_CAMPAIGN.md`](REWORK_CAMPAIGN.md) — **module inventory REWORKED (0 OPEN)**.
> When this file disagrees with STATUS, **STATUS wins**. Treat ✅ as “re-verified under rework”
> only when STATUS / REWORK_CAMPAIGN cite suite evidence.

> **Grundlage:** direkte Code-Lesung auf Branch `feat/app-integration-phase0-2`
> (HEAD `2094827`, Stand 2026-06-20). Status-Marker stützen sich auf reale Module,
> Test-Abdeckung und CLI-Verdrahtung — nicht auf `VISION.md`/`README.md`.

**Status-Legende**
- ✅ **real + getestet + verdrahtet** (nachweislich nutzbar, in CLI/Pipeline + Tests)
- 🟡 **vorhanden, aber begrenzt / optional** (gebaut + getestet, aber enger Scope, oder braucht optionale Dependency / Live-LLM / Owner-Gate)
- 🔩 **Stub / Platzhalter** (Vertrag steht, Implementierung fehlt)
- ❌ **Lücke** (deklariert, nicht gebaut)

**Kennzahlen (gemessen)**
- ~19.700 LOC allein in den Top-Level-Modulen von `src/gen/`, **24 Subpackages**.
- **~380+ Testdateien / ~3500 collected tests** (Stand rework; exact: `pytest --collect-only`).
- **~46 CLI-Modi** (`--mode`, Stand 2026-07-12 inkl. Fach-Pipelines + aero/humanoid-report + surface).
- **40 Physik-Validatoren** (`physics_validation.VALIDATORS`), **35 Auto-Select-Rezepte** (`physics_selection.RECIPES`), **27 Closed-Form-Physik-/FEM-Module**.
- Sehr wenige echte Stubs: 1 (`LeanKernelStub`); die ~21 „Unavailable"-Stellen sind **ehrliche Skip-Pfade** für optionale Dependencies (PyBullet, MuJoCo, GPU-Materials-Oracle, Postgres), keine Platzhalter.

---

## 1. Die drei Arme

### 1.1 Spezifizieren — Recherche → Spezifikation (α–δ) ✅
Idee → belegte, gegatete Bauspezifikation. Phasen α (Fakten) → β (Lösungsraum) → γ (Spezifikation + CAD) → δ (Physik).
- Module: `pipeline.py`, `agents/` (scout/scholar/skeptic/conductor/synthesizer/forge/architect), `clarification.py`, `completeness.py`, `refinement.py`.
- CLI: `--mode report | solution | spec | capstone | assess | print | realize`.
- Status: ✅ end-to-end, getestet (`test_phase_*`, `test_pipeline.py`), Gate-gestützt.

### 1.2 Entdecken — Discovery (`src/gen/discovery/`, 35 Module) ✅ / 🟡
Dimensionale symbolische Regression über **Power-Law/Π-Gruppen**; rediscovered bekannte Gesetze, gatet Red-Team-Fälle.
- Module: `engine.py`, `benchmark.py`, `tournament.py`, `controller.py`, `symbiosis.py` (Grok-Proposer), `universe_bridge.py`.
- CLI: `--mode research | discover-ode | feynman | campaign | council` ✅ offline; `aero-report | humanoid-report | surface` ✅ catalog/product surface.
- Status: ✅ Kern getestet + live (Rediscovery 6/6); 🟡 **Breite template-gebunden** (Power-Law/Π, eine ODE) — offene symbolische Suche ist Lücke.

### 1.3 Erfinden — Inventor (`src/gen/inventor/`, 15 Module) ✅ / 🟡
Deterministischer Loop: Safety → Council (Generate) → Grounding (δ-Gate) → Novelty → Pareto → Artefakte.
- Module: `loop.py`, `generate.py`, `score.py`, `novelty.py`, `safety.py`, `evolve_engine.py`, `archive.py` (MAP-Elites), `domains/` (base + **nur mechatronics**).
- CLI: `--mode invent | solve`.
- Status: ✅ Loop + Gates getestet (`test_inventor_*`, 10 Dateien); 🟡 Live-Generierung braucht LLM-Council; nur **eine Grounding-Domäne** (mechatronics).

---

## 2. Verifikations-/Gate-Kern (`src/gen/verification/`) ✅
Das Herz von GENESIS — „Gate statt Vorschlag". 4.213 LOC.
- `gates.py` (2.001 LOC — die Wächter C-1…C-18), `cross_model.py` (Modell-Familien-Trennung), `consensus.py` (N-Judge), `cegis.py` (Gegenbeispiel-geführte Verfeinerung), `smt.py`/`constraint_smt.py` (Z3-Feasibility), `derivation.py`, `units.py` (Einheiten-Algebra), `geometry.py`, `symbolic.py`, `drift_monitor.py`, `trustcore_adapter.py`.
- Status: ✅ durchgehend getestet (`test_gate*`, `test_constraint*`, `test_units.py`, `test_cross_model`), in `pipeline.py` verdrahtet.

## 3. Fakten-Ledger + Datenhaltung ✅ / 🟡
Jeder faktische Claim mit Quelle, Confidence, Verifikations-Status.
- `ledger/store.py` (InMemory, atomar, Quellenzwang) ✅ getestet (`test_ledger.py`).
- `ledger/postgres.py` (asyncpg, lazy) + `sql/001_ledger.sql` (Postgres/pgvector-Schema): 🟡 spiegelt den Vertrag, **in der Sandbox nicht lauffähig** (keine DB) — review-only.

## 4. LLM-/Agenten-Schicht ✅ / 🟡
- `agents/` (8): architect, conductor, forge, scholar, scout, skeptic, synthesizer — ✅ alle reviewed + getestet.
- `llm/` (9): `ollama.py` (lokal) ✅, `base.ScriptedLLM` (deterministisch) ✅, `claude_cli.py` + `grok_cli.py` (Abo-OAuth-CLI, keylos) 🟡 (live, braucht Login/Netz), `factory.py` (family-routed), `parsing.py` (adversarial gehärtet).
- Cross-Model-Default: Generator `grok-build`, Verifier `claude-opus-4-8` (andere Familie, Kernprinzip #3).

## 5. Physik-/FEM-/Validierungs-Module ✅ (gezählt)
**40 Validatoren / 35 Auto-Select-Rezepte / 27 Closed-Form-Module.** Auto-Select feuert aus measurand-Tags.
- Statik/Festigkeit: `structural.py`, `bracket_fem.py`, `fem.py`, `fem3d.py`, `fem3d_quadratic.py`, `plate_bending.py`, `plate_hole.py`, `bolted_joint.py`, `section_optimizer.py` (unified `propose_structural` for section + SIMP topology via `topology_optimizer.py`).
- Versagen: `buckling.py`, `fatigue.py`, `notch_fatigue.py`, `fracture.py`, `creep.py`, `torsion.py`, `pressure_vessel.py`, `contact.py` (Hertz).
- Thermik/Modal: `thermal.py`, `thermal_stress.py`, `modal.py`.
- Domänen-Achsen: `flight.py` (4 Flug-Achsen), `kinematics.py`, `actuation.py`, `compute.py`, `dynamics.py`, `digital_bus.py`.
- Querschnitt: `physics_validation.py` (VALIDATORS), `physics_selection.py` (RECIPES), `montecarlo.py`, `tolerance.py`, `dimensional_guard.py`, `mechanics_formulas.py`, `uncertainty.py`.
- Status: ✅ getestet (`test_*` je Modul), in den δ-Gate verdrahtet. Ehrliche Grenze: **Closed-Form-Erstauslegungs-Screens**, keine volle FEA-Suite.

## 6. CAD / Geometrie / Export ✅ / 🟡
- Geometrie-Kern: `brep.py`, `core/state.GeometryNode` (CSG: box/cyl/sphere + boolean + fillet).
- Export: `export/openscad.py` ✅, `export/build123d.py` (OCCT) 🟡 optional, `export/stl.py` + `export/brep_stl.py` ✅, `export/markdown.py` (Bauanleitung) ✅, `export/assembly.py`.
- Druckbarkeit: `printability.py`, `orientation.py`, `mesh_integrity.py` (watertight-Beweis) ✅.
- Fertigung: `cad/manufacturing_check.py` (CNC/Laser/PCB-DFM), `cad/gcode.py` (verifiziert), `cad/kicad.py`, `cad/cost_model.py`, `dfm.py`, `costing.py`, `tolerance.py`.
- Status: ✅ getestet + CLI `--format scad|b123d|stl`; 🟡 **Fidelity auf Primitive begrenzt** (kein sweep/loft/shell).

## 7. Elektronik ✅ / 🟡
- `electronics.py` (1.091 LOC): Analog, Power-Tree, ERC, KiCad-Netliste, interner DRC, Routing. `circuit.py`, `chip_selection.py` (geerdeter Katalog + Compute-Gate).
- CLI: `--mode chip`. Status: ✅ getestet (`test_electronics`, `test_kicad`, `test_elektriker`); ✅ DRC thresholds fully named/sourced (DRC_* + AUTO_PLACE_* + explicit harness-vs-PCB+dfm ref; WORK_QUEUE Nebenfund addressed + follow-up polish).

## 8. Simulation / Mehrkörper 🟡
- `simulation/multibody.py` (RK4, **Einzel-DOF-Pendel**, energie-validiert) ✅.
- `simulation/pybullet_sim.py` (Voll-Kontakt) + `simulation/backends.py` (MuJoCo-Adapter): 🟡 **optionale Deps**, sauberer Skip ohne sie; nur Einzelgelenk/fixed-base.
- `simulation/runner.py`, `surrogate.py`, `quantum_opt.py`. `urdf_bridge.py` (URDF-Export für externe Engines).
- Status: 🟡 deterministischer Kern echt, aber **keine Mehrkörper-Kontaktdynamik im eigenen Code**.

## 9. Fach-Pipelines / Realisierung (`src/gen/pipelines/`, 11 Disziplinen) ✅
Vollständige Realisierungskette (`--mode realize`).
- `integrator.py` (Orchestrierung), `architekt`, `designer`, `elektriker`, `fertigungs`, `ingenieur`, `physiker`, `regulatorik`, `software`, `techniker`, `wirtschaft`.
  - CLI (REWORK 2026-07-11): `--mode fach` (alle) oder einzeln `--mode architekt|…|wirtschaft` — first-stone, offline, ehrliche Lücken.
  - Status: ✅ Mapper + Tests; 🟡 **first-stone depth** (kein live Wissensbasis/Lieferanten-API).
- Status: ✅ **jede Disziplin getestet** (`test_architekt/designer/elektriker/physiker/techniker/regulatorik/wirtschaft/integrator.py`).

## 10. Externe Integration + Connectoren + Oracles ✅ / 🟡
- `external/registry.py`: lizenz-disziplinierte Binding-Registry (LicenseClass/IntegrationMode, hebt `LicenseViolation`) ✅.
- `external/oracle.py`: `external_oracle()`-Plugin-Typ — externe Antworten gehen **nur als gegatete UNVERIFIED-Claims** ins Ledger ✅.
- `external/materials_oracle.py`: Materials-Energy-Oracle (ORB-Klasse) — 🟡 echter Adapter wirft `MaterialsOracleUnavailable` ohne GPU; **Offline-Twin** beweist nur die Verdrahtung.
- Discovery-Connectoren: `tools/sources/openalex.py`, `tools/sources/patents.py` (PatentsView) auf dem SearchBackend-Seam ✅ getestet (`test_external_*`).

## 11. Mathe-Beweis-Kernel ✅ / 🔩
- `proof_kernels.Z3IdentityKernel`: **echte QF_NRA-Entscheidungsprozedur** für polynomiale/rationale Identitäten (∀ vars: lhs==rhs via UNSAT) ✅.
- `discovery/proof_loop.py`: mpmath-Hochpräzisions-Prefilter (sound refuter) + sympy-simplify (heuristisch) + z3-Kernel → Label **„Satz"** nur kernel-bewiesen ✅.
- `proof_kernels.LeanKernelStub`: 🔩 kein Lean/Coq installiert. **Transzendentes** bleibt „Kandidat" (Evidenz, kein Beweis).
- Status: ✅ getestet (`test_proof_kernels`, `test_proof_tier`, `test_discovery_proof_loop`).

## 12. Discovery-Methoden (Detail) ✅ / 🟡
- `sindy.py` (eine skalare 2.-Ordnung-ODE aus Simulatordaten) ✅, `multiterm.py` (additive Gesetze) ✅, `transcendental.py` (`y=C·f(α·π)+D`) ✅, `composition.py` (Minimal-Korrektur) ✅, `active_resolution.py` / `active_search.py` (diskriminierende Messung) ✅, `assumption_annihilator.py`, `separability.py`, `first_principles.py`, `cosmic_insight.py`, `reality_fork.py`.
- Hygiene/Validierung: `srbench_hygiene.py` (gegen Schein-Entdeckung) ✅, `validation.py` (Out-of-Sample) ✅, `uncertainty.py`, `canonical.py` (Dedup).
- RL-Ökosystem: `rl_env.py`, `reward.py`, `knowledge_graph.py`, `concept_utility.py`, `tree_search.py` (Gate als Oracle).
- Status: ✅ 22 Discovery-Testdateien; 🟡 alle innerhalb der Template-Familien.

## 13. Inventor-Submodule ✅
`safety.py` (gestaffelter Safety-Screen), `novelty.py` (Prior-Art-Distanz), `score.py` (5-Achsen-Pareto), `archive.py` (MAP-Elites), `evolve_engine.py` (Rekombination), `optimize.py`, `refinement.py`, `eval.py` (Integritäts-Eval-Harness). Status: ✅ getestet.

## 14. HORIZON / Grenzverschiebung (`src/gen/grenzverschiebung/`, 14 Module) 🟡
Meta-/Vorausschau-Layer: `lumencrucible.py` (Selbst-Verbesserung), `technology_builder.py`, `technology_roadmapper.py`, `breakthrough_watch.py`, `capability_gap_analyzer.py`, `experiment_designer.py`, `learning_integrator.py`, `safety_ladder.py`, `milestone_builder.py`, `teststand_architect.py`, `boundary_reviser.py`, `development_front.py`, `bench_test_runner.py`.
- HORIZON-Zertifikat-Gates: `reality.py` (δ⁺), `coverage.py` (δ⁺ Deckung), `inverse_design.py` (γ⁺ Pareto), `seams.py` (ε), `memory_fabric.py` (ζ), `omega.py` (Ω).
- CLI: `--mode breakthrough` (via `extensions/breakthrough_bridge.py`).
- Status: 🟡 gebaut + teils getestet (`test_experiment_designer`, `test_learning_integrator`, `test_technology*`), aber **explorativer/meta** — eher angestrebte Ausbaustufe als Alltagsfähigkeit.

## 15. Wissensbasis + Retrieval/Tools (`src/gen/tools/`, 11 + `wissensbasis/`) ✅ / 🟡
- Quellen: `tools/codata.py` (Naturkonstanten), `tools/dlmf.py` (math. Funktionen), `tools/wikidata.py`, `tools/arxiv_backend.py`, `tools/sources/` (OpenAlex/Patents).
- Retrieval: `tools/rag_backend.py` (In-Memory-RAG), `tools/ollama_embedder.py` (lokale Embeddings), `tools/search.py`, `tools/fetch.py`/`http.py` (SSRF-gehärtet), `tools/formula_backend.py`.
- `wissensbasis/`: `store.py`, `evidence.py`, `bio_molecular.py` (🟡 Bio-Komponenten-Rezepte, Seed-Daten).
- Status: ✅ Retrieval/Quellen getestet + im Scout verdrahtet.

## 16. Memory / Lernmaschine 🟡
- `memory/` (vendored `anamnesis_mem`: capture/retrieve/storage) + `memory/verified_facts.py`; `memory_fabric.py` (ζ-Gate).
- `lernmaschine/engine.py`, `integration/` (audited_run, drift, identity_research_hook), `research_promotion.py`.
- Status: 🟡 vorhanden + getestet, aber peripher zum Kern-Workflow.

## 17. Web-UI ✅
- `web/app.py` (FastAPI) + `web/static/index.html`; Endpunkte für report/spec/assess/print/research/invent, gate-/printability-/ratification-Dicts.
- Start: `start-genesis-web.bat` / `scripts/start-genesis-web.ps1` (uvicorn).
- Status: ✅ getestet (`test_webapp.py`).

## 18. MCPs 🟡
- `mcps/`: `asya-state`, `pinecone`, `project-state` (Konfig/State-Server). 🟡 Hilfs-Infrastruktur, nicht Teil des verifizierten Kerns.

## 19. Querschnitt — Determinismus, Audit, Sicherheit, Telemetrie ✅
- `security.py`, `telemetry.py`, `audit/run_audit.py` (signiertes Audit), `calibration.py` (Split-Conformal), `ratification.py` (HITL), `goldset.py` (Eval-Harness), `evaluation.py` (Leak/False-Alarm), `grounding_integrity.py`, `constraint_consistency.py`, `geometry_verification.py`, `reality.py`.
- Determinismus: `run_id`, Checkpoint-Resume, byte-stabile Prompts (Kernprinzip #5). Status: ✅ getestet.

---

## 20. CLI-Modi (`cli.py`) — siehe STATUS für ehrliche LIVE/DEMO-Labels

> REWORK: `frontier`, `fach`, `architekt`…`wirtschaft` (10 Fach-Pipelines) hinzugefügt. Nicht jeder Mode ist LIVE-α; viele sind offline first-stone / demo.

`gen --mode <MODE>` — Default `report`. Zusätzlich `--format text|md|scad|b123d|stl`, `--demo`, `--live` (Council), `--generator`/`--verifier` (Cross-Model), `--checkpoint-dir`.

| Modus | Funktion | Status |
|---|---|---|
| `report` | Phase α: belegte Fakten | ✅ |
| `solution` | Phase β: Lösungsraum | ✅ |
| `spec` | Phase γ: Bauspezifikation (+ CAD-Format) | ✅ |
| `capstone` | komplette γ-Tiefe durch alle Gates (demo) | ✅ |
| `assess` | Quality-Engine-Verdikt (Klärung+δ+Constraints+Grounding) | ✅ |
| `print` | Druckbarkeits-Verdikt + STL-Mesh-Integrität | ✅ |
| `bundle` | Bauanleitung+SCAD+STL+BOM+MANIFEST+MISSING | ✅ |
| `realize` | volle Realisierungskette (DFM/Lern/Zeichnungen/Regulatorik) | ✅ |
| `humanoid` | 2 Ganzkörper-Humanoide (gegatet, CSG-Teile) | ✅/🟡 |
| `ideas` / `future_ideas` | 5 vorausschauende Ideen, physics_verified | ✅ |
| `dream` | 3 visionäre Konzepte (grok-geerdet) | ✅ |
| `section` | minimaler-Material-Querschnitts-Optimierer | ✅ |
| `training` | ML-Trainingsplan mit ehrlichem Grenz-Gate | ✅ |
| `chip` | Chip-Auswahl nach Anforderung (Compute-Gate) | ✅ |
| `council` | Cross-Model-Council (offline default, `--live` real) | ✅/🟡 |
| `research` | Formel-Identitäts-Beweis (z3/sympy/mpmath) | ✅ |
| `discover-ode` | SINDy-ODE-Entdeckung aus Simulator-Trajektorie | ✅ |
| `feynman` | Feynman-SRDB-Rediscovery-Benchmark | ✅ |
| `campaign` | komponierte gegatete Discovery-Kampagne | ✅ |
| `invent` / `solve` | Inventor-Loop (Feld bzw. Problem) | ✅/🟡 |
| `breakthrough` | HORIZON-Grenzverschiebung | 🟡 |
| `eval` / `protocol` | Eval-Harness / Protokoll | ✅ |

---

## Gesamtbild (nüchtern)

**Nachweislich nutzbar (✅):** der Verifikations-/Gate-Kern, das Fakten-Ledger (in-memory), die α–δ-Spezifikationskette mit 40 Physik-Validatoren, CSG-CAD + Export + Druckbarkeits-Beweis, Elektronik/DFM/G-Code/KiCad, die 11 Fach-Pipelines (Realisierung), der Discovery-Kern (Power-Law-Rediscovery + polynomialer z3-Beweis), der Inventor-Loop, die Wissensbasis/Retrieval-Schicht, das Web-UI und 24 CLI-Modi — alles durch 1755 Tests und CLI-Verdrahtung gedeckt, offline + deterministisch.

**Vorhanden, aber begrenzt/optional (🟡):** Mehrkörper-Simulation (nur Einzel-DOF eigen; PyBullet/MuJoCo optional), Postgres-Ledger (kein DB-Lauf in der Sandbox), Live-LLM-Pfade (claude/grok-CLI, owner-/netz-gated), Materials-Oracle (GPU-gated, nur Offline-Twin), CAD-Fidelity (Primitive), Inventor-Grounding (eine Domäne), HORIZON/Grenzverschiebung (explorativ).

**Stub/Lücke (🔩/❌):** Lean/Coq-Beweis-Kernel (Stub) → transzendente Beweise nicht maschinengeschlossen; offene symbolische/GP-Suche jenseits der Templates; gelernter Ganzkörper-Regler/Sim2Real; mechanische Detail-CAD.

**Angestrebt vs. real:** Die große HORIZON-/„Breakthrough"-/Universe-Explorer-Rahmung ist teils gebaut, teils Vision; der **verifizierte, getestete Kern ist deutlich enger, aber echt** — und das Projekt markiert diese Grenze konsequent selbst (Gates, „Kandidat" vs. „Satz", `MISSING.md`).
