# DOC ↔ CODE DRIFT — was geschrieben steht vs. was implementiert ist

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
| `GENESIS_TODO.md` §3.5 (Z.18): „FragmentStore + **SourceConnectorRegistry**" | FragmentStore = `wissensbasis/store.py` ✓ — **SourceConnectorRegistry existiert NICHT** | `grep -riE 'SourceConnectorRegistry\|source_connector' src/gen/` → 0 Treffer |
| `GENESIS_TODO.md` Z.67: „KiCad-Export/PCB-Layout … abgeschlossen" | Kein KiCad-Adapter; nur interne regelbasierte Place/Route/DRC | keine `kicad`-Adapter-Module; `grenzverschiebung/lumencrucible.py` Z.50 nennt KiCad/Ansys selbst „external-tool seams" |
| `GENESIS_TODO.md` Z.25 / `HORIZON.md` Z.29: „~950 passed" / „950 passed / 19 skipped" | **1185 passed / 9 skipped** (frisch gemessen) | `python -m pytest -q` |

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

- Lab Notebook · Measurement Plan Builder · **SourceConnectorRegistry** · Reference Case Library
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

## 6 · Methode & Grenzen dieses Audits (ehrlich)

- **Geprüft:** Existenz (Datei/Symbol via `grep`/`find`) + Test-Präsenz (Testdatei vorhanden,
  Suite grün).
- **NICHT geprüft:** tiefe Korrektheit/Reife jedes Frontier-Moduls. „Existiert + getestet" ≠
  „produktionsvalidiert" — die Live-/Real-World-Validierung ist owner-gated (README §15).
- **Nicht erschöpfend** gegen `GENESIS_PLATFORM_PLAN.md` (2183 Z.) und `BUILD_LOG.md` (7338 Z.)
  abgeglichen — nur die aktionablen TODO-/Status-Aussagen.

---

## 7 · Empfohlene Folge-Schritte (klein, je verifizierbar — auf „go")

1. `HORIZON.md` §4: φ/χ-Status → ✓ (Belege s. §3) + Test-Count auf 1185/9.
2. `GENESIS_TODO.md`: die zwei Overclaims korrigieren (SourceConnectorRegistry = nicht gebaut;
   KiCad = interne Äquivalente, kein Adapter) + Test-Count.
3. `GENESIS_PLATFORM_BUILD_TODO.md`: gebaute Items `[x]` abhaken (s. §2) — oder die Datei durch
   den Status dieses Drift-Dokuments ersetzen, statt sie weiter divergieren zu lassen.
4. Optional: die genuin ungebauten Plattform-Kappen (§2) entweder bauen oder explizit als
   „nicht geplant" markieren, damit sie nicht als stille Schuld weiterlaufen.
