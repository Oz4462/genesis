# Phase L2 — Recall-Tuning + Drift/Recall-Wiring (2026-06-14)

## Item 1 — Skeptic model-driven Verifikations-Queries (Recall-Tuning)

- `skeptic._check_queries` reformuliert jetzt per Verifier-Modell 2–4 Such-Queries für
  **unabhängige** Evidenz (statt nur den wörtlichen Claim-Text), behält den Claim-Text
  immer als Baseline und fällt bei jedem Fehler auf ihn zurück (nie leer, nie erfunden).
  `src/gen/agents/skeptic.py` (+ `_QUERY_SYSTEM`). arXiv ist bereits in den Skeptic-Backends
  (runner reicht `deps.backends` durch).
- **Beweis:** `tests/test_skeptic_query_reformulation.py` — ein Claim, dessen wörtlicher Text
  KEINE unabhängige Quelle findet, dessen reformulierte Query aber schon, wird **VERIFIED**
  (verbatim-only wäre UNSUPPORTED). Bestehende Skeptic/α-Acceptance-Tests unverändert grün.

## Item 2a — Cross-Run Output-Drift (Monitoring, nicht Core-Gate)

- **Designentscheidung (ehrlich):** Genesis-Phasen-Gates sind deterministisch + LLM-frei;
  Modell-Output-Drift braucht Embedder + **Cross-Run-Baseline** → gehört in die
  Monitoring-Schicht, NICHT in ein Phasen-Gate. `gen.integration.drift.detect_run_drift`
  embeddet die Output-Claim-Texte eines Laufs und testet sie gegen eine Baseline früherer
  Läufe mit dem CCDD-`DriftMonitor` (Phase 1). Opt-in (`verify`-Extra).
- **Beweis:** `tests/test_integration_item2.py` — verschobener Lauf → Alarm; in-Distribution → still.

## Item 2b — Memory-Recall-Vorfilter (provenance-erhaltend)

- `VerifiedFactsLibrary` speichert jetzt die **Quellen** des Claims mit (`ReasoningStep.produces`)
  und `RecalledFact.sources` gibt sie zurück → ein recallter Fakt bleibt „kein Fakt ohne Quelle"
  (verifiziert-in-früherem-Lauf, nicht quellenlos).
- `gen.integration.audited_run(recall=True, library=…)` recallt die Frage VOR dem Lauf gegen
  die Library und liefert die Treffer als `reused_facts` (mit Provenance) — der Cross-Run-Vorfilter.
- **Vorbedingung (ehrlich, Schritt-9-Fix):** Der Vorfilter feuert NUR, wenn der Aufrufer die
  Library vorher separat kalibriert hat (`library.add_calibration(...)`, `min_calibration=30`) —
  `audited_run` kalibriert nie selbst. Auf kalter Library abstiniert der Recall per Design;
  das Ergebnis sagt das explizit über `AuditedRunResult.recall_status`
  (`"disabled" | "uncalibrated" | "no_match" | "hit"`), damit „abstiniert weil unkalibriert"
  nie wie „ehrlich nichts gefunden" aussieht. End-zu-End-Beweis auf gewarmter Library:
  `tests/test_audited_run_recall.py`.
- **Ehrliche Grenze:** Der Vorfilter *signalisiert* Wiederverwendbares; er **kürzt den Lauf
  noch nicht ab**. Ein echtes Scout-Short-Circuit kollidiert mit der per-Lauf-Fetch-Audit-
  Invariante (recallte Quellen wurden nicht in DIESEM Lauf gefetcht) → bewusst deferred,
  bis ein „reused-fact"-Pfad im Gate/Ledger sauber modelliert ist.

## Verifikation

- Neue Tests grün: reformulation 1, drift 2, recall-provenance 1 (+ Regression).
- **Volle Suite: 872 passed, 19 skipped, 0 Fehler.** ruff: All checks passed.
