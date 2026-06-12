# GENESIS

*Generative Engine for Networked Ideation, Synthesis & Specification*

**Ein Mensch liefert eine Idee. GENESIS recherchiert, verifiziert, berechnet und liefert eine umsetzbare, belegte Spezifikation — ohne Halluzination.**

> Open-Source-Infrastruktur, damit Menschen — privat wie Unternehmen — aus einer kleinen Idee etwas Vollständiges erschaffen können: mit Quellen statt Behauptungen, mit nachgerechneter Physik statt geratener Zahlen, und mit ehrlichen Lücken statt erfundener Antworten.

```
794 Tests offline bewiesen · deterministisch · läuft komplett lokal · kein Cloud-Zwang
```

---

## Inhalt

1. [Das Problem & die Antwort](#1--das-problem--die-antwort)
2. [Die Garantie](#2--die-garantie)
3. [Architektur: die Phasen α → β → γ → δ](#3--architektur-die-phasen-α--β--γ--δ)
4. [Die Gates](#4--die-gates)
5. [Die Physik-Engine (Phase δ)](#5--die-physik-engine-phase-δ)
6. [Die Quality-Engine](#6--die-quality-engine)
7. [Installation](#7--installation)
8. [Nutzung: CLI](#8--nutzung-cli)
9. [Nutzung: Web-UI](#9--nutzung-web-ui)
10. [Nutzung: Python-API](#10--nutzung-python-api)
11. [Live-Modus (lokale LLMs)](#11--live-modus-lokale-llms)
12. [Messung & Gold-Set](#12--messung--gold-set)
13. [Verifikations-Philosophie](#13--verifikations-philosophie)
14. [Projektstruktur](#14--projektstruktur)
15. [Status & ehrliche Grenzen](#15--status--ehrliche-grenzen)
16. [Dokumentation](#16--dokumentation)

---

## 1 · Das Problem & die Antwort

Sprachmodelle erfinden. Sie liefern überzeugende Preise, die kein Shop führt, Normen, die nicht existieren, und Festigkeitswerte, die niemand gemessen hat. Für Recherche ist das ärgerlich — für eine **Bauanleitung**, die jemand wirklich umsetzt, ist es gefährlich.

GENESIS dreht das Verhältnis um: **das Modell darf nur Struktur vorschlagen — niemals Fakten erschaffen.** Jeder faktische Wert muss wörtlich in einer verifizierten, unabhängig korroborierten Quelle stehen. Jede Rechnung führt Code aus, und ein unabhängiges Gate rechnet sie nach. Jede Designentscheidung ist als Entscheidung deklariert und vom Menschen ratifizierbar. Und wo nichts belegbar ist, sagt GENESIS das — **„Ich weiß es nicht" ist ein gültiger, erwünschter Output.**

Das ist keine Prompt-Bitte, sondern Struktur: ein `Claim` ohne Quelle kann im Datenmodell **nicht existieren** (erzwungen im Konstruktor, im Ledger und als Datenbank-Trigger — drei Schichten).

## 2 · Die Garantie

| Prinzip | Bedeutung | Durchsetzung |
|---|---|---|
| **Kein Fakt ohne Quelle** | Jede Behauptung lebt im Fakten-Ledger mit Quelle, Konfidenz, Status | Konstruktor + Ledger + DB-Trigger |
| **Wertzwang im Wortlaut** | Eine Zahl in der Spezifikation steht *wörtlich* in einem verifizierten Beleg | GATE γ C-4 |
| **Code rechnet, Gate rechnet nach** | Das LLM macht nie Mathematik; abgeleitete Werte berechnet Code, das Gate rechnet sie unabhängig nach | GATE γ C-6 |
| **Dimensionale Homogenität** | kg + mm oder eine als Länge deklarierte Fläche werden abgefangen (Einheiten als abelsche Gruppe) | GATE γ C-15 |
| **Cross-Claim-Konsistenz** | Zwei Größen mit demselben deklarierten `measurand` dürfen sich nicht widersprechen | GATE γ C-17 |
| **Unsicherheits-Propagation** | Messunsicherheiten propagieren nach GUM (JCGM 100) — und das Gate rechnet auch das nach | GATE γ C-18 |
| **Keine versteckte Entscheidung** | Jede Wahl trägt eine Begründung und erscheint auf dem ratifizierbaren Entscheidungsblatt | Konstruktor + GATE γ |
| **Cross-Model-Verifikation** | Der Verifizierer (skeptic) ist ein *anderes* Modell als der Generator; Selbst-Bestätigung zählt nicht | erzwungen vor jedem Call |
| **Ehrliche Abstention** | Was nicht belegbar ist, wird Lücke — nie ein teilweiser oder gedrifteter Plan | alle Gates + Agenten |
| **Determinismus** | Jeder Lauf hat eine `run_id`, ist gecheckpointet und exakt reproduzierbar | Runner + Config-Hash |

## 3 · Architektur: die Phasen α → β → γ → δ

```
Idee/Frage
   │
   ▼
 α  RECHERCHE      scout → scholar → skeptic → conductor
   │               Quellen finden → atomare Claims (Zitat wörtlich geprüft)
   │               → cross-model verifizieren → Report (jeder Satz ↦ Claim)
   ▼
 β  LÖSUNGSRAUM    synthesizer: real existierende Ansätze, jeder in
   │               verifizierten Claims verankert — nichts erfunden
   ▼
 γ  SPEZIFIKATION  architect: Größen (mit deklarierter Herkunft), parametrische
   │               3D-Geometrie (CSG), Stückliste, Schritte mit Prüfkriterium,
   │               numerisch geprüfte Constraints, Entscheidungsblatt
   ▼
 δ  VALIDIERUNG    deterministische, LLM-freie Physik- und Geometrie-Prüfung
   │               (Engine: siehe unten) + Quality-Verdikt + Ratifikation
   ▼
 belegte, geprüfte, ratifizierbare Spezifikation  (+ CAD-Export: OpenSCAD,
 build123d, STL — und ein vollständiges Markdown-Bauhandbuch)
```

Jeder Agent erfüllt ein framework-freies Protocol (`core/interfaces.py`); Framework-Spezifisches lebt hinter Adaptern. Der Zustand ist typisiert (`core/state.py`), der Ledger erzwingt Provenance, Checkpoints machen Läufe reproduzierbar.

## 4 · Die Gates

Eine Phase endet erst, wenn ihr Gate besteht. Gates sind **reine, deterministische Funktionen** — kein Modell-Urteil:

| Gate | Prüft | Beispiele harter Fehler |
|---|---|---|
| **α** | Report-Soundness | unbelegter Satz, widerlegter Claim als Fakt, tote Zitation |
| **β** | Lösungsraum | unverankerter Ansatz |
| **γ** (C-1…C-18) | Spezifikation | Wert nicht im Beleg-Wortlaut, gebrochene Ableitung, Dimensionsfehler, Cross-Claim-Widerspruch, falsche Unsicherheit |
| **δ** | Geometrie | tote Bool-Operation, leerer Schnitt, degenerierte Geometrie (AABB — beweisbar, keine False Positives) |
| **δ-Physik** | Engineering | `PHYSICS_CHECK_FAILED` (Marge nicht erfüllt), `PHYSICS_CHECK_ERROR` (unrechenbare Eingabe), `PHYSICS_UNKNOWN_VALIDATOR` — **nie ein stiller Pass** |
| **ERC** | Elektrik | schwebende Netze, zwei Treiber auf einem Netz, ungetriebene Last |
| **CODE** | Software | das Deliverable wird in einem isolierten Subprozess **ausgeführt**; rote Checks = FAIL |
| **PROTOCOL** | Bio/Labor | Messung ohne Kontrollgruppe oder mit zu wenigen Replikaten |

## 5 · Die Physik-Engine (Phase δ)

Eine deterministische, LLM-freie Engineering-Validierungs-Engine (`docs/phases/PHASE_DELTA.md`, §1–§51). **Jeder Validator ist gegen geschlossene Formen verifiziert** — exakt, wo es beweisbar ist (Maschinengenauigkeit), sonst als ehrliche Konvergenz oder konservative Schranke mit deklarierter Grenze.

**13 Validatoren hinter dem δ-Physik-Gate:**

| Versagensmodus | Validator | Verifiziert gegen |
|---|---|---|
| Torsion (Welle) | `torsion` | τ=16T/πd³ ≡ T·r/J (Identität, exakt) |
| Knicken (Stabilität) | `buckling` | Euler π²EI/(KL)², 4 Lagerungen < 0,1 % |
| Ermüdung (zyklisch) | `fatigue` | Goodman/Soderberg/Gerber-Endpunkte, Basquin, Miner |
| Kerb-Ermüdung | `notch_fatigue` | Peterson q=1/(1+a/r), K_f-Grenzfälle |
| Bruchmechanik | `fracture` | Irwin K=Yσ√(πa), Paris-Integral vs. Numerik 3·10⁻¹¹ |
| Hertz-Kontakt | `contact` | p₀=1,5·p_mean exakt, Grenzfall Kugel-auf-Ebene |
| Druckbehälter | `pressure_vessel` | dünnwandig + Lamé (Randbedingungen exakt) |
| Kriechen (heiß) | `creep` | Larson-Miller-Inverse exakt, Norton (σ₂/σ₁)ⁿ |
| Übertemperatur | `overtemperature` | Fourier Q=kAΔT/L maschinengenau |
| Thermospannung | `thermal_mismatch` | −EαΔT exakt, Timoshenko-Bimetall |
| Resonanz | `resonance` | Eigenfrequenz-Abstand (Modalanalyse-gestützt) |
| Plattenbiegung | `plate_bending` | Kirchhoff-Kreisplatte (Timoshenko/Roark) |
| Schraubenvorspannung | `bolted_joint` | Shigley/VDI 2230, Separationslast exakt |

**Dahinter rechnet echte FEM** (reines numpy, optional gmsh/cadquery): 3-D-Kontinuum mit linearen **und quadratischen** Tetraedern (T10 trifft die Biegefrequenz auf 0,2 %), berechnete Loch-Spannungskonzentration (trifft Howlands Kt≈3,14), Thermik stationär **und transient**, Modalanalyse (exakt 6 Starrkörpermoden), Monte-Carlo-Unsicherheit (JCGM 101), SPICE-artige Schaltungsanalyse (DC/AC/nichtlinear/transient), exakte BREP-Geometrie (OpenCASCADE) und orientierungsabhängiges FDM-DFM.

**Auto-Select:** Die Spezifikation wählt ihre Checks selbst. Größen tragen deklarierte `measurand`-Tags (`shaft.torque`, `material.shear_strength`, …); ein Rezept-Katalog löst daraus die passenden Checks auf — **einheiten-korrekt konvertiert** (150 N·m → 150000 N·mm), und eine indizierte-aber-unrechenbare Prüfung wird **Lücke**, nie still verworfen und nie mit falscher Einheit gefüttert.

## 6 · Die Quality-Engine

Um die Gates herum sitzt eine verdrahtete Produktions-Schicht — komponiert zu **einem ehrlichen Gesamt-Verdikt** (`pipeline.assess_specification`), das eine Lücke nie als Pass maskiert:

| Baustein | Was es tut |
|---|---|
| **Eval-Harness** (`evaluation.py`) | Die Garantie als gemessene Zahl: kuratierte solide + manipulierte Fälle über **beide** Gates; die nicht verhandelbare Metrik ist **Leaks = 0** |
| **Verify→Refine-Loop** (`refinement.py`) | Gate-Fehler → gezielte Korrektur-Direktiven → begrenzte Re-Generierung (max. 5 Runden); meldet ehrlich `stuck`/`exhausted` — **nie Fake-Erfolg** |
| **Proaktive Klärung** (`clarification.py`) | Erkennt Unterspezifikation und stellt die wertvollsten Rückfragen zuerst (EVPI-priorisiert); Antworten werden deklarierte Entscheidungen; fragt nie nach nicht vorhandener Physik |
| **Ratifikation** (`ratification.py`) | Die KI schlägt vor, der Mensch entscheidet: jede Entscheidung, jede Lücke und jedes gescheiterte Gate blockiert „fertig", bis sie explizit abgezeichnet ist — **kein Auto-Approval** |
| **Kalibrierung** (`calibration.py`) | Akzeptanz-Schwellen per Messung (Precision@Threshold), ECE, Konsistenz-Konfidenz — und ehrliches `None`, wenn die Daten die Schwelle nicht hergeben |
| **Telemetrie** (`telemetry.py`) | OTel-förmiger Prozess-Trace (Gates, Verdikte, Runden, Zeiten) — auditierbar, deterministisch testbar |
| **Geometrie-Verifikation** (`geometry_verification.py`) | Der gebaute CAD-Körper wird gegen die analytisch implizierte Geometrie kreuzgeprüft (Volumen + Maße exakt) |
| **Constraint-Konsistenz** (`constraint_consistency.py`) | Findet strukturell widersprüchliche Anforderungen (a≥b ∧ a<b) **wertunabhängig**, ohne Solver |
| **Grounding-Integrität** (`grounding_integrity.py`) | Verifikations-Quellen müssen von Original-Quellen **disjunkt** sein (keine zirkuläre Selbst-Bestätigung); jeder Report-Satz ↦ realer, nicht-widerlegter Claim |

Das Gesamt-Verdikt unterscheidet ehrlich: `physics_verified` · `needs_clarification` · `physics_incomplete` (Lücke ≠ Pass) · `physics_failed` · `no_physics_indicated` (nichts geprüft ≠ Freifahrtschein) · `inconsistent_constraints`.

## 7 · Installation

Voraussetzung: **Python ≥ 3.11**. Alles läuft lokal; nichts verlässt deinen Rechner.

```bash
git clone <repo> && cd genesis
pip install -e .            # Kern (numpy) + Kommandos `genesis` und `genesis-web`
pip install -e .[web]       # + lokale Web-UI (FastAPI/uvicorn)
pip install -e .[cad]       # + exakter CAD-Kernel (cadquery/OCP) und FEM-Mesher (gmsh)
pip install -e .[postgres]  # + persistenter Fakten-Ledger (asyncpg; In-Memory ist Default)
pip install -e .[full]      # alles inkl. Dev-Tools (pytest, ruff, httpx)
```

Ohne die optionalen Pakete bleibt alles funktionsfähig — die betreffenden Features/Tests **skippen ehrlich**, statt zu raten.

```bash
python -m pytest tests/ -q          # 794 passed (volle Deps) — ohne LLM-Token, ohne Netz
```

## 8 · Nutzung: CLI

Alle folgenden Modi sind **deterministisch und offline** (kein Internet, kein LLM):

```bash
genesis --mode capstone               # komplette Spezifikation durch ALLE Gates (LED-Regalhalter)
genesis --mode capstone --format md   #   … als vollständiges Markdown-Bauhandbuch
genesis --demo                        # α-Demo: verifizierter Fakten-Report
genesis --demo --mode spec            # γ-Demo: Bauanleitung + Quality-Verdikt-Footer
genesis --demo --mode spec --format scad    # Geometrie als OpenSCAD-Quelltext
genesis --demo --mode spec --format b123d   # … als build123d-Python
genesis --demo --mode spec --format stl     # … als STL-Mesh
genesis --mode assess                 # das ehrliche Quality-Verdikt über die Demo-Specs
genesis --mode eval                   # die Anti-Halluzinations-Garantie als Metrik (Leaks = 0)
genesis --mode protocol               # Bio-Domäne: reproduzierbares Pflanzen-Protokoll
genesis-web                           # lokale Web-UI auf http://127.0.0.1:8077
```

(Vor `pip install -e .` geht alles auch direkt aus dem Repo: `PYTHONPATH=src python -m gen …` bzw. `python -m gen.web`.)

Live-Modi (lokales Ollama nötig, siehe [§11](#11--live-modus-lokale-llms)):

```bash
genesis "Wie funktioniert ein Wälzlager?"          # Live-α: Frage → belegter Report
genesis --mode solution "Drehmoment begrenzen"     # Live-β: Problem → verankerter Lösungsraum
genesis --mode spec "Wandhalter für 5-kg-Kamera"   # Live-γ: Idee → belegte Spezifikation
```

## 9 · Nutzung: Web-UI

```bash
genesis-web        # → http://127.0.0.1:8077  (bindet nur an localhost)
```

Die Oberfläche ist für **Laien** gebaut und macht die Ehrlichkeit sichtbar statt sie zu glätten:

| Tab | Inhalt |
|---|---|
| **Übersicht** | Was GENESIS garantiert, Farb-Legende, Live-Status |
| **α · Fakten-Report** | Jeder Satz klickbar → Beleg-Zitat + Quellen-Links |
| **γ · Bauanleitung** | Größen mit Herkunfts-Badges (belegt · berechnet · Entscheidung), Stückliste, Schritte mit Prüfkriterium, Lücken prominent in Gelb |
| **Capstone** | Die komplette Spezifikation mit allen Gate-Badges |
| **Physik-Verdikt** | Auto-gewählte Checks mit gerechneten Sicherheitsfaktoren; „keine Physik deklariert" erscheint grau als *nichts geprüft* — nie als Pass |
| **Klärungs-Dialog** | GENESIS fragt, du antwortest, das Verdikt wird neu berechnet — der Gelb→Grün-Flow live |
| **Garantie-Metrik** | Das Eval-Harness mit **Leaks = 0** als Haupt-KPI |
| **Sign-off** | Ratifikation als Checkliste: nichts gilt ohne deine expliziten Häkchen |
| **Eigene Frage** | Der Live-Pfad — solange das Owner-Gate zu ist, antwortet GENESIS mit einer ehrlichen Ablehnung statt einer erfundenen Antwort |

Farbcode: **grün** = unabhängig verifiziert / Marge erfüllt · **gelb** = ehrliche Lücke / offene Entscheidung · **rot** = Prüfung gescheitert · **grau** = nicht geprüft.

## 10 · Nutzung: Python-API

```python
import gen

# Live-Pipelines (Ollama nötig): α / β / γ
report = await gen.run("Frage …", deps, config=cfg)
spec   = await gen.run_specification("Idee …", deps, config=cfg)

# Quality-Verdikt über eine Spezifikation (offline, deterministisch)
from gen.demo import drive_shaft_spec
verdikt = gen.assess_specification(drive_shaft_spec())
print(verdikt.overall)                  # "physics_verified"

# Die Physik-Validatoren auch direkt als verifizierte Rechenbibliothek:
from gen.torsion import shaft_torsion_check
shaft_torsion_check(torque=150000, diameter=25, length=600,
                    shear_modulus_g=80000, shear_strength=260)
# -> {"max_shear": 48.9, "safety_factor": 5.32, "ok": True, ...}

from gen.buckling import buckling_check
from gen.fatigue import goodman_check
from gen.pressure_vessel import pressure_vessel_check
# ... alle 13, jede gegen geschlossene Formen getestet
```

`import gen` lädt bewusst **kein** numpy (PEP-562-Lazy-Export) — wer nur die α/β/γ-Pipelines nutzt, bleibt dependency-leicht.

## 11 · Live-Modus (lokale LLMs)

Der Live-Pfad nutzt **lokales Ollama** (kein Cloud-Key) und ein keyloses Wikipedia-Backend:

```bash
ollama pull qwen2.5:14b     # Generator (scout/scholar)
ollama pull gemma4          # Verifizierer (skeptic) — MUSS eine andere Modellfamilie sein
```

Gleiche Modellfamilie für Generator und Verifizierer? GENESIS **bricht ab, bevor irgendein Call passiert** — Cross-Model ist Pflicht, nicht Vorschlag. Mit `--checkpoint-dir runs` entsteht pro Lauf ein reproduzierbarer Audit-Checkpoint.

In der Web-UI ist der Live-Pfad zusätzlich **hart gegated**: erst `GENESIS_ALLOW_LIVE=1` öffnet ihn — bis dahin liefert „Eigene Frage" eine ehrliche Ablehnung mit Begründung, niemals eine erfundene Offline-Antwort.

**Status:** α/β sind live gegen echte Modelle bewiesen (inkl. eines Laufs, in dem der Wortlaut-Wächter eine echte Modell-Paraphrase abfing). Der erste gemessene Live-γ-Lauf ist bewusst aufgeschoben, bis die Messlatte definiert ist — siehe nächster Abschnitt.

## 12 · Messung & Gold-Set

„Produktionsreif" ist bei GENESIS **eine Messung, keine Behauptung.** Dafür existieren zwei Ebenen:

**Offline (läuft heute):** `genesis --mode eval` misst die deterministische Diskriminierung beider Gates über kuratierte solide + manipulierte Spezifikationen. Ergebnis: 10/10 korrekt, **Leaks = 0** (kein Halluzinations-Typ rutscht durch), 0 Fehlalarme.

**Live (vorbereitet, owner-gated):** `goldset/v1.json` — 24 kuratierte Fälle in drei Klassen:
- **Fakten** (10): bekannt belegbare Antworten; die erwarteten Tokens müssen erscheinen,
- **Fallen** (7): plausibel klingend, aber nicht verlässlich belegbar — Abstention oder belegte Antwort ist korrekt, eine selbstbewusste unbelegte Zahl ist die Halluzination,
- **Nonsense** (7): nicht existente Entitäten (erfundenes Polymer, erfundene Norm, erfundenes Theorem) — **die einzig richtige Antwort ist Enthaltung.**

Der Scorer (`gen/goldset.py`) berechnet Fakten-Genauigkeit, **Abstention-Recall** und Fallen-Resistenz, führt eine `hallucinations`-Liste, deren Leerheit die nicht verhandelbare Messlatte ist — und **verweigert** die Bewertung unvollständiger Läufe.

## 13 · Verifikations-Philosophie

- **Exakt, wo beweisbar:** uniforme Spannung, Fourier-Leitung, Starrkörpermoden, Lamé-Randbedingungen, Volumen — auf Maschinengenauigkeit gepinnt. Sonst: ehrliche Konvergenz (mit gemessener Rate) oder konservative Schranke, immer mit deklarierter Grenze.
- **Zwei unabhängige Methoden:** FEM gegen geschlossene Form, BREP gegen analytisches Volumen, MNA gegen Ohm — Übereinstimmung als Schutz gegen Fehler in einer von beiden.
- **Tests mit Zähnen:** Jeder Wächter hat Negativtests (der manipulierte Fall **muss** scheitern). Das Eval-Harness aggregiert das zu Leaks = 0.
- **Real-World-Verifikation:** Die Web-UI wurde nicht nur unit-getestet, sondern im echten Browser bedient (Playwright): Klärungs-Dialog Gelb→Grün, Sign-off-Verweigerung, Live-Ablehnungskarte.
- **794 Tests** (volle Abhängigkeiten) / 767 + 9 skipped (Minimal-Umgebung) — alle ohne LLM-Token und ohne Netz; zusätzlich grün mit Deprecation-Warnings als Fehlern. Lint-Baseline: `ruff check src tests` = sauber.

## 14 · Projektstruktur

```
src/gen/
  core/                state.py (Claim/Quantity/Spec …), interfaces.py, errors.py, …
  agents/              scout, scholar, skeptic, conductor, synthesizer, architect
  ledger/              In-Memory- + Postgres-Fakten-Ledger (Quellenzwang)
  tools/, llm/         ehrliches Fetch/Search, LLM-Boundary (Ollama + ScriptedLLM)
  verification/        gates.py (α/β/γ/δ/ERC/CODE/PROTOCOL), derivation, units,
                       geometry (AABB), cross_model
  export/              OpenSCAD · build123d · STL · Markdown-Bauhandbuch
  fem.py fem3d.py fem3d_quadratic.py plate_hole.py bracket_fem.py
                       FEM: Balken, 3-D-Tets (linear/quadratisch), Loch-Kt, Halter
  torsion.py buckling.py fatigue.py notch_fatigue.py fracture.py contact.py
  pressure_vessel.py creep.py plate_bending.py bolted_joint.py thermal.py
  thermal_stress.py modal.py
                       die 13 Physik-Validatoren (+ Modal-/Thermik-FEM dahinter)
  physics_validation.py   GATE δ-Physik (Registry, nie ein stiller Pass)
  physics_selection.py    Auto-Select: measurand-Tags → Checks + Lücken
  pipeline.py             das eine ehrliche Gesamt-Verdikt
  evaluation.py refinement.py clarification.py ratification.py calibration.py
  telemetry.py geometry_verification.py constraint_consistency.py
  grounding_integrity.py goldset.py
                       die Quality-Engine
  dfm.py orientation.py tolerance.py uncertainty.py montecarlo.py circuit.py
  brep.py software.py costing.py completeness.py
                       weitere δ/ε-Schichten (DFM, Toleranz, GUM/MC, SPICE, BREP, CODE)
  web/                 lokale Web-UI (FastAPI + statisches Frontend)
  config.py runner.py cli.py demo.py
goldset/v1.json        das kuratierte Mess-Set für die Live-Läufe
sql/001_ledger.sql     Quellenzwang als DB-Constraint
docs/                  VISION, ARCHITECTURE, DATA_MODEL, PIPELINE, phases/ (α–δ inkl.
                       PHASE_DELTA.md §1–§51), agents/
tests/                 794 Tests inkl. Gate-Akzeptanz, Physik-Engine, Quality-Engine,
                       Web-API & 4 Frageklassen
```

## 15 · Status & ehrliche Grenzen

**Fertig und bewiesen (offline):** die komplette α/β/γ/δ-Kette mit allen Gates, die Physik-Engine (13 Validatoren + FEM), die Quality-Engine, CLI, Web-UI, Packaging, Gold-Set-Vertrag — 794 Tests, deterministisch, reproduzierbar.

**Live bewiesen:** α (Fakten-Report) und β gegen echte lokale Modelle, inklusive empirischer Bestätigung, dass der Wortlaut-Wächter echte Modell-Paraphrasen abfängt.

**Bewusst offen (owner-gated, wartet auf den gemessenen Erstlauf):**
- der Gold-Set-Lauf gegen Ollama (der Scorer steht bereit),
- die Live-γ-Erstvalidierung (Idee → Spec gegen ein echtes Modell),
- ob ein echtes Modell die `measurand`-Tags zuverlässig deklariert (der Vertrag ist gebaut und scripted bewiesen),
- der Live-Verify→Refine-Loop und Verifizierer-Multi-Sampling.

**Prinzipielle Grenzen (deklariert, nicht versteckt):** Die Physik-Validatoren sind lineare Ingenieursmodelle mit dokumentierten Annahmen — ein bestandener Check ist *notwendig, nicht hinreichend* für ein sicheres reales Produkt. GENESIS spezifiziert und prüft; bauen, messen und verantworten muss weiterhin ein Mensch — genau dafür existiert der Sign-off.

## 16 · Dokumentation

| Dokument | Inhalt |
|---|---|
| `docs/VISION.md` | Warum es GENESIS gibt; Stand der Technik; Risiken |
| `docs/ARCHITECTURE.md` | Datenfluss, State, Gesamtbild |
| `docs/DATA_MODEL.md` | Ledger + Graph + DB-Schema, exakt |
| `docs/PIPELINE.md` | Die Phasen und ihre Gates |
| `docs/phases/PHASE_ALPHA…DELTA(.RESULT).md` | Max. Detail pro Phase; RESULT-Dateien sind ehrliche, historische Abnahme-Snapshots |
| `docs/phases/PHASE_DELTA.md` (§1–§51) | Jede Validierungs-Schicht: was sie fängt, wogegen sie verifiziert ist, was ihre ehrliche Grenze ist, Quelle |
| `docs/agents/*.md` | Pro Agent: Verantwortung, I/O, Werkzeuge, Fehlerzustände |
| `CLAUDE.md` / `CONTRIBUTING.md` | Arbeitskonventionen; ein Commit = ein selbstkontrollierter Schritt |

---

*GENESIS behandelt seine eigene Dokumentation nach demselben Prinzip wie seine Outputs: Zahlen sind gemessen, nicht hochgerechnet; Grenzen sind deklariert, nicht versteckt; und was noch nicht bewiesen ist, steht unter „offen" — nicht unter „fertig".*
