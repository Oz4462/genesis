# CLAUDE.md — GENESIS (operativ)

> Die **einzige** operative Arbeitsanweisung für Claude Code in diesem Repo (konsolidiert
> 2026-07-04, Audit: `docs/AUDIT_2026-07-04.md`). Vision/Architektur: `docs/VISION.md`.
> Phasen-Historie: `docs/phases/` (α–δ) + `docs/HORIZON.md` (φ→Ω). Historische
> Status-Snapshots: `docs/BUILD_HISTORY.md`. **Bei Konflikt gewinnen die Kernprinzipien.**

## Was GENESIS ist (in einem Satz)
Ein Mensch liefert ein Problem oder eine Idee; GENESIS recherchiert, verifiziert, synthetisiert, detailliert, simuliert und liefert eine umsetzbare Spezifikation — **ohne Halluzination**.

## Kernprinzipien (überschreiben alles andere)
1. **Kein faktischer Output ohne Quelle.** Jede Behauptung lebt im Fakten-Ledger mit Quelle, Confidence und Verifikations-Status. Code, der faktische Claims ohne Ledger-Eintrag erzeugt, ist ein Bug.
2. **Verifikation ist ein Gate, kein Vorschlag.** Eine Phase darf erst enden, wenn ihr Gate bestanden ist. Gates sind im Code als harte Bedingungen implementiert.
3. **Cross-Model.** Der Verifikator (`skeptic`) nutzt ein anderes Modell als der Generator. Single-Model-Self-Check zählt nicht als Verifikation.
4. **"Ich weiß es nicht" ist ein gültiger, erwünschter Output.** Refusal/Abstention wird gemessen, nicht bestraft.
5. **Determinismus & Reproduzierbarkeit.** Jeder Lauf hat eine `run_id`, ist gecheckpointet und aus Ledger + Config exakt reproduzierbar.
6. **Stack-Agnostik.** Code gegen die Interfaces in `src/gen/core/interfaces.py`, nicht gegen ein konkretes Framework. Framework-spezifisches lebt hinter Adaptern.

## Arbeitskonventionen
- **Sprache:** Code/Kommentare/Identifier Englisch; Doku Deutsch ok. Nutzer-sichtbare Ergebnisse DEUTSCH (Owner-Direktive 2026-06-12; Zitate wortlautgetreu in Quellsprache, ids/units/Formeln/measurands/Gate-Diagnostik englisch).
- **Jede neue Funktion braucht:** Typ-Annotationen, Docstring (was/warum), dokumentierte Fehlerfälle, mindestens einen Test (inkl. Negativtest).
- **Jeder Agent** erfüllt das `Agent`-Protocol (`core/interfaces.py`): explizites Input-/Output-Schema, deklarierte Tools und Fehlerzustände.
- **Keine stillen Defaults bei faktischen Dingen.** Lieber Exception als geratener Wert (Beispiel: `fracture.py` wirft bewusst `NotImplementedError` für Mixed-Mode).
- **Tests zuerst für Gates.** Ein Gate ohne Test existiert nicht.
- **Vor neuem Modul erst `grep`/Read prüfen, ob es schon existiert** (Lektion 2026-06-19: Beinahe-Duplizierung von `training_plan.py`).
- **4 Linsen nach jeder Arbeitseinheit** (`docs/4_LINSEN_PRINZIP.md`): L1 Wahrheit, L2 Drift, L3 Vollständigkeit/Naht, L4 Realisierbarkeit; Abgleich mit `docs/GENESIS_PLATFORM_PLAN.md`; Selbstkontrolle im BUILD_LOG dokumentieren.
- **Zahlen-Claims in Doku sind Messwerte:** Testsummen/Validator-Zahlen nur mit frischem Messlauf ändern; historische Snapshots als solche labeln (Wurzel des Doku-Drifts, siehe Audit).

## Definition of Done (pro Aufgabe)
- [ ] Interface erfüllt, Typen geprüft
- [ ] Tests grün (inkl. mindestens ein Negativtest: fehlende Quelle / Tool-Fehler / Widerspruch)
- [ ] Ledger-Einträge korrekt erzeugt (falls faktisch)
- [ ] Gate-Bedingung im Code geprüft (falls Phasen-relevant)
- [ ] Doku des Agenten/Moduls aktualisiert
- [ ] 4 Linsen angewendet + dokumentiert (BUILD_LOG)

## Verzeichnis (Kurzkarte)
```
docs/VISION.md              Warum · docs/ARCHITECTURE.md  Was · docs/PIPELINE.md  7 Phasen
docs/DATA_MODEL.md          Ledger/Graph/DB exakt · sql/  Postgres/pgvector-Schema
docs/phases/                α–δ Spezifikation + RESULT · docs/HORIZON.md  φ→Ω (alle ✓)
docs/agents/*.md            Pro Agent: Prompt, I/O, Tools, Fehler, Tests
docs/AUDIT_2026-07-04.md    Letztes Voll-Audit + priorisierter Verbesserungsplan
WORK_QUEUE.md               Operativer Backlog (Deep-Review-Schritte, Deferred D1–D16)
docs/BUILD_LOG.md           Arbeitsprotokoll · docs/BUILD_HISTORY.md  alte Status-Snapshots
src/gen/core|agents|ledger|verification/   Kern (framework-frei)
src/gen/discovery/          Universe-Explorer (35 Module) · src/gen/pipelines/  Fach-Pipelines
src/gen/<physik>.py         δ-Achsen (structural…security) · tests/  247 Dateien
```

## Verifizierter Ist-Stand (gemessen 2026-07-04 abends, nicht fortschreiben ohne Messung)
- **Testsuite (main, offline): 1853 passed / 0 failed / 61 skipped** (~29 s, `uv run pytest tests/ -q`;
  morgens 1727 — Zuwachs = Schritt-7-Kampagne Batch 1+2, D8–D13, P7, fertigungs-Naht).
- **43 Validatoren** in `physics_validation.VALIDATORS`, **38 Recipes** in `physics_selection.RECIPES` (Auto-Select aus measurand-Tags → ehrliches Gate-Verdikt pass/fail/gap).
- **Discovery: 35 Module**, 146 Discovery-Testfunktionen; `rediscovery_benchmark()` 100 %; Frontier 6.1–6.5 gebaut; offene Frontier: multiplikative/transzendente Kopplungen + GP-Suche (`docs/discovery/STATUS.md`).
- **Alle Phasen gebaut und gegated:** α, β, γ, δ (docs/phases/) + φ, χ, δ⁺, γ⁺, ε, ζ, Ω (HORIZON, je `test_phase_*.py`).
- Live-Default: Generator `qwen3.5:9b` + Verifier `gemma4:12b` (Fallback qwen2.5:14b/gemma4:latest).
- Git: `main` lokal ist der Live-Stand (35 Commits vor `origin/main`); **Push nur auf Owner-Ansage.**

## Aktueller Fokus (2026-07-04, nachgeführt)
1. **Humanoid TP2 „Struktur-Härtung" GEBAUT** (Worktree-Branch `worktree-claude-orchestrator`,
   Commits `b03b4be`/`0b0a0f9`/`f779ed9`): 4 Checks (Goodman-, Kerb-Fatigue, Euler-Knickung,
   Resonanz) feuern via Measurand-Tagging auf beide Humanoiden, 0 neue Validatoren/Recipes;
   Margen echt (printed Kerbe 1.04 dünn — hängt an DECISION a=6 mm, wartet auf Datenblatt).
   Worktree-Suite 1743/0/61. **Offen: Grok-Cross-Review + Merge (owner-gated;** TP1+TP2 =
   17 Commits unmerged, main 11 voraus; Achtung: runner.py-F821-Fix existiert in beiden Ästen).
2. **Deep-Review-Kampagne** (`WORK_QUEUE.md`): **Schritt 7 KOMPLETT** (physics_validation/selection/
   units 7a+7b, modal/orientation/manufacturing 7c, FEM-Schicht 7d `2e13c97`, mesh/brep/circuit 7e
   `f0d14ec`) — alle Claude-seitig; **Grok-Cross-Reviews nachholen** (CLI-Outage 2026-07-04).
   Schritt 8 (export/costing/completeness/software) Reviews laufen; danach Schritt 9.
3. **Deferred-Backlog** (`WORK_QUEUE.md`): D8–D10 `c2f03cd` + D13(a–d) `393d7dc` + D15-geometry
   `28e4ba1` ERLEDIGT; offen: D2 (`_now()`-Determinismus), D1, D4–D6, D11/D12, D14, D16,
   Recipes für die 7 MANUAL_ONLY-Validatoren.
4. **Doku-Hygiene:** Zähl-Drift in README/STATUS/HORIZON fixen (P2 im Audit-Plan).
- **Owner-gated (kein Autonomie-Zugriff):** Push/Merge; Live-Ollama-Läufe + Extraction-Bottleneck;
  measurand-Emission live-Architect; Refine-Loop live-Conductor.

## Memory-Konvention (ab 2026-07-04)
- **Diese CLAUDE.md ist die einzige operative Quelle** für Auftrag, Stand und Fokus. Session-
  übergreifendes Projektwissen wird HIER (Fokus/Ist-Stand) oder in `WORK_QUEUE.md` (Backlog)
  festgehalten — nicht in parallelen TODO-Dateien.
- `docs/GENESIS_TODO.md` + `docs/GENESIS_PLATFORM_BUILD_TODO.md` sind eingefroren (Checkboxen
  ungepflegt, siehe Audit B1) — nur noch historische Referenz.
- Jeder Arbeitsschritt: Commit mit sprechender Message + BUILD_LOG-Eintrag bei Arbeitseinheiten
  mit Selbstkontrolle. `IMPLEMENTATION_PLAN.md` bleibt der separate Meta-Strang (Council-Loop).
