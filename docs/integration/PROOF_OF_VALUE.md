# Mehrwert-Beweis (Proof of Value) — GENESIS-Integrationen

> Stand: 2026-06-13 · Begleitdokument zu `CATALOG.md`.
> Prinzip: **Keine Integration ohne vorab definiertes, messbares Gate.** Gate nicht
> bestanden → keine Integration (ehrliches Abbrechen, GENESIS-Kernprinzip 4).
> Dieses Dokument ist der **schriftliche Beweis-Entwurf**; die empirischen Messläufe
> sind Phase 0 der Ausführung (nach Owner-Freigabe) — siehe Harness-Spezifikationen unten.

## Beweis-Methodik

- **Baseline** = aktueller GENESIS-Stand auf identischem Input (`goldset/v1.json`,
  `src/gen/demo.py`-Welten), gemessen mit dem vorhandenen `src/gen/evaluation.py`
  (Leaks-Metrik) + Determinismus-Check (gleicher `run_id`/seed → gleiches Verdikt).
- **Treatment** = GENESIS + die jeweilige Integration, gleicher Input, gleiche Seeds.
- **Jeder PoV-Lauf** erhält `run_id` + Checkpoint, ist reproduzierbar, Ergebnis als
  signierter Bericht unter `runs/pov/<run_id>/`.
- **Ein Gate liefert eine Zahl**, kein Bauchgefühl. Phase-0-Gate = Owner-Ratifikation der Zahlen
  (`src/gen/ratification.py`-Prinzip: nichts gilt als bestätigt bis explizit ratifiziert).

## Falsifizierbarkeit (was den Mehrwert WIDERLEGEN würde)

Damit der Beweis ehrlich ist, wird jede Hypothese mit einem expliziten
Falsifikations-Kriterium gepaart. Tritt es ein, wird die Integration verworfen oder
zurückgestellt — und das im Bericht dokumentiert.

---

## PoV-1 — trust-core ersetzt/erweitert die Verifikations-Math

- **Hypothese:** trust-core liefert dieselben Garantien wie `src/gen/calibration.py`
  bei **weniger eigenem Code** und **zusätzlicher** Drift-Detection (CCDD), die GENESIS fehlt.
- **Harness:** `scripts/pov/pov1_trustcore.py` (Hinweis: `goldset/v1.json` enthält
  Task-Fälle fact/trap/nonsense, **keine** (confidence, is_true)-Paare — daher prüft die
  Harness die Äquivalenz per randomisiertem Property-Test statt am Gold-Set; das ist
  stärker, weil es den gesamten (n, alpha)-Raum abdeckt).
  1. Äquivalenz: GENESIS `gen.calibration.conformal_quantile` vs trust-core
     `conformal/split.split_conformal_threshold` über 5000 deterministisch gezogene
     (n, scores, alpha)-Fälle; Boundary (GENESIS `None` ⇄ trust-core `+inf`) = äquivalent.
  2. LOC-Zählung der ersetzbaren Genesis-Split-Conformal-Funktionen + der CCDD-LOC, die
     Genesis sonst selbst schreiben müsste.
  3. Neuer CCDD-Drift-Test: `calibrate` + `StreamingDetector` auf No-Shift- vs Shift-Stream.
- **Messgrößen:** Mismatch-Zahl, ersetzbare/gesparte LOC, Drift-Alarm {ja/nein} je Stream.
- **PASS-Gate:** 0 Mismatches **UND** CCDD-Drift erkennt Shift & schweigt bei No-Shift
  **UND** ersetzbare Genesis-LOC > 0 (Netto-LOC final in Phase 1 mit fertigem Adapter belegt).
- **Falsifikation:** ≥1 unerklärter Mismatch, oder Drift-Detektor feuert bei No-Shift / schweigt
  bei Shift → trust-core bringt hier keinen Mehrwert, Eigenimplementierung bleibt.
- **ERGEBNIS (run_id `pov1`, 2026-06-13): PASS.** Äquivalenz 4467 exakt + 533 Boundary,
  **0 Mismatch / 5000**. CCDD: No-Shift kein Alarm, Shift-Alarm @Sample 99. LOC: 35 Genesis-Zeilen
  → Adapter, **+5368 getestete CCDD-Zeilen gratis**. Bericht: `runs/pov/pov1/report.json`.

## PoV-2 — ANAMNESIS Cross-Run-Memory

- **Hypothese:** Ein zweiter Lauf einer gleichen/ähnlichen Frage ist **schneller/günstiger**
  bei **gleicher oder besserer** Korrektheit, weil verifizierte Fakten wiederverwendet werden.
- **Harness (offline-Mechanik-Beweis):** `scripts/pov/pov2_memory.py` — echter
  ANAMNESIS `TraceStore` + `ConformalCalibrator` + `ConformalRetriever`. Die volle
  Token-/Zeit-A/B-Messung braucht einen Live-Ollama-Lauf (owner-gated) und wird hier durch
  „avoided research calls" als Spar-Proxy ersetzt; der Fokus liegt auf der entscheidenden
  Honesty-Eigenschaft.
  1. Verified-facts-Store aus Genesis-typischen Fakten (Gold-Set-„fact"-Stil) füllen.
  2. Kalibrator an Paraphrasen warm laufen lassen (n≥30) → tau.
  3. Wiederholungen (anders formuliert) → korrekter Reuse erwartet.
  4. Nonsense/Novel-Queries (Gold-Set-„nonsense"-Stil) → **Abstention** erwartet (kein false reuse).
  5. Determinismus + Score-Separation (genuine vs novel) als Diagnostik.
- **Messgrößen:** reuse_correct_rate, **false_reuse_rate (Honesty-Gate)**, Score-Separation.
- **PASS-Gate:** false_reuse_rate = 0 **UND** reuse_correct_rate ≥ 0.7 **UND** deterministisch.
- **Falsifikation:** Memory führt false reuse ein, das NICHT auf den Embedder zurückführbar ist,
  oder erkennt Wiederholungen nicht → Memory nur als Audit-Log, nicht als Research-Vorfilter.

## PoV-3 — buch-llm Multi-Agent-Debatte als Synthese-Verifikator

- **Hypothese:** Mehr-Kritiker-Konsens erkennt **mehr unsound Specs** als der Single-`skeptic`,
  ohne sound-Specs fälschlich zu verwerfen, und bleibt deterministisch.
- **Harness:** `scripts/pov/pov3_debate.py`
  1. Gold-Set mit sound/unsound-Specs (vorhandenes Eval-Set in `src/gen/evaluation.py`).
  2. Verdikt-Lauf A: aktueller Single-Skeptic. Lauf B: + portierte 7-Kritiker-Debatte
     (Thompson-Aggregation), Cross-Model-Regel gewahrt (Generator ≠ Kritiker-Modell).
  3. Determinismus: gleicher Seed → gleiches Verdikt, zweifach.
- **Messgrößen:** Leak-Rate (unsound durchgerutscht), sound-Recall, Determinismus {ok/nicht}.
- **PASS-Gate:** Leak-Rate sinkt **UND** sound-Recall unverändert **UND** Determinismus ok.
- **Falsifikation:** Debatte senkt sound-Recall oder ist nicht reproduzierbar → verworfen
  (Determinismus ist nicht verhandelbar, GENESIS-Kernprinzip 5).
- **ERGEBNIS (run_id `pov3`, 2026-06-13): PASS** (echter `DebateOrchestrator.run_debate`,
  isoliert geladen). leak-rate **0.593 → 0.173 (−71%)**, sound-recall 1.000→1.000,
  deterministisch. **Scope-Vorbehalt:** simulierte imperfekte Verifier-Inputs; buch-llm-Critics
  sind selbst noch Stubs → echter End-to-End-Nutzen braucht LLM-verdrahtete Cross-Model-Critics
  + Live-Run (deferred, owner-gated). Bericht: `runs/pov/pov3/report.json`.

## PoV-4 — VERIDEX Governance / Audit

- **Hypothese:** Jeder Lauf kann einen **manipulationssicheren, unabhängig verifizierbaren**
  Audit-Trail erzeugen und **Modell-Drift** erkennen — ohne Determinismus zu brechen.
- **Harness:** `scripts/pov/pov4_audit.py`
  1. Lauf erzeugt aus Genesis-Ledger/Telemetry ein signiertes Audit-Bündel (VERIDEX `audit.py`).
  2. Unabhängiger Verify (Standalone) → grün erwartet.
  3. 1 Byte am Bündel kippen → Verify muss fehlschlagen (Tamper-Erkennung).
  4. Generator-Modell wechseln → CCDD-Drift-Gate muss feuern.
- **Messgrößen:** Verify {grün}, Tamper-Erkennung {ja}, Drift-Alarm bei Wechsel {ja}.
- **PASS-Gate:** alle drei erfüllt.
- **Falsifikation:** Verify-Lücke, kein Tamper-Erkennen, oder Drift-Gate stumm → nicht audit-tauglich.
- **ERGEBNIS (run_id `pov4`, 2026-06-13): PASS.** Signieren→Verify grün; 1 gekipptes Byte →
  Verify schlägt fehl (tamper-evident); fremder Key → abgelehnt; CCDD-Drift feuert bei Shift,
  schweigt bei No-Shift. Genesis hat heute KEIN Signing (keine `cryptography`/`pynacl`-Dep) →
  net-new. Mechanik via trust-core DSSE/Ed25519-Receipts (Det.-Signatur, fixe Seed/issued_at).
  **Scope-Vorbehalt:** der vollständige VERIDEX-Annex-IV/Art-12-Bundle-Wrap ist Phase-4-Adapter-Scope.
  Bericht: `runs/pov/pov4/report.json`.

---

## Phase-0-Gate (Owner-Ratifikation)

Nach Ausführung der vier Harnesses liegt je PoV eine Zahl vor. **Nur PoV mit PASS** gehen
in die jeweilige Integrations-Phase (siehe Plan-Datei Phase 1–4). Reihenfolge bleibt
trust-core → ANAMNESIS → buch-llm-Debatte → VERIDEX. Ergebnis-Tabelle wird hier ergänzt:

| PoV | Δ-Messung (ausfüllen) | Verdikt | Datum/run_id |
|---|---|---|---|
| PoV-1 trust-core | 0 Mismatch/5000; Drift ja/nein korrekt; 35 LOC→Adapter, +5368 CCDD gratis | **PASS** | 2026-06-13 / pov1 |
| PoV-2 ANAMNESIS | **ollama-Embedder:** reuse correct 0.80, **false_reuse 0/8 (0.00)**, Separation 0.217≪0.593 (kein Overlap) | **PASS** | 2026-06-13 / pov2 |
| PoV-3 buch-llm-Debatte | leak-rate 0.593 → **0.173 (−71%)**; sound-recall 1.000→1.000; deterministisch | **PASS** | 2026-06-13 / pov3 |
| PoV-4 VERIDEX | verify ok; tamper erkannt; wrong-key abgelehnt; Drift-Alarm bei Shift, still bei No-Shift | **PASS** | 2026-06-13 / pov4 |

**PoV-2-Befund (final, evidence-grounded):**
- **Mit echtem lokalem Embedder (Ollama `embeddinggemma`, 768-dim):** reuse_correct 0.80,
  **false_reuse 0/8**, Score-Separation genuine 0.217 ≪ novel 0.593 (kein Overlap),
  deterministisch → **PASS**. ANAMNESIS-Reuse erkennt Wiederholungen korrekt UND abstrahiert
  ehrlich bei Nonsense. (`embedder=ollama`; kein pip-Install, kein Netz — lokale Infra.)
- **Mit Spielzeug-`hash_embedder` (Diagnostik):** false_reuse 3/8, Overlap=True → bewies, dass
  das false-reuse ein **Embedder-Artefakt** war, nicht ein Mechanismus-Fehler. Genau diese
  Trennung machte den Befund belastbar.
- **Restbeweis (deferred):** die End-to-End-Token-/Zeit-Ersparnis über den live Genesis-Lauf
  (avoided research calls als Proxy belegt; echtes Δ braucht den live α/γ-Lauf).

## Constraints (gelten für alle PoV + Integrationen)

- Ein aktives Modul zur Zeit; nächste Phase erst nach grünem Gate der vorigen.
- Messläufe sind **read-only** ggü. dem Produktivcode (`src/gen` unverändert bis Integration).
- Lokales Ollama/Postgres nur nach Inspektion; keine `taskkill /IM`/`pkill`; kein force-push;
  kein Live-/Push bis Arbeitspaket fertig + verifiziert.
- Jede Behauptung in den Berichten ist belegt (Zahl + `run_id`), kein „sollte gehen".
