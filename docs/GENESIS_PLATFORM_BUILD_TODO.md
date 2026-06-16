# GENESIS Plattform-Bauplan — TODO

**Stand:** 2026-06-15  
**Quelle:** `docs/GENESIS_PLATFORM_PLAN.md`  
**Ziel:** Aus der Vision eine konkrete Baufolge machen: was gebaut werden soll, was wir
dafür benötigen, wie wir es benötigen und wie wir es am besten angehen.

---

## 0 · Nicht verhandelbare Regeln

- Genesis ist keine SaaS-Chat-App.
- Kein Genesis-Kernmodul darf nur eine LLM-Abfrage sein.
- LLMs dürfen Kandidaten, Sprache, Varianten und Hypothesen liefern.
- Genesis-Core besteht aus typisierten Daten, lokaler Knowledge, Buildern, Runnern,
  deterministischen Gates, Evidence und menschlicher Ratifikation.
- Jede Fähigkeit wird erst behauptet, wenn sie ein Gate, Tests und ein Receipt hat.
- Kein „unmöglich" als Endurteil: Grenzen werden typisiert, kartiert und durch Stufen,
  Experimente und Technologieentwicklung verschoben.
- Patente, Simulationen und Datenquellen sind Beweismittel oder Innovationsradar, aber
  niemals automatisch Wahrheit.

---

## 1 · Zielarchitektur in einem Satz

```
Dream / Idee
  -> Moonshot- und Intent-Klärung
  -> Forschungsfront + Patent-/Prior-Art-Karte
  -> Entwicklungsfront + Capability Gaps
  -> Hypothesen + Experimente
  -> Prototyp / CAD / Teststand
  -> Simulation + Model Contract
  -> Messung + Lab Notebook
  -> Learning + Knowledge Base
  -> Proof Package + nächste Reifegrad-Stufe
```

---

## 2 · Bauwelle A: Architekturverträge zuerst

Diese Dokumente verhindern, dass Genesis später zu einem losen Prompt-System wird.

### A1 · Module Contract

**Datei:** `docs/architecture/MODULE_CONTRACT.md`

**Zu bauen:**

- Standardvertrag für jedes Genesis-Modul.
- Vorlage für Builder, Runner, Gate, Receipt und Evidence.
- Regel: Core-Modul ohne lokalen Tool-/Knowledge-/Runner-Anteil ist nur Kandidatengenerator.

**Benötigt:**

- bestehende Core-Patterns: `GateResult`, `GateFailure`, `RunState`
- Beispiele aus bestehenden Gates: alpha, gamma, delta, omega

**Definition of Done:**

- Dokument beschreibt Pflichtfelder:
  - `Input`
  - `Knowledge`
  - `Builder`
  - `Runner`
  - `Gate`
  - `Failure Modes`
  - `Evidence`
  - `Human Decision`
- mindestens 3 Beispielmodule beschrieben:
  - `technology_builder`
  - `experiment_designer`
  - `development_front_mapper`

### A2 · R&D System Contract

**Datei:** `docs/architecture/RD_SYSTEM.md`

**Zu bauen:**

- Forschungs- und Entwicklungs-Betriebssystem als Daten- und Modularchitektur.

**Benötigt:**

- Datenmodelle für:
  - `Hypothesis`
  - `ResearchQuestion`
  - `ExperimentPlan`
  - `MeasurementPlan`
  - `TestStandSpec`
  - `PrototypeSpec`
  - `MeasurementRun`
  - `LabNotebookEntry`
  - `LearningDelta`

**Definition of Done:**

- Kette beschrieben:

```text
Frage -> Stand der Technik -> Grenze -> Hypothese -> Experiment
-> Prototyp/Teststand -> Messung -> Auswertung -> Lernen -> nächste Stufe
```

- Gates für Hypothesen, Experimente, Messdaten und Learning-Updates definiert.

### A3 · Simulation Contract

**Datei:** `docs/architecture/SIMULATION_CONTRACT.md`

**Zu bauen:**

- Modell- und Simulationsvertrag auf Basis von V&V-Standards.

**Benötigt:**

- Standards/Leitlinien als Quellenfundament:
  - NASA-STD-7009B
  - NASA-HDBK-7009B
  - ASME V&V 10/20/40
  - AIAA/CFD-V&V
  - NIST/JCGM/GUM

**Definition of Done:**

- `ModelContract` definiert:
  - intended use
  - decision criticality
  - conceptual model
  - governing equations
  - assumptions
  - verification evidence
  - validation evidence
  - uncertainty budget
  - sensitivity report
  - applicability domain
  - known invalid cases
  - acceptance criteria
- `SimulationSpec` und `SimulationReceipt` skizziert.
- Gate-Regeln für Mesh, Konvergenz, Einheiten, Randbedingungen und Claim-Scope definiert.

### A4 · Source Connector Contract

**Datei:** `docs/architecture/SOURCE_CONNECTORS.md`

**Zu bauen:**

- Vertrag für Datenquellen, APIs, Kosten, Limits, Lizenz und Cache-Policy.

**Benötigt:**

- Connector-Schema:
  - `name`
  - `source_type`
  - `api_or_access`
  - `auth_required`
  - `cost_model`
  - `rate_limit`
  - `license_policy`
  - `ttl`
  - `store_fulltext`
  - `store_snippets`
  - `cache_policy`
  - `provenance_fields`

**Definition of Done:**

- klare Regel: Discovery ja, Vollspeicher nein.
- klare Regel: Evidence Extraction statt Datenhalde.
- klare Regel: Volltext nur speichern, wenn erlaubt/lizenziert.

---

## 3 · Bauwelle B: Daten, Knowledge Base, Patente

Ohne eigene Knowledge Base bleibt Genesis abhängig vom LLM. Aber wir speichern nicht die
Welt. Wir speichern Belege, strukturierte Fakten, Hashes, Receipts, Messungen und
Projektartefakte.

### B1 · Minimal Knowledge Store

**Zu bauen:**

- erster lokaler Store für strukturierte Genesis-Wissenseinträge.

**Benötigt:**

- Speicherform:
  - Start: SQLite oder JSONL + content-addressed files
  - später: Postgres optional
- Tabellen/Sammlungen:
  - `sources`
  - `claims`
  - `materials`
  - `components`
  - `formulas`
  - `process_rules`
  - `failure_modes`
  - `measurements`
  - `builds`
  - `patent_receipts`

**Definition of Done:**

- Eintrag kann Quelle, Hash, Datum, Lizenzstatus, Evidence und Gültigkeitsbereich speichern.
- Tests beweisen, dass ein Fakt ohne Quelle/Evidence nicht persistent wird.

### B2 · Content-addressed Cache

**Zu bauen:**

- begrenzter lokaler Cache für PDFs, Datenblätter, Patentdokumente, Meshes, CAD, Logs.

**Benötigt:**

- Hash-basierte Dateinamen
- TTL/LRU
- Projekt-Pinning
- Cache-Limit, z.B. konfigurierbar 5-20 GB
- Metadata sidecar

**Definition of Done:**

- Cache kann Datei speichern, Hash prüfen, pinnen, evicten.
- Gate verhindert, dass nicht erlaubte Volltexte dauerhaft gespeichert werden.

### B3 · SourceConnectorRegistry

**Zu bauen:**

- Registry, die alle Quellen mit Kosten, Limits, Lizenz und Speicherregeln beschreibt.

**Erste Connectoren:**

- Paper:
  - arXiv
  - Crossref
  - OpenAlex
  - PubMed/NCBI
  - NASA NTRS
- Patente:
  - WIPO PATENTSCOPE
  - EPO OPS
  - USPTO Open Data / Bulk Data
  - Espacenet
  - The Lens, falls Terms/API passend
  - Google Patents als Discovery-Hilfe, nicht blind automatisieren
- Datenblätter/Komponenten:
  - Herstellerseiten
  - Distributor-APIs, falls Zugang/Terms passen
  - lokale Uploads
- Normen:
  - freie Normen/NIST
  - ISO/IEC/ASTM/VDE/DIN nur Metadaten oder lizenziert

**Definition of Done:**

- Jeder Connector gibt ein `SourcePolicy`-Objekt zurück.
- Genesis kann vor Abruf prüfen: darf ich speichern, wie lange, mit welchen Limits?

### B4 · Evidence Extractor

**Zu bauen:**

- extrahiert kleine, relevante Belege aus Quellen statt Volltext zu speichern.

**Benötigt:**

- strukturierte Extracts:
  - Claim-Text
  - Wert
  - Einheit
  - Tabellen-/Abschnittsreferenz
  - kurzer zulässiger Belegauszug
  - Quelle/Hash/Abrufdatum
  - Unsicherheit/Gültigkeitsbereich

**Definition of Done:**

- Aus einem Datenblattwert wird ein strukturierter `EvidenceValue`.
- Gate blockiert Wert ohne Quelle, Einheit oder Gültigkeitsbereich, wenn nötig.

### B5 · Global Patent Intelligence Layer

**Zu bauen:**

- weltweites Patent- und Prior-Art-System als Innovationsradar.

**Benötigt:**

- Datenmodelle:
  - `PatentSearchQuery`
  - `PatentSourceReceipt`
  - `PatentFamilyMap`
  - `PatentClaimMap`
  - `PriorArtMap`
  - `TechnologyDisclosure`
  - `LegalStatusSnapshot`
  - `FreedomToOperateWarning`

**Wie angehen:**

1. Start mit Metadaten, nicht Volltext-Massenimport.
2. Query Expansion: Synonyme, IPC/CPC-Klassen, Sprachen.
3. WIPO/EPO/USPTO als erste harte Quellen.
4. Coverage Receipt für jede Recherche:
   - Quellen
   - Länder/Jurisdiktionen
   - Zeitraum
   - Sprachen
   - Query
   - Limits/Fehler
5. Patentfamilien clustern.
6. Technische Merkmale extrahieren.
7. Prior-Art-Karte erzeugen.

**Gates:**

- keine „neue Idee"-Behauptung ohne `PatentSourceReceipt`.
- keine globale Vollständigkeit ohne Coverage-Grenze.
- Patent ist Prior Art / technische Offenlegung, kein Funktionsbeweis.
- keine Freedom-to-Operate-Aussage ohne Jurisdiktion, Datum, Status und menschliche/rechtliche Prüfung.

---

## 4 · Bauwelle C: Moonshot und Grenzverschiebung

### C1 · Moonshot Pipeline

**Zu bauen:**

- Pipeline, die große Visionen ernst nimmt, aber nicht als riskantes Baupaket ausgibt.

**Datenmodelle:**

- `Dream`
- `MoonshotIntent`
- `DevelopmentFrontMap`
- `RiskBoundary`
- `MissingTechnology`
- `ExperimentLadder`

**Definition of Done:**

- Jetpack-Fall als Test:
  - Traumkern erkannt
  - heutige Grenzen kartiert
  - direkte riskante Umsetzung blockiert
  - sichere Stufen vorgeschlagen
  - fehlende Technologien benannt
  - erster messbarer Test definiert

### C2 · Development Front Mapper

**Zu bauen:**

- kartiert, was heute bekannt/gezeigt/offen ist.

**Benötigt:**

- Zugriff auf Knowledge Store
- SourceConnectorRegistry
- Patent/Paper/Prior-Art-Inputs
- Gate für Grenztypen

**Grenztypen:**

- `known_possible`
- `possible_but_unsafe_directly`
- `missing_measurement`
- `missing_model`
- `missing_component`
- `missing_tooling`
- `needs_breakthrough`
- `contradicts_current_model`

**Definition of Done:**

- Keine Grenze ohne Begründung und Quelle/Receipt.

### C3 · Capability Gap Analyzer

**Zu bauen:**

- trennt fehlendes Wissen, fehlende Messung, fehlendes Modell, fehlende Technologie,
  fehlendes Tooling und fehlende Finanzierung/Komponente.

**Output:**

- `CapabilityGap`
- Priorität
- nächste prüfbare Handlung

### C4 · Milestone Builder

**Zu bauen:**

- macht aus Vision und Gap eine Leiter.

**Gate:**

- kein Meilenstein ohne Erfolgskriterium.
- kein Meilenstein ohne Messgröße oder prüfbare Evidence.

### C5 · Technology Builder

**Zu bauen:**

- baut aus einer fehlenden Technologie einen ersten Prototyp-Plan.

**Output:**

- `TechnologyPrototypeSpec`
- Material-/Werkzeugbedarf
- CAD-/Fertigungsbedarf
- Teststandbedarf
- Sicherheitsgrenzen

### C6 · Boundary Reviser

**Zu bauen:**

- aktualisiert die Entwicklungsfront nach neuer Evidence.

**Gate:**

- keine Grenzverschiebung ohne Messung, Quelle, Simulation Receipt oder menschlich
  ratifizierte Evidence.

---

## 5 · Bauwelle D: R&D, Experimente, Teststände

### D1 · Hypothesis Builder

**Zu bauen:**

- generiert prüfbare Hypothesen aus Lücken, Träumen, Patentideen und Frontier Maps.

**Gate:**

- keine Hypothese ohne messbare Vorhersage.
- keine Hypothese ohne Falsifikationsmöglichkeit.

### D2 · Experiment Designer

**Zu bauen:**

- erzeugt ausführbare `ExperimentPlan`s.

**Pflichtfelder:**

- Hypothese
- kontrollierbare Variable
- Messgröße
- Sensorik
- Setup
- Kontrollbedingung
- Sicherheitsgrenze
- Abbruchkriterium
- Auswertung
- Unsicherheitsmodell

**Gate:**

- kein Experiment ohne Messgröße, Sicherheitsgrenze und Abbruchkriterium.

### D3 · Teststand Architect

**Zu bauen:**

- plant sichere Prüfstände statt gefährlicher Direktversuche.

**Beispiele:**

- Schubprüfstand für ducted fan
- Temperaturprüfstand für Kühlung
- Lastprüfstand für Struktur
- Batterietest mit Schutzschaltung

**Gate:**

- kein riskanter Direktversuch, wenn ein Prüfstand möglich ist.

### D4 · Bench Test Runner

**Zu bauen:**

- nimmt Messdaten oder simulierte Testläufe und bewertet sie deterministisch.

**Benötigt:**

- Datenimport
- Einheitenprüfung
- Unsicherheitsrechnung
- Vergleich gegen Erfolgskriterium
- Receipt

### D5 · Lab Notebook

**Zu bauen:**

- auditierbares Versuchsbuch.

**Speichert:**

- Artefakt-Version
- Setup
- Messgeräte
- Kalibrierung
- Umgebung
- Rohdaten
- Auswertung
- Entscheidungen
- Fehlerbilder

---

## 6 · Bauwelle E: Simulation und Industrie-Solver

### E1 · Solver Inventory

**Zu bauen:**

- Inventar lokaler und installierbarer Solver.

**Prüfen:**

- OpenFOAM
- SU2
- CalculiX
- Code_Aster
- Elmer
- Gmsh
- Salome
- ParaView
- KiCad/ngspice
- FreeCAD

**Erfassen:**

- Lizenz
- Installierbarkeit auf Windows
- CLI/API
- Input-/Output-Formate
- Referenzfälle
- Rechenkosten

### E2 · SimulationSpec / SimulationReceipt

**Zu bauen:**

- Datenmodelle für jede Simulation.

**Gate:**

- kein Solver-Ergebnis ohne Receipt.
- kein hübsches Bild als Beweis ohne Kennwert.
- keine Simulation ohne Modellgrenze.

### E3 · Reference Case Library

**Zu bauen:**

- kleine Benchmark-Sammlung.

**Startfälle:**

- Rohr-/Kanalströmung
- Strömung um Zylinder
- einfacher Wärmeleitfall
- Balkenbiegung
- Torsion
- einfache Schaltung

### E4 · Mesh + Convergence Gates

**Zu bauen:**

- Mesh-Qualitätsbericht
- Residuen-/Konvergenzbericht
- Mesh-Unabhängigkeitsvergleich

### E5 · First CFD/FEM Runner

**Vorgehen:**

1. zuerst einfachster Referenzfall
2. dann Runner
3. dann Gate
4. dann Verbindung zu Experiment Designer

**Nicht zuerst tun:**

- keine volle Jetpack-CFD
- keine komplexe Turbine
- keine Show-Visualisierung ohne Receipt

---

## 7 · Bauwelle F: CAD, Fertigung, PRINTFORGE

### F1 · PRINTFORGE Inventory

**Zu bauen:**

- `docs/integration/PRINTFORGE_INVENTORY.md`

**Suchen:**

- Projektpfade auf dem PC
- Sprache
- Fähigkeiten
- Tests
- Inputs/Outputs
- CAD/Slicer/Printability/Fertigung?
- Lizenz/Abhängigkeiten

**Entscheidung:**

- integrieren
- adaptieren
- Ideen übernehmen
- verwerfen und selbst bauen

### F2 · CAD Capability Audit

**Zu bauen:**

- `docs/integration/CAD_CAPABILITY_AUDIT.md`

**Prüfen:**

- OpenSCAD
- build123d
- OCP/OpenCASCADE
- STL
- Geometrie-Verifikation
- Orientation/Printability
- Mesh Integrity
- STEP
- FreeCAD
- KiCad

### F3 · Prototype CAD Builder

**Zu bauen:**

- aus `PrototypeSpec` oder `TechnologyPrototypeSpec` parametrisches CAD erzeugen.

**Gate:**

- keine Geometrie ohne Maß-/Einheiten-/Volume-/AABB-Prüfung.

### F4 · Manufacturing Runner

**Zu bauen:**

- DFM/Printability/CNC/PCB-Rules als Runner.

**Start:**

- FDM
- STL Integrity
- Wandstärke
- Brücken
- Überhänge
- erste Lage
- Toleranzen

---

## 8 · Bauwelle G: Nutzer, Lernen, Proof Packages

### G1 · Technology Readiness Ladder

**Zu bauen:**

- Reifegradmodell:

```text
Idee -> Konzept -> Modell -> Simulation -> Prüfstand
-> Prototyp -> Feldtest -> Produkt -> zertifizierbar
```

**Gate:**

- keine höhere Stufe ohne Evidence.

### G2 · Resource Planner

**Zu bauen:**

- nächster Schritt mit Kosten, Werkzeugen, Material, Zeit und Sicherheitsbedarf.

**Output:**

- billigste sichere Version
- Maker-Version
- professionelle Version

### G3 · Safety and Hazard Mode

**Zu bauen:**

- Risikoklassen und Sicherheitsleiter.

**Gate:**

- kein direkter Sprung zu menschentragenden oder Hochenergie-Tests.

### G4 · Teacher Mode

**Zu bauen:**

- jede Build-/Experiment-/Simulation-Stufe bekommt Lernnotizen.

**Gate:**

- kein Schritt ohne Erkenntnisgewinn.

### G5 · Community Evidence

**Zu bauen:**

- Nutzer-/Community-Messungen mit Trust.

**Artefakte:**

- `CommunityBuildReport`
- `ReplicationResult`
- `FieldFailureReport`
- `CommunityEvidenceScore`

### G6 · Proof Package Generator

**Zu bauen:**

- kompletter Projektabschluss als beweisbares Archiv.

**Enthält:**

- Quellen
- Claims
- Entscheidungen
- offene Lücken
- CAD
- BOM
- Simulation Receipts
- Model Contracts
- Experimente
- Messdaten
- Lab Notebook
- Risiken
- Fertigungsdateien
- Montageplan
- Testplan
- nächste Stufe

---

## 9 · Empfohlene Reihenfolge

### Phase 1: Verträge und Inventare

- [ ] `docs/architecture/MODULE_CONTRACT.md`
- [ ] `docs/architecture/SOURCE_CONNECTORS.md`
- [ ] `docs/architecture/RD_SYSTEM.md`
- [ ] `docs/architecture/SIMULATION_CONTRACT.md`
- [ ] `docs/integration/PRINTFORGE_INVENTORY.md`
- [ ] `docs/integration/CAD_CAPABILITY_AUDIT.md`
- [ ] Solver Inventory
- [ ] Patent Source Inventory

### Phase 2: Datenkern

- [ ] Minimal Knowledge Store
- [ ] Content-addressed Cache
- [ ] SourceConnectorRegistry
- [ ] Evidence Extractor
- [ ] erstes Paper-Connector-Paar
- [ ] erster Patent-Connector oder Patent-Metadata-Importer

### Phase 3: Grenzverschiebung

- [ ] `Dream` / `MoonshotIntent`
- [ ] `DevelopmentFrontMap`
- [ ] `CapabilityGap`
- [ ] `MilestoneLadder`
- [ ] `ExperimentLadder`
- [ ] Jetpack-Testfall als nicht-riskanter Pipeline-Test

### Phase 4: R&D

- [ ] Hypothesis Builder
- [ ] Experiment Designer
- [ ] Measurement Plan Builder
- [ ] Teststand Architect
- [ ] Lab Notebook
- [ ] Bench Test Runner

### Phase 5: Simulation

- [ ] `ModelContract`
- [ ] `SimulationSpec`
- [ ] `SimulationReceipt`
- [ ] Reference Case Library
- [ ] Mesh Gate
- [ ] Convergence Gate
- [ ] erster FEM/CFD Runner mit bekanntem Referenzfall

### Phase 6: CAD/Fertigung

- [ ] Prototype CAD Builder
- [ ] Manufacturing Runner
- [ ] PRINTFORGE Adapter, falls sinnvoll
- [ ] FreeCAD Adapter
- [ ] KiCad Adapter
- [ ] STEP/Assembly/Drawings Roadmap

### Phase 7: Plattform-Output

- [ ] Readiness Ladder
- [ ] Resource Planner
- [ ] Safety/Hazard Mode
- [ ] Teacher Mode
- [ ] Community Evidence Store
- [ ] Proof Package Generator
- [ ] erster vollständiger Plattform-Demo-Pfad

---

## 10 · Erste konkrete Umsetzung

Wenn wir mit Code starten, nicht mit allem gleichzeitig.

Empfohlener erster harter Stein:

1. `docs/architecture/MODULE_CONTRACT.md`
2. danach `SourceConnectorRegistry` als Datenmodell + Tests
3. danach `MinimalKnowledgeStore`
4. danach `DevelopmentFrontMap` + Jetpack-Testfall

Warum diese Reihenfolge:

- Der Modulvertrag verhindert LLM-only-Drift.
- SourceConnectorRegistry verhindert Datenchaos und Kosten-/Lizenzblindheit.
- Knowledge Store gibt Genesis ein eigenes Gedächtnis.
- DevelopmentFrontMap macht aus Vision eine verschiebbare Grenze.

Erst danach sollten wir große Solver, PRINTFORGE oder globale Patentabfragen tief
integrieren.

---

## 11 · Done-Kriterium für diesen Bauplan

Dieser Plan ist erfüllt, wenn Genesis für eine große Idee folgendes erzeugt:

```text
Dream
  -> Patent/Paper/Prior-Art-Frontier
  -> DevelopmentFrontMap
  -> CapabilityGaps
  -> MilestoneLadder
  -> ExperimentPlan
  -> PrototypeSpec
  -> SimulationSpec + Receipt
  -> TestStandSpec
  -> MeasurementRun
  -> LearningDelta
  -> ProofPackage
```

Und jedes Artefakt hat:

- Typ
- Quelle/Evidence
- Gate
- Failure Modes
- offene Lücken
- nächste Stufe
