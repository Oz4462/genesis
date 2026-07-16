# CLAUDE.md — GENESIS (operativ)

> Die **einzige** operative Arbeitsanweisung für Claude Code / Coding-Agents in diesem Repo.
> **Konsolidiert:** 2026-07-04 · **Zahlen + Fokus re-synchronisiert:** 2026-07-12.
>
> **SSOT Produkt-Wahrheit:** [`docs/STATUS.md`](docs/STATUS.md) — bei Konflikt mit CLAUDE.md
> (Zahlen, Campaign-Stand, CLI-Tabelle) **gewinnt STATUS**. Campaign-Checklist:
> [`docs/REWORK_CAMPAIGN.md`](docs/REWORK_CAMPAIGN.md). Island-Disposition:
> [`docs/ISLAND_TRIAGE_2026-07-11.md`](docs/ISLAND_TRIAGE_2026-07-11.md).
>
> Vision/Architektur: `docs/VISION.md`. Phasen-Historie: `docs/phases/` (α–δ) +
> `docs/HORIZON.md` (φ→Ω inkl. δ⁺/γ⁺/ε/ζ). Historische Snapshots: `docs/BUILD_HISTORY.md`,
> `docs/AUDIT_2026-07-04.md`. **Bei Konflikt gewinnen die Kernprinzipien (§ unten).**

## Was GENESIS ist (in einem Satz)

Ein Mensch liefert ein Problem oder eine Idee; GENESIS recherchiert, verifiziert, synthetisiert,
detailliert, simuliert und liefert eine umsetzbare Spezifikation — **ohne Halluzination**.

## Kernprinzipien (überschreiben alles andere)

1. **Kein faktischer Output ohne Quelle.** Jede Behauptung lebt im Fakten-Ledger mit Quelle,
   Confidence und Verifikations-Status. Code, der faktische Claims ohne Ledger-Eintrag erzeugt, ist ein Bug.
2. **Verifikation ist ein Gate, kein Vorschlag.** Eine Phase darf erst enden, wenn ihr Gate bestanden ist.
3. **Cross-Model.** Der Verifikator (`skeptic`) nutzt ein anderes Modell als der Generator.
4. **"Ich weiß es nicht" ist ein gültiger, erwünschter Output.** Refusal/Abstention wird gemessen, nicht bestraft.
5. **Determinismus & Reproduzierbarkeit.** Jeder Lauf hat eine `run_id`, ist gecheckpointet und
   aus Ledger + Config exakt reproduzierbar.
6. **Stack-Agnostik.** Code gegen die Interfaces in `src/gen/core/interfaces.py`, nicht gegen ein
   konkretes Framework. Framework-spezifisches lebt hinter Adaptern.

## Arbeitskonventionen

- **Sprache:** Code/Kommentare/Identifier Englisch; Doku Deutsch ok. Nutzer-sichtbare Ergebnisse
  DEUTSCH (Owner-Direktive 2026-06-12; Zitate wortlautgetreu; ids/units/Formeln/Gate-Diagnostik englisch).
- **Jede neue Funktion braucht:** Typ-Annotationen, Docstring (was/warum), dokumentierte Fehlerfälle,
  mindestens einen Test (inkl. Negativtest).
- **Jeder Agent** erfüllt das `Agent`-Protocol (`core/interfaces.py`).
- **Keine stillen Defaults bei faktischen Dingen.** Lieber Exception als geratener Wert.
- **Tests zuerst für Gates.** Ein Gate ohne Test existiert nicht.
- **Vor neuem Modul erst `grep`/Read** — keine Duplikate.
- **4 Linsen** nach jeder Arbeitseinheit (`docs/4_LINSEN_PRINZIP.md`): L1 Wahrheit · L2 Drift ·
  L3 Vollständigkeit/Naht · L4 Realisierbarkeit; Selbstkontrolle im `docs/BUILD_LOG.md`.
- **Zahlen-Claims in Doku sind Messwerte:** nur mit frischem Messlauf ändern; historische Snapshots
  **datieren und labeln** (Wurzel des Doku-Drifts, siehe Audit 2026-07-04).

## Definition of Done (pro Aufgabe)

- [ ] Interface erfüllt, Typen geprüft
- [ ] Tests grün (inkl. mindestens ein Negativtest)
- [ ] Ledger-Einträge korrekt (falls faktisch)
- [ ] Gate-Bedingung im Code geprüft (falls Phasen-relevant)
- [ ] Doku des Agenten/Moduls aktualisiert
- [ ] 4 Linsen angewendet + dokumentiert (BUILD_LOG)

## Verzeichnis (Kurzkarte)

```
docs/STATUS.md              SSOT Produkt-Wahrheit (curated + AUTO-Block)
docs/REWORK_CAMPAIGN.md     Module-Checklist REWORK 2026-07-11/12
docs/ISLAND_TRIAGE_*.md     Island-Disposition (KEEP_OPTIN / PRODUCT_WIRE / …)
docs/CAPABILITIES.md        Fähigkeits-Inventar (untergeordnet STATUS)
docs/VISION.md · ARCHITECTURE.md · PIPELINE.md · DATA_MODEL.md
docs/phases/                α–δ Spezifikation + RESULT
docs/HORIZON.md             φ, χ, δ⁺, γ⁺, ε, ζ, Ω (Phasen + ehrliche Gaps)
docs/AUDIT_2026-07-04.md    Historisches Voll-Audit (Zahlen veraltet — nicht als Live-Stand zitieren)
WORK_QUEUE.md               Historischer Deep-Review-Backlog (viele Checkboxen ungepflegt)
docs/BUILD_LOG.md           Arbeitsprotokoll
docs/SESSION_HANDOFF_*.md   Session-Handoffs
src/gen/core|agents|ledger|verification/   Kern
src/gen/discovery/          Universe-Explorer
src/gen/pipelines/          Fach-Pipelines
src/gen/product_surface.py  CLI-Reachability-Anker (find_islands)
src/gen/<physik>.py         δ-Achsen · tests/
scripts/find_islands.py · scripts/gen_status.py
```

## Verifizierter Ist-Stand (gemessen 2026-07-15 — nicht fortschreiben ohne Messung)

> Ältere Zeilen in AUDIT (2026-07-04: 1727p/61s), CLAUDE-Stand 2026-07-04 (2079p/43s)
> und 2026-07-12 (2494 collected · 44/38/8 · 327/258/26) sind **historische Snapshots**,
> keine Live-Zahlen.

| Messgröße | Wert (2026-07-15) | Quelle |
|-----------|-------------------|--------|
| Tests collected | **2594** | `pytest --collect-only -q` |
| Voller Suite-Lauf | **2557 passed / 49 skipped / 0 failed** (Stand `34dc771`, 34:25 min lokal mit cad-venv; CI 3.11+3.12 ohne Kernel ebenfalls grün) | `pytest tests -q` |
| Validatoren | **45** | `len(physics_validation.VALIDATORS)` |
| Recipes | **46** | `len(physics_selection.RECIPES)` |
| MANUAL_ONLY-Validatoren | **1** (`montecarlo_product` auto-selektiert seit 2026-07-14) | `physics_selection.MANUAL_ONLY_VALIDATORS` |
| Discovery-Module (`.py` exkl. `__init__`) | **39** | `src/gen/discovery/` |
| Reachability | modules **334** · WIRED **266** · SCRIPT **9** · ISLAND **25** · INFRA **34** | `scripts/find_islands.py` |
| REWORK-Module OPEN | **0** (~303 REWORKED) | `docs/REWORK_CAMPAIGN.md` |
| CLI-Modi | **51** (inkl. `sources` / `caps` / `multi-physics` seit Phase D/E) | `gen.cli` choices |

**Phasen (gebaut + getestet, nicht „fertig im Sinne von allwissend“):**

- Kernbogen α–δ: `docs/phases/` + Pipeline/Gates
- HORIZON: φ (`divergence`), χ (`frontier`), δ⁺, γ⁺, ε, ζ, Ω — siehe `docs/HORIZON.md` und
  `tests/test_phase_*.py`. Offline-CLI u. a.: `council`, `feynman`, `campaign`, `horizon-full`,
  `goldset` (Demos grün; Live-LLM optional).

**Discovery / Frontier (Kurz, ohne abgebrochene Formeln):** Module u. a. `additive_argument`,
`gp_search`, `multiterm`, `transcendental`, `symbiosis`, `campaign` — Details und ehrliche Ablehnungen
(z. B. allgemeine Komposition `f(g(·))`) stehen in den Modul-Docstrings und
`docs/discovery/` falls vorhanden. **Keine unvollständigen Formeln in CLAUDE.md zitieren.**

**Git (2026-07-12):**

- Default-Branch **`main`** trackt **`origin/main`** (GitHub `Oz4462/genesis`).
- REWORK-Kampagne + Continue über **PR #1–#9** auf `main` gemerged (CI 3.11+3.12).
- **Nicht** behaupten „lokal 35 Commits vor origin/main“ — das war ein veralteter
  Worktree-Stand und ist **nicht** der Live-Stand. Ungepushte/private Branches sind
  **owner-gated**, nicht stillschweigend „main“.

## Aktueller Fokus (2026-07-15)

0. **Backlog-Phasen A–G abgeschlossen** (H1–H5, C1–C8, W1–W5, S1–S4, X1–X4, G1–G4 —
   siehe `docs/BACKLOG_TODO_PLAN.md` + STATUS). Re-Audit-Befund G1 (stille 0-Byte-STLs
   in `cad/assembly.py`) ist behoben; CAD-Pfad liefert echte Kernel-STLs + top/front-DXF.
   Offene Produkttiefe: full GD&T-Rahmen/PDF, multi-axis CAM, Assembly-Constraints,
   KiCad-Copper/DRC, Harness-Routen, Ready-to-Build-ZIP, multi-physics depth, Viz/Montage
   (H1 2026-07-16: Envelope-Bemaßung + right-view auf Paket-DXF erledigt).

## Fokus-Historie (2026-07-12)

1. **FULL REWORK CAMPAIGN (2026-07-11):** Module-Inventory **REWORKED** (0 OPEN in
   `REWORK_CAMPAIGN.md`). Prior-DONE war nicht vertrauenswürdig bis Suite+Wiring re-proven.
2. **Product surface:** `gen.product_surface` + CLI; Katalog-Reports `aero-report` /
   `humanoid-report`; `surface` zeigt Reachability.
3. **Residual Islands (26):** absichtlich KEEP_OPTIN / experimental / SCRIPT-adjacent
   (Postgres, MCP, GPU-oracle, Solver, Humanoid-SCRIPT, RL-Harness) — siehe ISLAND_TRIAGE.
   **Nicht** massenhaft in den CLI-Import zwingen (bricht Startup ohne optionale Stacks).
4. **Optional nächste Schicht:** unabhängiges **VERIFIED** (4 Linsen) auf High-Risk-Modulen;
   optional `scripts/gen_status.py` AUTO-Block nach großen Merges erneuern.
5. **Owner-gated:** Force-Push auf `main` verboten; Live-Ollama/Cloud-LLM; Asset-Downloads
   für Humanoid-Meshes.

## Memory-Konvention

| Datei | Rolle |
|-------|--------|
| **`CLAUDE.md`** (diese Datei) | Operative Agent-Anweisung + datierte Messwerte |
| **`docs/STATUS.md`** | **SSOT** Produkt-Wahrheit (curated + AUTO) |
| **`docs/REWORK_CAMPAIGN.md`** | Campaign-Checklist |
| **`docs/ISLAND_TRIAGE_*.md`** | Island-Disposition |
| **`docs/SESSION_HANDOFF_*.md`** | Session-Übergabe |
| **`docs/BUILD_LOG.md`** | Arbeitseinheiten + 4 Linsen |
| **`WORK_QUEUE.md`** | Historischer Deep-Review-Backlog — **nicht** Live-SSOT |
| **`docs/GENESIS_TODO.md`**, **`docs/GENESIS_PLATFORM_BUILD_TODO.md`**, **`docs/OPEN_MODULES_FULL_LIST.md`** | **Eingefroren / historisch** (Checkboxen oft ungepflegt; Audit B1) — nur Referenz |
| **`docs/AUDIT_2026-07-04.md`** | Historisches Audit — Zahlen **nicht** als Live-Stand zitieren |

- Session-übergreifendes Wissen: **STATUS / REWORK / Handoff / diese CLAUDE.md** — keine parallelen
  Schatten-TODOs anlegen.
- Jeder Arbeitsschritt: Conventional Commit + Push auf Feature-Branch + PR; nach CI grün mergen.
  Vor ~500k Context: Handoff aktualisieren.

## Schnell-Verify

```bash
cd /home/genesis/genesis
.venv/bin/python -c "from gen.physics_validation import VALIDATORS; from gen.physics_selection import RECIPES; print(len(VALIDATORS), len(RECIPES))"
.venv/bin/python scripts/find_islands.py | head -8
.venv/bin/python -m pytest --collect-only -q | tail -3
.venv/bin/python -m gen --mode surface | tail -5
```
