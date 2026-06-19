# Simulatoren, große offene Datensätze & Entwicklungs-Werkzeuge — Katalog für GENESIS

> Tiefe belegte Suche (2026-06-19, 4 Teams) als Ergänzung zu `MODELL_KATALOG_EXTERN`
> (Foundation-Modelle) und `FORSCHUNG_AUTONOMES_ERFINDEN` (Methoden). Fokus: was GENESIS als
> **Simulations-Orakel, Datenquelle und Dev-Toolchain** einbauen kann — und was *kommerziell* geht.

---

## 0 · Kurzfazit (die drei Fragen beantwortet)

1. **Mehr offene Simulatoren?** Ja, für **jede physikalische Domäne** — von Mehrkörper/Robotik über CFD/FEM/Elektromagnetik bis Molekulardynamik, Quantenchemie, Schaltungen, Quantencomputer und Systembiologie. Das ersetzt GENESIS' heutige dünne Stubs (PyBullet + Basis-FEM + Schaltungssim) durch **echte Engines**.
2. **Die „Milliarden-Daten" — und Zugriff in GENESIS?** Ja: PubChem (119M Moleküle), ZINC-22 (**54,9 Mrd.** Moleküle), GDB-17 (**166 Mrd.**), AlphaFold-DB (214M Strukturen), Materials Project/NOMAD/OMat24, ERA5 (10 PB), **OpenAlex (250M Paper, CC0)**, Patente via BigQuery. Zugriff über **freie REST-APIs / Python-Clients / BigQuery / HuggingFace / AWS Open Data** — und **mehrere sind JETZT schon via MCP in dieser Umgebung erreichbar** (ChEMBL, PubMed, ClinicalTrials, bioRxiv, HuggingFace Hub) + GENESIS' bestehende Connectoren (Semantic Scholar, arXiv, Wikidata, CODATA).
3. **Mehr Erfindungs-/Entwicklungs-Werkzeuge?** Ja: Optimierung (OR-Tools, pymoo, Optuna, BoTorch/Ax), generatives/inverses Design (Modulus-PINNs, Topologie-Opt), Knowledge Graphs (PyKEEN, txtai), CAD/CAE/EDA (CadQuery, build123d, FreeCAD, KiCad, Gmsh), RL (Gymnasium, SB3) und — der Standout — **AiiDA**: provenance-getrackte automatisierte Simulations-Kampagnen (passt exakt zu GENESIS' Ledger-Ethos).

**Großes Bild:** Mit diesen drei Katalogen kann GENESIS quer durch **fast die ganze Wissenschaft** geerdet werden — Physik, Chemie, Biologie, Materialien, Elektronik —, fast alles aus permissiv lizenzierten offenen Werkzeugen.

---

## Teil A · Simulatoren (Orakel, die GENESIS anrufen kann)

**Wichtig (Lizenz-Muster):** GENESIS ruft Simulatoren als **separaten Prozess** auf → Output wird gegateter Claim. In diesem Muster sind **auch GPL-Simulatoren nutzbar** (kein statisches Linken). Permissiv = sauber einbettbar. **ASE (LGPL)** ist die Python-Klammer über fast alle Atomistik-Engines.

### Continuum / Mechanik / Robotik
| Engine | Domäne | Lizenz | Komm. | Python |
|---|---|---|---|---|
| **Kratos Multiphysics** | FEM Struktur/CFD/DEM/FSI | BSD-4 | ✅ | `pip KratosMultiphysics-all` |
| **MuJoCo** | Mehrkörper/Kontakt/Robotik | Apache-2.0 | ✅ | `pip mujoco` |
| **PyBullet** | Starr/Weich-Körper (schon in GENESIS) | zlib | ✅ | `pip pybullet` |
| **Project Chrono** | Mehrkörper + FEA + Granular | BSD-3 | ✅ | `conda pychrono` |
| **Drake** | Mehrkörper + Optimierung/Regelung | BSD-3 | ✅ | `pip drake` |
| **FEniCSx** | allgemeine FEM-PDEs | LGPL-3 | ✅ | conda (Linux/WSL) |
| **SfePy / PyNiteFEA** | FEM / Struktur (leicht) | BSD / MIT | ✅ | `pip sfepy` / `PyNiteFEA` |
| **OpenFOAM · SU2 · PyFR** | CFD | GPL-3 / LGPL / BSD-3 | ✅* | PyFoam / pysu2 / `pip pyfr` |
| **Meep · openEMS** | Elektromagnetik/Photonik (FDTD) | GPL-2/3 | ✅* | `conda pymeep` |
| **SimPy · Mesa** | Discrete-Event / Agenten-Modelle | MIT / Apache | ✅ | `pip simpy` / `mesa` |

### Atomistik / Quanten / Chemie / Elektronik / Bio
| Engine | Domäne | Lizenz | Komm. | Python |
|---|---|---|---|---|
| **OpenMM** | Molekulardynamik (GPU, programmierbar) | MIT-Kern | ✅ | nativ |
| **GROMACS · LAMMPS · HOOMD** | MD (Biomol / atomistisch / Soft Matter) | LGPL / GPL / BSD | ✅* | gmxapi / `lammps` / nativ |
| **PySCF** | Quantenchemie/DFT (molekular) | Apache-2.0 | ✅ | nativ |
| **Psi4 · NWChem** | Ab-initio QC | LGPL-3 / ECL-2.0 | ✅ | Treiber / ASE |
| **xtb · DFTB+** | schnelle semi-empirische QC (Screening) | LGPL-3 | ✅ | `conda` + ASE |
| **Quantum ESPRESSO · ABINIT · GPAW · CP2K** | Festkörper-DFT | GPL | ✅* | via ASE/AbiPy |
| **Cantera · RMG · RDKit** | Reaktionskinetik / Mechanismus / Cheminformatik | BSD / MIT / BSD | ✅ | nativ |
| **ngspice · Xyce · Verilator** | Analog-/Digital-Schaltungen | BSD / GPL-3 / LGPL+Artistic | ✅* | PySpice / cocotb |
| **Qiskit Aer · Cirq · PennyLane** | Quantencomputer-Simulation | Apache-2.0 | ✅ | nativ |
| **Tellurium · COPASI · BioNetGen · NEURON** | Systembiologie / Neuro | Apache / Artistic-2 / MIT / BSD | ✅ | nativ |

\* GPL-Engines: als externes Orakel-Prozess nutzen, nicht statisch linken.

---

## Teil B · Große offene Datensätze („Milliarden") + Zugriff

**🔌 = jetzt schon via MCP/Connector in GENESIS erreichbar.**

### Chemie
| Quelle | Größe | Lizenz | Komm. | Zugriff |
|---|---|---|---|---|
| **PubChem** | 119M Verbindungen | keine Restriktion | ✅ | PUG-REST-API, PubChemPy, FTP |
| **ChEMBL** 🔌 | 2,4M Verb. / 20M Aktivitäten | CC-BY-SA 3.0 | ✅ | REST, Python-Client, **MCP** |
| **ZINC-22** | **54,9 Mrd.** Moleküle | akademisch (uneindeutig) | ⚠️ | CartBlanche, AWS/OCI |
| **GDB-17** | **166 Mrd.** enumeriert | offen (Zenodo) | ✅ | gdb.unibe.ch / Zenodo |
| **Open Reaction DB** | >2M Reaktionen | CC-BY-SA 4.0 | ✅ | GitHub `ord-data`, `ord-schema` |
| **QM9 / QM7-X** | 134K Mol. + DFT-Props | offen | ✅ | quantum-machine.org, HF, TFDS |

### Biologie
| Quelle | Größe | Lizenz | Komm. | Zugriff |
|---|---|---|---|---|
| **AlphaFold-DB** | **214M** Strukturen | CC-BY 4.0 | ✅ | API, EBI-FTP, Google Cloud |
| **RCSB PDB** | 230K exp. Strukturen | **CC0** | ✅ | Data/Search-API (REST+GraphQL) |
| **UniProt** | 190M+ Sequenzen | CC-BY 4.0 | ✅ | REST `rest.uniprot.org`, SPARQL |
| **PubMed / PMC** 🔌 | 37M / 11,8M Volltext | gemischt (komm. Subset) | ⚠️ | E-utilities, **MCP**, AWS |
| **ClinicalTrials** 🔌 | alle Studien | offen | ✅ | API, **MCP** |
| **bioRxiv** 🔌 | Preprints | offen | ✅ | API, **MCP** |

### Materialien
| Quelle | Größe | Lizenz | Komm. | Zugriff |
|---|---|---|---|---|
| **NOMAD** | >12M Einträge (größte) | CC-BY 4.0 | ✅ | API + OPTIMADE |
| **Materials Project** | 150K+ Materialien | CC-BY 4.0 (GNoME-Teil NC!) | ✅ | `mp-api`, AWS Open Data |
| **OQMD · AFLOW · JARVIS** | 1,4M / 3,5M / 40K+ | CC-BY / gemischt / NIST-public | ✅/⚠️ | REST + OPTIMADE |
| **OMat24 (Meta)** | **110M** DFT-Rechnungen | CC-BY 4.0 | ✅ | HuggingFace 🔌 |
| **Open Catalyst OC20/22** | 1,3M / 62K Relaxationen | CC-BY 4.0 | ✅ | fair-chem, HF 🔌 |

### Physik / Klima / Literatur / Patente / Wissen
| Quelle | Größe | Lizenz | Komm. | Zugriff |
|---|---|---|---|---|
| **ERA5** (Klima) | ~10 PB | Copernicus (Attribution) | ✅ | CDS-API, AWS, Earth Engine |
| **NASA Earthdata** | >100 PB | US-Gov offen | ✅ | CMR-API, Earthdata Cloud |
| **OpenAlex** | **250M** Werke | **CC0** | ✅ | freie REST-API, S3-Snapshot |
| **Semantic Scholar** 🔌 | 200M Paper, 2,4 Mrd. Zitate | gemischt (NC-Teile) | ⚠️ | API (in GENESIS verdrahtet) |
| **arXiv** 🔌 | 2,4M Preprints | Metadaten CC0 | ✅/⚠️ | API (in GENESIS), AWS-S3 |
| **USPTO PatentsView · Google Patents** | gesamtes Patentkorpus | public domain / frei | ✅ | API + **BigQuery** |
| **Wikidata** 🔌 | 100M+ Entitäten | **CC0** | ✅ | SPARQL (in GENESIS verdrahtet) |

### Zugriffs-Infrastruktur
- **Google BigQuery Public Datasets** — Patente/AlphaFold/Genomik im Petabyte-Maßstab abfragen ohne Download.
- **AWS Open Data Registry** (1100+ Datensätze, >400 PB) — Bulk-Layer für ERA5/MP/ZINC/AlphaFold.
- **HuggingFace Datasets** 🔌 — OMat24, QM9, Open Catalyst (via `hf_hub_query` erreichbar).

**Top-Empfehlung (frei, sauber, leicht zu verdrahten):** OpenAlex (CC0) · PubChem · RCSB PDB (CC0) · AlphaFold-DB · UniProt · Materials Project · Wikidata 🔌 · ChEMBL 🔌. **Lizenz-Wachsamkeit:** Semantic-Scholar-NC-Records, PMC-NC-Subset, Materials-Project-GNoME (NC), ZINC (patent-geschützte Records).

---

## Teil C · Weitere Erfindungs-/Entwicklungs-Werkzeuge

| Stufe | Werkzeuge (Lizenz) | Komm. |
|---|---|---|
| **Optimierung** | **OR-Tools** (Apache, CP-SAT) · **pymoo** (Apache, Multi-Objektiv) · **Optuna** (MIT) · **BoTorch/Ax** (MIT) · CVXPY/SciPy/Pyomo (Apache/BSD) | ✅ |
| **Evolutionär** | DEAP (LGPL) · PyGAD (BSD) · gplearn (BSD) | ✅ |
| **AutoML / Surrogat / Active Learning** | SMT (BSD, Kriging) · AutoGluon (Apache) · FLAML (MIT) · modAL (MIT) | ✅ |
| **Generatives / inverses Design** | **NVIDIA Modulus/PhysicsNeMo** (Apache, PINNs/Operatoren) · DeepXDE (LGPL) · Topologie-Opt (ToPy GPL*) | ✅ |
| **Knowledge Graphs / Reasoning** | **PyKEEN** (MIT, KG-Embeddings) · txtai (Apache) · RDFLib (BSD) · Neo4j Community (GPL*, als DB-Server) | ✅ |
| **CAD / CAE / EDA** | **CadQuery · build123d** (Apache) · OCCT (LGPL) · FreeCAD (LGPL) · KiCad/Gmsh/OpenSCAD (GPL*, als Tool) | ✅ |
| **RL (Design-Agenten)** | Gymnasium · Stable-Baselines3 (MIT) · RLlib (Apache) · CleanRL (MIT) | ✅ |
| **Workflow / Provenance** | **AiiDA** (MIT) · MLflow (Apache) · DVC (Apache) · Snakemake (MIT) · Nextflow/Covalent/Parsl (Apache) | ✅ |

\* Copyleft: als isolierten Prozess/Service nutzen, nicht statisch einbetten.

**⭐ Standout — AiiDA (MIT):** provenance-getrackte automatisierte Simulations-Kampagnen — startet viele Rechnungen lokal/HPC und hält den **vollständigen Input→Output-Provenance-Graphen** querybar. Praktisch *gebaut* für GENESIS' „viele Sims fahren + alles im Ledger belegen". Starker Backbone-Kandidat für den Entdeckungs-Loop.

---

## Teil D · Lizenz-Disziplin (eine Regel)

**Permissiv (Apache/MIT/BSD, LGPL bei dynamischem Import)** = sauber einbettbar. **Copyleft (GPL/AGPL)** = nur als **separater Prozess/Service anrufen** (CLI/Socket), nicht statisch linken/mitvertreiben. GENESIS' `external_oracle()`-Muster (Aufruf als Prozess → gegateter Claim) erfüllt das ohnehin — also sind **auch GPL-Simulatoren als Orakel nutzbar**. Datensatz-Lizenz separat zur Code-Lizenz prüfen.

---

## Teil E · Was GENESIS heute schon erreicht vs. ergänzt

- **Schon via MCP/Connector erreichbar:** ChEMBL, PubMed, ClinicalTrials, bioRxiv, HuggingFace-Hub; plus GENESIS' eigene: Semantic Scholar, arXiv, Wikidata, CODATA, DLMF.
- **Leicht zu ergänzen (freie REST-APIs):** OpenAlex, PubChem, RCSB PDB, UniProt, Materials Project, OQMD/NOMAD (OPTIMADE), Google Patents (BigQuery).
- **Simulatoren zu verdrahten (P-Stufen):** zuerst die, die GENESIS' Domänen tragen — **MuJoCo/Drake/Kratos** (Mechatronik, ergänzt PyBullet), **OpenMM/xtb + ASE** (Molekül/Material), **Cantera** (Chemie), **ngspice** (Elektronik, ergänzt MNA-Sim).
- **Dev-Backbone:** **AiiDA** (Provenance) + **OR-Tools/pymoo/Optuna** (Optimierung) + **CadQuery/build123d** (CAD, schon teils in GENESIS).

---

*Belege: alle Links in den Recherche-Digests; Lizenzen primärquellen-geprüft. Dieser Katalog +
`MODELL_KATALOG_EXTERN` bilden den vollständigen externen Bau-Stack für die `INVENTOR_ARCHITEKTUR` (§10¾).*
