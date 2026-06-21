# Externe Integration — Katalog → Seam-Karte (GENESIS)

> **Zweck.** Jedes externe Modell / Werkzeug / jede freie API aus den zwei Katalogen
> (`MODELL_KATALOG_EXTERN_2026-06-19.md`, `WERKZEUGE_DATEN_SIMULATION_2026-06-19.md`) wird hier **genau einer
> gebauten Naht** zugeordnet, mit **Lizenz** und **Status**. Regel (hart, CLAUDE.md §1 / INVENTOR §10¾):
> **keine Anbindung ohne (a) eine Naht und (b) eine ledger-belegte Lizenz.** Der Kern linkt nur permissiv
> (Apache/MIT/BSD/CC0/CC-BY); Copyleft nur als Separat-Prozess-Orakel; NC ist im kommerziellen Kern verboten.
> Stand: 2026-06-20. Offline-Default ist immer das Test-Rückgrat; jede externe Anbindung ist opt-in.

## Status-Legende
- 🟢 **live-fähig** — Offline-Default gebaut **oder** freie API ohne Key live erreichbar (heute nutzbar).
- 🟡 **opt-in-pip** — Adapter gebaut + import-gegated; Tool per `pip` nachrüstbar, dann live.
- 🔴 **BLOCKED** — braucht GPU / Julia / Lean / API-Key / Owner-Freigabe; Offline-Zwilling beweist die Verdrahtung.

## Die sechs gebauten Nähte

| Naht | Modul | Offline-Default (Test-Rückgrat) | Externer Eintritt |
|---|---|---|---|
| **Lizenz-Ledger** | `gen.external.registry` | — (Pflicht-Gate für ALLE) | `external_binding()` → `record_binding()` (VERIFIED-Claim) |
| **Externes Orakel** | `gen.external.oracle` | Fake-Orakel (Tests) | `ExternalOracle.query()` → `record_oracle_claim()` (UNVERIFIED-Claim) |
| **Such-Backend** | `gen.core.interfaces.SearchBackend` | RAG/arXiv (gebaut) | `tools/sources/*` (OpenAlex, PatentsView gebaut) |
| **Simulator-Backend** | `gen.simulation.backends` | `MultibodyPendulumBackend` (RK4) | `SimulatorBackend.simulate()` (MuJoCo-Adapter) |
| **Optimierer** | `gen.inventor.optimize` | `ParetoOptimizer` (inverse_design) | `Optimizer.select()` (pymoo-Adapter) |
| **Evolve-Engine** | `gen.inventor.evolve_engine` | `MapElitesEngine` (MAP-Elites) | `EvolveEngine.evolve()` (OpenEvolve-Adapter) |
| **Beweis-Kernel** | `gen.proof_kernels` / `discovery.proof_loop` | `Z3IdentityKernel` (z3 QF_NRA) | `ProofKernel`-Slot (Lean/Goedel) |
| **SR-Engine-Judge** | `gen.discovery.engine` (`judge_candidate`) | multiterm/transcendental (gebaut) | extern erzeugte Kandidaten werden ohnehin gegated |

---

## 1 · Foundation-Modelle → `ExternalOracle` (gegateter Claim, nie Roh-Wahrheit) + Lizenz-Ledger

Jeder Modell-Output ist ein **UNVERIFIED**-Claim mit Provenance+Unsicherheit; ein deterministisches Gate
entscheidet. Google-NC-Modelle sind durch offene Alternativen ERSETZT (vom Registry-Gate erzwungen: NC ist
nicht konstruierbar).

### Biologie / Protein
| Modell | Lizenz | Status | Naht | Ersetzt (NC) |
|---|---|---|---|---|
| **Boltz-1/2** | MIT | 🔴 GPU | ExternalOracle | AlphaFold 3 (CC-BY-NC-SA) |
| **Chai-1 / Protenix / OpenFold3** | Apache-2.0 | 🔴 GPU | ExternalOracle | AlphaFold 3 |
| **RoseTTAFold-All-Atom** | BSD | 🔴 GPU | ExternalOracle | — |
| **ESMFold + ESM-2** | MIT | 🔴 GPU | ExternalOracle | — |
| **RFdiffusion / ProteinMPNN / DiffDock** | BSD / MIT / MIT | 🔴 GPU | ExternalOracle | — |

### Materialien / Chemie
| Modell | Lizenz | Status | Naht | Ersetzt (NC) |
|---|---|---|---|---|
| **Orbital ORB v3** | Apache-2.0 | 🔴 GPU | ExternalOracle (+ Simulator für Relax) | GNoME (CC-BY-NC) |
| **MS MatterSim / CHGNet / M3GNet** | MIT / BSD-3 / BSD-3 | 🔴 GPU | ExternalOracle | GNoME |
| **MACE-MP-0** (nur dieser Checkpoint) | MIT | 🔴 GPU | ExternalOracle | MACE-OMAT/MATPES (ASL-NC ❌) |
| **MS MatterGen / REINVENT 4** | MIT / Apache-2.0 | 🔴 GPU | ExternalOracle | AlphaEvolve-Materialien |
| **SevenNet** | GPL-3 | 🔴 GPU + Prozess-Orakel | ExternalOracle (IntegrationMode.PROCESS) | — |

### Wetter / Klima / Erde
| Modell | Lizenz | Status | Naht | Ersetzt (NC) |
|---|---|---|---|---|
| **MS Aurora** | MIT | 🔴 GPU | ExternalOracle | GraphCast/GenCast (CC-BY-NC-SA) |
| **ECMWF AIFS-Single** | CC-BY 4.0 | 🔴 GPU | ExternalOracle | GraphCast |
| **NVIDIA FourCastNet 3** | Apache-2.0 | 🔴 GPU | ExternalOracle | GenCast |

### Google-direkt-nutzbar (permissiv)
AlphaFold-DB (CC-BY) → **SearchBackend/Daten**; AlphaFold 2 / AlphaGeometry 1 (Apache+CC-BY) → ExternalOracle;
Gemma 4 (Apache-2.0) → **LLM-Proposer** (bestehender `LLMClient`-Seam). **NC bleibt draußen:** AlphaFold 3,
AlphaGenome, GraphCast/GenCast-Gewichte, GNoME-Daten — Registry-Gate verbietet sie.

---

## 2 · Simulatoren → `SimulatorBackend` (Prozess-/Library-Orakel)

| Simulator | Domäne | Lizenz | Status | Naht / Notiz |
|---|---|---|---|---|
| **MultibodyPendulumBackend** (in-house RK4) | Mechanik | — | 🟢 | Offline-Default, gebaut + getestet |
| **PyBullet** (in-house) | Mehrkörper/Kontakt | zlib/MIT | 🟢 | schon in GENESIS (`simulation/pybullet_sim.py`) |
| **MuJoCo** | Mehrkörper/Robotik | Apache-2.0 | 🟡 `pip mujoco` | `MujocoPendulumBackend` gebaut, import-gegated |
| **OpenMM** | Molekulardynamik | MIT | 🟡 | gleicher Seam, Adapter nachrüstbar |
| **Cantera** | Reaktionskinetik | BSD | 🟡 | gleicher Seam |
| **ngspice** | Analog-Schaltung | BSD | 🟡 | ergänzt bestehende MNA-Sim |
| **Xyce** | Analog-Schaltung | GPL-3 | 🔴 Prozess-Orakel | nur als Separat-Prozess (Copyleft-Firewall) |

---

## 3 · Freie Daten-APIs → `SearchBackend` (Discovery, Prior-Art, Daten-Orakel)

| API | Inhalt | Lizenz | Status | Naht |
|---|---|---|---|---|
| **OpenAlex** | 250M Werke | **CC0** | 🟢 **live verifiziert** (200, echte IDs) | `tools/sources/openalex.py` gebaut |
| **PatentsView** | US-Patentkorpus | public domain | 🟡 Key (`X-Api-Key`) | `tools/sources/patents.py` gebaut; Key in Transport gebacken |
| **arXiv / Semantic Scholar / Wikidata / CODATA** | Literatur/Konstanten | gemischt | 🟢 | schon in GENESIS (`tools/{arxiv_backend,…}`) |
| **PubChem** | 119M Moleküle | keine Restriktion | 🟡 | gleiches Connector-Muster (PUG-REST) |
| **RCSB PDB** | 230K Strukturen | **CC0** | 🟡 | gleiches Muster (REST/GraphQL) |
| **UniProt** | 190M Sequenzen | CC-BY 4.0 | 🟡 | gleiches Muster |
| **Materials Project** | 150K Materialien | CC-BY 4.0 (GNoME-Teil NC ❌) | 🔴 Key (`mp-api`) | Registry trennt CC-BY-Teil von NC-Teil |
| **Google Patents (BigQuery)** | gesamtes Korpus | frei | 🔴 GCP-Key | gleicher Seam, BigQuery-Transport |

> **Lizenz-Wachsamkeit (im Code erzwungen):** Semantic-Scholar-NC-Records, PMC-NC-Subset, Materials-Project-
> GNoME (NC), ZINC (patentgeschützte Records) → Registry-Gate lehnt NC im Kern ab.

---

## 4 · Optimierung → `gen.inventor.optimize`

| Tool | Funktion | Lizenz | Status | Naht |
|---|---|---|---|---|
| **ParetoOptimizer** (in-house) | Non-Dominanz-Auswahl | — | 🟢 | Offline-Default, gebaut |
| **pymoo** | Multi-Objektiv (NSGA-II) | Apache-2.0 | 🟡 `pip pymoo` | `PymooOptimizer` gebaut, import-gegated |
| **OR-Tools** | CP-SAT/LP | Apache-2.0 | 🟡 | gleicher Seam |
| **Optuna** | Hyperparam/BBO | MIT | 🟡 | gleicher Seam |
| **BoTorch / Ax** | bayes. Exp.-Design (EIG/T-Opt) | MIT | 🟡 | TR5b: hinter `active_resolution`-Naht (Offline-Default = TR5) |

---

## 5 · Evolution / Open-Ended → `gen.inventor.evolve_engine`

| Engine | Funktion | Lizenz | Status | Naht |
|---|---|---|---|---|
| **MapElitesEngine** (in-house) | MAP-Elites + Inseln | — | 🟢 | Offline-Default, gebaut |
| **OpenEvolve** | LLM-Evolution | Apache-2.0 | 🟡 `pip` | `OpenEvolveEngine` gebaut, import-gegated |
| **ShinkaEvolve** (Sakana) | LLM-Evolution | Apache-2.0 | 🟡 | gleicher Seam |
| **FunSearch** | Programm-Suche | Apache-2.0 | 🟡 | gleicher Seam (du bringst das LLM) |
| ~~AlphaEvolve~~ | geschlossen | — | ❌ | ersetzt durch OpenEvolve/ShinkaEvolve |

---

## 6 · Symbolische Regression + Beweis → Engine-Judge / Beweis-Kernel

| Tool | Funktion | Lizenz | Status | Naht |
|---|---|---|---|---|
| **engine + multiterm + transcendental** (in-house) | dimensionale SR | — | 🟢 | Offline-Default, gebaut |
| **PySINDy** | SINDy-Adapter | MIT | 🟡 `pip pysindy` | TR1b hinter `discovery.sindy`-Naht (Offline-STLSQ = Default) |
| **PySR** | SR (Julia-Backend) | Apache-2.0 | 🔴 Julia | TR7 hinter Engine-`judge_candidate` (extern erzeugte Kand. werden gegated) |
| **PhySO** | Physik-SR (Deep RL) | MIT | 🔴 GPU | gleicher Engine-Judge-Seam |
| **z3 QF_NRA** (in-house) | Polynom/Rational-Beweis | MIT | 🟢 | Offline-Default `Z3IdentityKernel`, gebaut |
| **Lean + Goedel-Prover-V2 / Kimina / LeanDojo** | formale Beweise | Apache / Apache / MIT | 🔴 Lean | TR4b: `ProofKernel`-Slot (Offline-Zwilling = z3) |
| ~~AlphaProof~~ | geschlossen | — | ❌ | ersetzt durch Goedel/Kimina |

---

## 7 · Provenance-/Workflow-Backbone (dokumentierte Option)

| Tool | Funktion | Lizenz | Status | Notiz |
|---|---|---|---|---|
| **AiiDA** ⭐ | provenance-getrackte Sim-Kampagnen | MIT | 🟡 | passt zum Ledger-Ethos; Backbone-Kandidat für den Entdeckungs-Loop |
| **PyKEEN / txtai / RDFLib** | KG-Embeddings / Reasoning | MIT / Apache / BSD | 🟡 | ergänzt `knowledge_graph` |
| **MLflow / DVC / Snakemake** | Experiment/Daten-Versionierung | Apache / Apache / MIT | 🟡 | optionale Telemetrie/Repro-Schicht |
| **Neo4j Community** | Graph-DB | GPL | 🔴 Prozess-Server | nur als Separat-Prozess (Copyleft-Firewall) |

---

## BLOCKED-Übersicht (Offline-Zwilling beweist die Verdrahtung)

- **GPU-Foundation-Orakel** (Boltz-2/ORB/Aurora/…) → `ExternalOracle` (TC3); Owner-GPU/API. Zwilling: Fake-Orakel.
- **PatentsView/Materials-Project-Volllast** → API-Key. Zwilling: Fixture-Tests (TC2).
- **PySR/PhySO** (Julia/GPU) → TR7-Engine-Judge. Zwilling: in-house SR.
- **Lean/Goedel-Kernel** → TR4b-`ProofKernel`-Slot. Zwilling: z3-Kernel.
- **MuJoCo/OpenMM/Cantera/ngspice** → `SimulatorBackend` (TC4); `pip`-opt-in. Zwilling: RK4/PyBullet/MNA.
- **pymoo/openevolve/Ax/pysindy** → opt-in-`pip`-Adapter gebaut. Zwilling: in-house Default.

**Invariante:** Keine Zeile dieser Karte ist ohne (Naht + Lizenz) — und jede live geschaltete Anbindung wird
über `external.registry.record_binding()` als Lizenz-Claim ins Ledger geschrieben, bevor ihr Output (über
`external.oracle.record_oracle_claim()`, gegatet, UNVERIFIED) genutzt wird.
