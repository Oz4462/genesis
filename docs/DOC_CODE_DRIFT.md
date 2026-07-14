# DOC ↔ CODE DRIFT — was geschrieben steht vs. was implementiert ist

> **ABGELÖST / HISTORISCH.** Dieses Dokument ist selbst gedriftet (nannte u. a. „27 Validatoren";
> Live-Stand 2026-07-12: **44** Validatoren / 38 Recipes — siehe `CLAUDE.md` / `docs/STATUS.md`).
> **Live-SSOT:** `docs/STATUS.md` · Agent-Ops: `CLAUDE.md` · Kampagne: `docs/REWORK_CAMPAIGN.md`.  
> Audit-Snapshot: `docs/AUDIT_2026-07-04.md` (Zahlen veraltet). Dieses File nur noch als
> historische Drift-Analyse belassen — **nicht** als Live-Inventar zitieren.

**Stand:** 2026-06-17 · **Methode:** die Plan-/TODO-/HORIZON-Dokumente gegen den realen
`src/gen/`-Baum + die Test-Suite geprüft (**Existenz** via `grep`/`find` + **Test-Präsenz**,
kein tiefer Reife-Audit). Suite zum Zeitpunkt: **1185 passed / 9 skipped**, `ruff check .` clean.

> Warum dieses Dokument: Die autonomen Build-Logs (`GENESIS_TODO.md`,
> `GENESIS_PLATFORM_BUILD_TODO.md`, `BUILD_LOG.md`) wurden im Eifer geschrieben und nie
> konsequent gegen den Code abgeglichen. Hier steht ehrlich, was wirklich gebaut ist, was
> nur geplant/aufgeschrieben ist, und wo die Dokumente vom Code abweichen — in beide
> Richtungen. Gleiches Prinzip wie GENESIS selbst: jede Aussage trägt ihre Evidenz.

---

## 1 · Dokumente, die ÜBER den Code hinaus behaupten (Overclaim — wichtigste Klasse)

Das hier ist der Kern der Frage „aufgeschrieben, aber nicht implementiert":

| Aufgeschrieben als gebaut | Realität im Code | Evidenz |
|---|---|---|
| `GENESIS_TODO.md` Z.67: „KiCad-Export/PCB-Layout … abgeschlossen" | Kein KiCad-**Adapter/-Export**; nur interne regelbasierte Place/Route/DRC | keine `kicad`-Adapter-Module; `grenzverschiebung/lumencrucible.py` Z.50 nennt KiCad/Ansys selbst „external-tool seams" mit „strong internal deterministic equivalents" |
| `GENESIS_TODO.md` Z.25 / `HORIZON.md` Z.29: „~950 passed" / „950 passed / 19 skipped" | **1185 passed / 9 skipped** (frisch gemessen) | `python -m pytest -q` |

> Korrektur-Hinweis (Selbst-Audit): Ein erster Entwurf dieses Dokuments listete hier auch
> „SourceConnectorRegistry existiert nicht". **Das war falsch** — verursacht durch ein fehlerhaftes
> `grep -E '…\|…'` (Backslash-Pipe wurde als Literal gesucht). `class SourceConnectorRegistry`
> existiert in `wissensbasis/store.py:213`; `GENESIS_TODO.md` §3.5 war an dieser Stelle korrekt.
> Beim erneuten, korrekten Grep entfernt. (Genau die Verifikation, die GENESIS predigt.)

---

## 2 · `GENESIS_PLATFORM_BUILD_TODO.md` — Checkboxen komplett unzuverlässig

**46× `[ ]` (offen), 0× `[x]` (erledigt)** — die Datei wurde nie abgehakt, obwohl ein großer
Teil längst gebaut ist. Als Status-Quelle damit **wertlos**; sie liest sich wie „nichts gebaut",
während der Code das Gegenteil zeigt.

**Tatsächlich GEBAUT (Checkbox steht fälschlich auf `[ ]`):**

| BUILD_TODO-Item | Implementierung |
|---|---|
| Teststand Architect | `grenzverschiebung/teststand_architect.py` (+ `tests/test_teststand_architect.py`) |
| Experiment Designer | `grenzverschiebung/experiment_designer.py` |
| Bench Test Runner | `grenzverschiebung/bench_test_runner.py` |
| `DevelopmentFrontMap` | `grenzverschiebung/development_front.py` |
| `CapabilityGap` | `grenzverschiebung/capability_gap_analyzer.py` |
| `MilestoneLadder` | `grenzverschiebung/milestone_builder.py` |
| `SimulationSpec` / `SimulationReceipt` / `ModelContract` | `simulation/runner.py` (+ `tests/test_simulation_runner.py`) |
| erster FEM/CFD Runner | `fem.py` / `fem3d.py` (FEM ✓; CFD nein) |
| Manufacturing Runner / Prototype CAD Builder | `cad/manufacturing_check.py`, `cad/prototype_cad_builder.py` |

**Genuin NICHT gebaut (verifiziert abwesend — `grep` → 0 Treffer in `src/gen/`):**

- Lab Notebook · Measurement Plan Builder · Reference Case Library
- Mesh Gate · Convergence Gate (die Simulations-Qualitäts-Gates)
- Readiness Ladder · Resource Planner · Teacher Mode · Community Evidence Store · Proof Package Generator (Plattform-Kappen)
- `docs/architecture/{MODULE_CONTRACT,SOURCE_CONNECTORS,RD_SYSTEM,SIMULATION_CONTRACT}.md` — das Verzeichnis `docs/architecture/` existiert nicht
- `docs/integration/CAD_CAPABILITY_AUDIT.md` — abwesend (`docs/integration/PRINTFORGE_INVENTORY.md` existiert)
- Externe CAD/EDA-Adapter: **FreeCAD · KiCad · PRINTFORGE** — keine Adapter-Module; bewusste externe Nähte, intern existieren deterministische Äquivalente
- „erster vollständiger Plattform-Demo-Pfad" (E2E über alle Schichten)

---

## 3 · `HORIZON.md` §4 — Status-Tabelle understated (Doku hinkt dem Code nach)

`HORIZON.md` §4 markiert **φ „zu beweisen — erster Stein"** und **χ „zu beweisen"** — beide
sind in Wahrheit gebaut, gegated und getestet:

- **φ**: `agents/forge.py` + `gate_phi` (`verification/gates.py:569`) + `tests/test_phase_phi.py`
- **χ**: `gate_chi` (`verification/gates.py:658`) + `tests/test_phase_chi.py`
- δ⁺/γ⁺/ε/ζ/Ω sind dort korrekt als ✓ markiert; Gates verifiziert in `reality.py:84`,
  `coverage.py:213`, `inverse_design.py:273`, `seams.py:294`, `memory_fabric.py:89`, `omega.py:307`.

Zusätzlich ist `HORIZON.md` Z.29 mit „950 passed / 19 skipped" stale (real 1185/9).

---

## 4 · Code OHNE Doku (Underclaim — Code > README, der ungefährliche Drift)

Die folgende Schicht existiert im Code (vom 1185-Test-Lauf gedeckt), fehlte aber komplett im
README. **Am 2026-06-17 in README §15 ehrlich ergänzt** (gebaut + gegated + getestet, mit
explizitem „nicht produktionsvalidiert"-Vorbehalt):

- HORIZON φ–Ω (8 deterministische Gates, s. §3)
- `grenzverschiebung/` (14 Module inkl. LUMENCRUCIBLE) · `extensions/breakthrough_bridge.py`
- `pipelines/` (11 Fach-Pipelines: Architekt/Ingenieur/Physiker/Techniker/Elektriker/Designer/Fertigung/Software/Regulatorik/Wirtschaft/Integrator)
- `simulation/` (runner + quantum_opt) · `electronics.py`
- `lernmaschine/` (8-Schritt-Lernzyklus) · `wissensbasis/` (`store`, `evidence`, `bio_molecular`)

---

## 5 · Bereits getrackter Code-Backlog (kein versehentlicher Drift — bewusst deferred)

`WORK_QUEUE.md` führt **D1–D13** (Architektur-/Risiko-Findings aus dem Modul-Review,
Claude×Grok) + die owner-gated Items (Branch mergen/pushen, Live-Ollama / Live-γ-Erstlauf,
Gold-Set-Lauf). Diese sind dokumentiert-und-bewusst-offen, kein Drift.

---

## 6 · CAD- und Math/Physik-Erweiterungen — real vs. Stub/unfertig

Auf Nachfrage („full CAD + Math/Physik-Erweiterungen, die auch"): beide Schichten existieren und sind
breit getestet — aber die *Vollständigkeits*-Claims der Build-Logs stehen teils auf bewusst gelabelten
Stubs. Keine dieser Stub-Stellen ist ein *stiller* Fehler (sie sind im Code als `stub` markiert); die
Drift liegt allein darin, dass die Build-Logs sie als „abgeschlossen" zusammenfassen.

### Math/Physik — solider, getesteter Kern; „Excellent"-Upgrade unvollständig
- **Real + getestet (~30 Testdateien):** die 27 Validatoren + FEM — `torsion`, `buckling`, `fatigue`,
  `notch_fatigue`, `fracture`, `contact`, `creep`, `pressure_vessel`, `plate_bending`, `bolted_joint`,
  `thermal`, `thermal_stress`, `modal`, `fem`/`fem3d`/`fem3d_quadratic`/`bracket_fem`, `montecarlo`,
  `uncertainty`, `tolerance`, `circuit` — je eigene Testdatei, gegen geschlossene Formen (README §5).
- **Ehrliche Grenze (historisch):** fracture Paris m≠2 closed form; m=2 uses `math.log`
  (was documented as NotImplemented — **fixed**; see fracture.py paris_cycles).
  Legacy note below retained for audit trail only — do not re-open as bug:
  ~~`fracture.py:140` wirft `NotImplementedError` für nicht~~  unterstützte Fälle, statt einen falschen Wert zu liefern — deklarierte Lücke, kein stiller Fehler.
- **Unfertig:** die „Geo/Math/Physik von *Gut* auf *Excellent*"-Härtung (GENESIS_TODO Z.40/60) ist
  **nicht abgeschlossen** — der dedizierte Agent endete an `max_tokens` (nach 47 Tool-Calls), kompensiert
  durch partielle manuelle Härtungen. Kern solide; das „Excellent"-Niveau ist teil-erreicht, nicht fertig.

### CAD — Geometrie/Export real + getestet; Fertigungs-/Fab-Breite ist Stub
- **Real + getestet:** `cad/prototype_cad_builder.py` (build123d), `cad/assembly.py`, `brep.py`
  (OpenCASCADE), `export/` (OpenSCAD · build123d · STL · BREP-STL · Markdown), `mesh_integrity.py`,
  `orientation.py`, `dfm.py`, `tolerance.py` — je Testdatei.
- **Bewusst Stub / unfertig (im Code als `stub` gelabelt):**
  - `cad/manufacturing_check.py`: nur **FDM** voll; **CNC / Laser / PCB sind Stubs** (`# CNC stub`,
    `# Laser/sheet stub`, `# PCB stub`); **Kostenmodell ist Stub** (hartkodiert `cost_stub = "Est.
    8-25 EUR …"`, `cost_model_stub`, `qa_plan_stub`).
  - `pipelines/fertigungs.py`: **G-Code-Erzeugung ist ein Text-Stub** (`gcode stub`).
  - `electronics.py:824` **`generate_kicad_schematic_stub`** — die „KiCad"-Ausgabe ist ein minimaler
    S-Expression-Stub (≤ 8 Komponenten), **kein** echter KiCad-Adapter (deckt §1-KiCad-Overclaim);
    `route_harness` hat ebenfalls einen Stub-Pfad.
  - `lernmaschine/engine.py:62`: „Kostenmodell / Stückliste mit realen Preisen fehlt (nur Stub)".
  - `extensions/breakthrough_bridge.py`: Wissensbasis-arXiv-Connector ist Stub (deckt die deferred
    Live-Connectors, §2/§5).

**Ehrliche Summe:** „full CAD" = Geometrie-/Export-/BREP-Pipeline ist echt und getestet; die
*Fertigungs-Breite* (CNC/Laser/PCB), Kosten, G-Code und KiCad sind angefangene Stubs. „Math/Physik-
Erweiterung" = der Validator-/FEM-Kern ist echt und getestet; das „Excellent"-Upgrade ist teil-fertig.

---

## 7 · Methode & Grenzen dieses Audits (ehrlich)

- **Geprüft:** Existenz (Datei/Symbol via `grep`/`find`) + Test-Präsenz (Testdatei vorhanden,
  Suite grün).
- **NICHT geprüft:** tiefe Korrektheit/Reife jedes Frontier-Moduls. „Existiert + getestet" ≠
  „produktionsvalidiert" — die Live-/Real-World-Validierung ist owner-gated (README §15).
- **Nicht erschöpfend** gegen `GENESIS_PLATFORM_PLAN.md` (2183 Z.) und `BUILD_LOG.md` (7338 Z.)
  abgeglichen — nur die aktionablen TODO-/Status-Aussagen.

---

## 8 · Empfohlene Folge-Schritte (klein, je verifizierbar — auf „go")

1. `HORIZON.md` §4: φ/χ-Status → ✓ (Belege s. §3) + Test-Count auf 1185/9.
2. `GENESIS_TODO.md`: die zwei Overclaims korrigieren (SourceConnectorRegistry = nicht gebaut;
   KiCad = interne Äquivalente, kein Adapter) + Test-Count.
3. `GENESIS_PLATFORM_BUILD_TODO.md`: gebaute Items `[x]` abhaken (s. §2) — oder die Datei durch
   den Status dieses Drift-Dokuments ersetzen, statt sie weiter divergieren zu lassen.
4. Optional: die genuin ungebauten Plattform-Kappen (§2) entweder bauen oder explizit als
   „nicht geplant" markieren, damit sie nicht als stille Schuld weiterlaufen.
5. Die CAD-Fertigungs-Stubs (CNC/Laser/PCB/Kosten/G-Code/KiCad, §6) und das unfertige
   „Excellent"-Math/Physik-Upgrade entweder fertig bauen oder in den Build-Logs als
   „Stub/teilfertig" statt „abgeschlossen" kennzeichnen.
