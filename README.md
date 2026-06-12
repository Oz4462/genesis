# GENESIS

*Generative Engine for Networked Ideation, Synthesis & Specification*

Ein Mensch liefert ein Problem oder eine Idee. GENESIS recherchiert, **verifiziert**, synthetisiert, detailliert und simuliert — und liefert eine umsetzbare Spezifikation. Domänenübergreifend. **Ohne Halluzination.**

> Open-Source-Infrastruktur, damit Menschen — privat wie Unternehmen — aus einer kleinen Idee etwas Vollständiges erschaffen können.

## Status

**Phase α + β + γ abgeschlossen und beweisbar korrekt; δ als vollständige deterministische Engineering-Validierungs-Engine ausgebaut; Quality-Engine (Eval, Refine-Loop, Klärung, Ratifikation, Kalibrierung, Telemetrie) verdrahtet — α/β auch live gegen echte Modelle bewiesen.**

Die vollständige α-Pipeline (Anti-Halluzination), der β-Lösungsraum und die γ-Spezifikation sind gebaut und getestet: Fakten-Ledger (Quellenzwang), Tool-Adapter (ehrliches Fetch), die Agenten (`scout`, `scholar`, `skeptic`, `conductor`, `synthesizer`, `architect`), Cross-Model-Verifikation, die Gates α, β und γ und die End-to-End-Verdrahtung mit CLI (`--mode report|solution|spec`).

**Phase δ (voll ausgebaut, `docs/phases/PHASE_DELTA.md` §1–§50):** eine deterministische, LLM-freie Physik-Validierungs-Engine — 3-D-FEM (lineare + quadratische Tets), Thermik (stationär + transient), Modalanalyse, Knicken, Ermüdung (inkl. Kerbe), Bruchmechanik, Torsion, Hertz-Kontakt, Druckbehälter, Kriechen, Plattenbiegung, Schraubenvorspannung, Thermospannung — **13 Validatoren** hinter einem ehrlichen **δ-Physik-Gate** (drei harte Fehlermodi, nie ein stiller Pass), mit **Auto-Select** aus measurand-getaggten Spec-Größen (einheiten-ehrlich, Lücken statt Drops). Jeder Validator ist gegen geschlossene Formen verifiziert (exakt wo beweisbar, sonst ehrliche Konvergenz/Schranke).

**Quality-Engine (verdrahtet, `--mode assess` + Footer im spec-Output):** Multi-Gate-Eval-Harness (Leaks = 0 als gemessene Metrik), geschlossener Verify→Refine-Loop (ehrliches stuck/exhaust, nie Fake-Erfolg), proaktive Klärung (EVPI-priorisierte Rückfragen), OTel-förmige Telemetrie, Human-in-the-Loop-Ratifikation (kein Auto-Approval), Confidence-Kalibrierung, Geometrie-Verifikation (gebauter BREP ≈ analytisch), Constraint-Widerspruchs-Detektor, Grounding-Integrität — komponiert zu **einem ehrlichen Gesamt-Verdikt** (`pipeline.assess_specification`), das eine Lücke nie als Pass maskiert.

**Neu (Phase γ):** Eine Idee wird zu einer **vollständigen, umsetzbaren Bauanleitung** — Größen mit deklarierter Herkunft, parametrische 3D-Geometrie (CSG), Stückliste, Schritte mit Prüfkriterien, numerisch geprüfte Constraints, Entscheidungsblatt. Die fünf γ-Halluzinationsklassen sind strukturell verhindert (PHASE_GAMMA.md §0): kein Wert ohne wörtlichen Beleg im VERIFIED-Claim, keine LLM-Arithmetik (Code rechnet, GATE γ rechnet unabhängig nach), keine Referenz ins Nichts, keine versteckte Entscheidung, kein Schritt ohne Check — und lieber ehrliche Abstention als eine teilweise/gedriftete Anleitung. Zusätzlich prüft GATE γ die **dimensionale Homogenität** jeder Rechnung (Einheiten als abelsche Gruppe, `verification/units.py`) — der Mars-Climate-Orbiter-Wächter: kg + mm oder eine als Länge deklarierte Fläche werden abgefangen. **Cross-Claim-Konsistenz (C-17):** zwei Größen mit demselben deklarierten `measurand` müssen übereinstimmen (gleiche Dimension, gleicher Wert nach Einheiten-Umrechnung) — ein deterministischer Wächter gegen Widerspruch zwischen zwei akzeptierten, belegten Fakten (z. B. „12 V" vs „24 V" für dieselbe Größe), ohne Sprachverständnis und ohne False Positive (eine Einheiten-Differenz wie 12 V vs 0,012 kV ist kein Konflikt). **Unsicherheits-Propagation (C-18):** ein DERIVED-Wert darf eine kombinierte Standardunsicherheit tragen, und GATE γ rechnet sie nach dem GUM-Fortpflanzungsgesetz (JCGM 100) unabhängig nach — „Code rechnet, Gate rechnet nach", jetzt auf die Unsicherheit angewandt. Im Capstone propagiert die deklarierte Last-Unsicherheit (12 ± 0,6 kg) bis zur Spitzenspannung (σ_peak = 22,1 ± 1,1 MPa, U₉₅ = ±2,2), und selbst der Worst-Case bleibt < 50 MPa.

**Phase δ (erste Schicht):** „validieren vor dem Bauen", aber nur was **deterministisch beweisbar** ist — keine erfundene Physik. GATE δ prüft die CSG-Geometrie über achsenparallele Bounding-Boxes: ein Loch, das das Teil verfehlt (`DEAD_OPERATION`), ein Schnitt nicht-berührender Teile (`EMPTY_INTERSECTION`), degenerierte Geometrie (`DEGENERATE_GEOMETRY`). Ehrliche Asymmetrie: ein **bestandenes** δ ist notwendig, nicht hinreichend (kein Festigkeits-/Herstellbarkeitsurteil); ein **gescheitertes** δ heißt „definitiv kaputt". Die Demo zeigt die Hüllbox + Status.

**Phase δ (zweite Schicht — deterministische Statik, ohne neuen Gate-Code):** Der Capstone beantwortet die erste echte Physik-Frage — *„hält der Halter die belegte Last?"* — komplett in der bestehenden γ-Maschinerie, mit **vier** belegten Checks: (1) Bemessungslast `F=(m·SF)·g` mit der schon deklarierten Sicherheit, (2) Kragträger-Biegespannung `σ_nom=6·F·L/(b·h²)`, (3) Kerb-Spitzenspannung `σ_peak=Kt·σ_nom` mit **Kt=3** (Kirsch-Lösung für die Kreisbohrung), (4) Schraubenschub `F/n ≤ αv·f_ub·A_s` (EN 1993-1-8). `g`, `Kt`, Festigkeit und Schraubendaten sind **GROUNDED** (Zahl wörtlich aus einem Claim), alles andere **DERIVED** (Code rechnet, GATE γ rechnet nach C-6, dimensional als Druck/Kraft verifiziert C-15), die Urteile sind numerische Constraints (C-13). **Der Check hat Zähne:** unter Bemessungslast + Kt=3 ergab der ursprüngliche 6-mm-Halter `σ_peak≈88 MPa > 50 MPa` (FAIL) → ehrliche Umkonstruktion auf 12 mm (`σ_peak≈22 MPa`, 56 % Reserve; Schraubenschub 36×). Die verbleibenden Residuen sind **präzise** als Gaps benannt und je an eine Entscheidung oder eine externe Größe gebunden — Wand-Auszug (substratabhängig), exaktes FEM-Feld (vs. konservativem Kt=3), Ermüdung/Dynamik (durch die statische Last-Entscheidung außerhalb), Druckprozess-Streuung (`docs/phases/PHASE_DELTA.md §9`).

**γ-Tiefe (Spezifikation bis zum letzten Detail):** claim-belegtes **Sourcing** (kein erfundener Shop/Preis), **Fastener→Loch** (ISO-273-Claim + Fit), **Komponenten-Kompatibilität** (Maß/Spannung/Strom-Constraints), getrennte **Elektronik-BOM** (V/A/W/Ω/Ah), **Montage-Detail** (Werkzeug/Drehmoment) + **Ort/Umgebung** (Platz-Fit in δ). Der **Capstone** (`python -m gen --mode capstone`) produziert eine komplette Spec (Mechanik + Elektronik + Beschaffung + Montage + Ort) durch **alle** Gates α/β/γ/δ — jeder faktische Wert belegt, kein erfundener Preis/Bauteil/Wert.

```
$ python -m pytest tests/ -q
794 passed
```

Alle Tests laufen **ohne einen einzigen LLM-Token und ohne Netzwerk**. Das heißt: Die Garantie „kein Fakt ohne Quelle, keine widerlegte Aussage als Tatsache, Lücken werden als Lücken markiert, im Zweifel Abstention" ist **bewiesen** — und von einem unabhängigen, adversarialen Audit bestätigt (Details: `docs/phases/PHASE_ALPHA_RESULT.md`).

```
$ python -m gen --demo                       # deterministischer α-Lauf, offline
$ python -m gen --demo --mode spec           # deterministische γ-Bauanleitung, offline
$ python -m gen --demo --mode spec --format scad  # CSG-Geometrie als OpenSCAD-Quelltext
$ python -m gen --demo --mode spec --format b123d # CSG-Geometrie als build123d-Python
$ python -m gen --demo --mode spec --format stl   # STL-Mesh (Primitive; Booleans -> scad/b123d)
$ python -m gen --mode capstone                   # komplette Spec durch alle Gates (Demo)
$ python -m gen --mode capstone --format md       # komplettes Markdown-Bauhandbuch
$ python -m gen --mode eval                        # Anti-Halluzinations-Garantie als Metrik (0 Leaks)
$ python -m gen --mode assess                      # ehrliches Quality-Verdikt (Klärung + δ-Physik + Constraints + Grounding)
$ python -m gen.web                                # lokale Web-UI auf http://127.0.0.1:8077 (Laien-Oberfläche)
$ python -m gen --mode protocol                    # Bio-Domäne: Pflanzen-Protokoll (γ + Reproduzierbarkeit)
$ python -m gen "Frage..."                   # Live-α: lokale Ollama-Modelle + Wikipedia
$ python -m gen --mode spec "Idee..."        # Live-γ: Idee -> belegte Spezifikation
```

**Live-Betrieb (neu):** Ein realer `OllamaLLM`-Adapter (Generator- und Verifier-Familie getrennt, vor jedem Aufruf erzwungen), ein keyloses `WikipediaBackend` als Discovery-Workhorse und der `PostgresLedgerStore` sind angebunden. Der Postgres-Ledger ist gegen eine echte PostgreSQL-Instanz verifiziert — alle drei Provenance-Schichten greifen, inklusive des DB-Triggers (`scripts/postgres_smoke.py`). Reale End-to-End-Läufe gegen lokale Ollama-Modelle (Generator ≠ Verifier-Familie) belegen beide Seiten der Garantie empirisch, ohne Cloud-Key (`scripts/live_smoke.py`):

- **Abstention statt Halluzination:** Sind Quellen nicht abrufbar oder ein Zitat nicht wörtlich belegbar, abstrahiert das System (Gate bestanden, null Claims). In einem Lauf fing der Wörtlich-Zitat-Guard live eine echte Modell-Paraphrase ab — manuell gegengeprüft, korrekt verworfen.
- **Autonomes VERIFIED:** Existiert echte, abrufbare Korroboration, erreicht GENESIS einen verifizierten Befund vollautomatisch — z. B. „Python is a programming language." mit `confidence 1.0`, gestützt durch zwei unabhängige Quellen, cross-model verifiziert, Gate bestanden.

Reales Testen mit kleinen lokalen Modellen deckte auch ehrliche Qualitätsgrenzen auf (Über-Fragmentierung, oberflächliches Verifier-Urteil) — root-cause-gefixt bzw. dokumentiert in `docs/BUILD_LOG.md` (LI-8). **Keine erfundene Tatsache gelangte je in einen Bericht.**

## Warum diese Reihenfolge

Wenn ein System halluziniert, ist jede weitere Fähigkeit (Ideenfindung, CAD, Simulation) wertlos — sie baut auf Erfundenem auf. Deshalb wird Anti-Halluzination **zuerst** und **isoliert** bewiesen. Erst dann kommen Ideation (Phase β), Spezifikation/CAD (γ), Simulation (δ), weitere Domänen (ε), Selbstlernen (ζ).

## Struktur

```
CLAUDE.md                       Operative Arbeitsregeln (Quelle der Wahrheit für Claude Code)
config.yaml                     Phase-α-Konfiguration (τ, Cross-Model-Familien, Backends)
docs/
  VISION.md                     Vision, Stand der Technik, ehrliche Risiken
  BUILD_LOG.md                  Beweiskette des Baus (Selbstkontrolle je Aufgabe)
  phases/PHASE_*.md             Spezifikation je Stufe (α, β, γ) + Akzeptanztests
  phases/PHASE_*_RESULT.md      Ehrliches Ergebnis je Kriterium + Audit
  agents/*.md                   Pro Agent: Verantwortung, I/O, Tools, Fehler, Tests
src/gen/
  core/interfaces.py            Framework-freie Protocols (Agent, Tool, LedgerStore, Gate, SearchBackend)
  core/state.py                 Datenmodell — inkl. Claim mit Quellenzwang-Invariante
  core/errors.py                Typisierte Fehler (lautes Scheitern statt stiller Defaults)
  ledger/store.py               InMemory-Ledger (Quellenzwang, Unabhängigkeitsregel)
  ledger/postgres.py            Postgres-Adapter (3. Schicht Quellenzwang, lazy asyncpg)
  tools/fetch.py                WebFetchTool — toter Fetch wird NIE zur Quelle
  tools/search.py               Semantic Scholar + generischer Web-Search-Adapter
  llm/base.py                   LLM-Boundary (mockbar) + deterministischer ScriptedLLM
  agents/scout.py               Breite — nur Quellen-Kandidaten
  agents/scholar.py             Tiefe — atomare Claims, jedes Zitat gegen die Quelle geprüft
  agents/skeptic.py             Verifikator — Cross-Model, neue unabhängige Quellen
  agents/conductor.py           Orchestrator — Report/Spec nur aus Ledger-Claims
  agents/synthesizer.py         Phase β — verankerte Lösungsansätze, erfindet nichts
  agents/architect.py           Phase γ — Spezifikation; Wertzwang, Code rechnet, Self-Gate
  verification/gates.py         GATEs α, β, γ — reine, getestete Verifikationslogik (+ Backstops)
  verification/derivation.py    Safe-Evaluator — DERIVED-Werte: Code rechnet, Gate rechnet nach
  verification/units.py         Dimensionsanalyse — Einheiten als abelsche Gruppe (C-15, Mars-Orbiter-Wächter)
  verification/geometry.py      AABB-Algebra + Volumen — Phase δ (sound; exakt-wo-beweisbar, sonst Schranke)
  verification/cross_model.py   Cross-Model-Pflicht + Confidence-Folding
  export/openscad.py            CSG-Geometrie -> OpenSCAD-Quelltext (deterministisch, traceable, zentriert)
  export/build123d.py           CSG-Geometrie -> build123d-Python (Algebra-Modus, OCCT)
  export/stl.py                 CSG-Primitive -> ASCII-STL-Mesh (Booleans ehrlich deferred)
  fem.py / fem3d.py / fem3d_quadratic.py / plate_hole.py / bracket_fem.py
                                δ-FEM: Balken, 3-D-Tets (linear+quadratisch), Loch-Kt, Halter
  structural.py / torsion.py / buckling.py / fatigue.py / notch_fatigue.py / fracture.py /
  contact.py / pressure_vessel.py / creep.py / plate_bending.py / bolted_joint.py /
  thermal.py / thermal_stress.py / modal.py
                                δ-Physik-Validatoren (Closed-Form, je gegen exakte Anker verifiziert)
  physics_validation.py         GATE δ-Physik — Registry (13 Validatoren), nie ein stiller Pass
  physics_selection.py          Auto-Select — measurand-getaggte Spec-Größen -> Checks + Lücken
  pipeline.py                   Ein ehrliches Gesamt-Verdikt (assess_specification)
  evaluation.py / refinement.py / clarification.py / ratification.py / calibration.py /
  telemetry.py / geometry_verification.py / constraint_consistency.py / grounding_integrity.py
                                Quality-Engine: Eval-Harness, Refine-Loop, Klärung, HITL-Sign-off,
                                Kalibrierung, OTel-Trace, Geometrie-/Constraint-/Grounding-Checks
  dfm.py / orientation.py / tolerance.py / uncertainty.py / montecarlo.py / circuit.py /
  brep.py / software.py / costing.py / completeness.py
                                δ/ε-Schichten: DFM, Toleranz, GUM/MC, SPICE-MNA, BREP, CODE-Gate
  config.py / runner.py / cli.py  Konfiguration, run(question)->Report, `python -m gen`
sql/001_ledger.sql              Fakten-Ledger; Quellenzwang als DB-Constraint
tests/                          794 Tests, inkl. Gate-Akzeptanz, δ-Physik-Engine (13 Validatoren + Gate + Auto-Select), Quality-Engine (Eval/Refine/Klärung/Ratifikation/Kalibrierung/Telemetrie/Pipeline) & 4 Frageklassen
```

## Die zentrale Idee in einer Datenstruktur

Alles dreht sich um den `Claim` (`src/gen/core/state.py`): eine einzelne, prüfbare Aussage, die **nicht ohne Quelle existieren kann** (erzwungen im Konstruktor, im Ledger UND als DB-Constraint — drei Schichten). Der `scholar` erzeugt einen Claim nur, wenn sein Stützzitat **wörtlich in der abgerufenen Quelle** steht. Der `skeptic` prüft jeden Claim mit **neuen, unabhängigen Quellen** und einem **anderen Modell** als der Erzeuger. Das `gate_alpha` lässt nur Berichte durch, in denen jede Tatsache so belegt ist — und prüft die Quellen-/Zuordnungs-Invarianten selbst nach, statt dem Assembler zu vertrauen.

## Nächster Schritt

Phase α + β + γ sind als Architektur vollständig bewiesen; α/β sind zusätzlich live (Ollama, Wikipedia, Postgres) verifiziert; δ liefert die erste deterministische Validierungs-Schicht (Geometrie). Die CAD-Export-Adapter (OpenSCAD + build123d) sind gebaut. Die ehrlichen nächsten Schritte: (1) der γ/δ-Live-Beweis — `--mode spec` gegen lokale Ollama-Modelle (die Garantien gelten unabhängig davon); (2) weitere δ-Schichten mit echten Modellen (Toleranz/Passung deterministisch, FEM/CFD hinter Adaptern), jede unter demselben Beweis-Standard; (3) externe Discovery-Quellen produktionsreif machen. Siehe `docs/phases/PHASE_DELTA_RESULT.md` und `PHASE_GAMMA_RESULT.md`.

## Lizenz

Ziel: Apache-2.0 (Open Source).
