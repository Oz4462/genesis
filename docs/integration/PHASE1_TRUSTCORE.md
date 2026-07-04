# Phase 1 — trust-core Integration (abgeschlossen 2026-06-13)

> Gerechtfertigt durch PoV-1 (PASS): trust-core split-conformal numerisch identisch
> zu Genesis (0 Mismatch/5000) + net-new FDR/Drift. Siehe `PROOF_OF_VALUE.md`.

## Was integriert wurde

- **Dependency:** `trust-core` als optionaler Extra `verify` in `pyproject.toml`
  (`pip install -e ".[verify]"`; editable installiert aus `../../../alle apps/trust-core`).
  Core bleibt numpy-only — `verify` ist opt-in, nicht in `gen.verification.__init__`.
- **`src/gen/verification/trustcore_adapter.py`** (net-new, geführter Import):
  - `split_conformal_threshold(scores, alpha) -> float|None` — trust-core split-conformal
    in Genesis-None-Konvention (inf→None, leer→None).
  - `bh_fdr_threshold` / `bh_adjusted_qvalues` — Benjamini-Hochberg FDR (**net-new**:
    Batch-Claim-Akzeptanz mit kontrollierter False-Discovery-Rate).
- **`src/gen/verification/drift_monitor.py`** (net-new, geführter Import):
  - `DriftMonitor` über trust-core CCDD (`calibrate` + `StreamingDetector`) — erkennt
    Modell-Output-Drift gegen eine Baseline; **Fähigkeit, die Genesis komplett fehlte**.
    Honest: Monitoring-Signal (öffnet Review), kein harter Phasen-Gate, da RunState noch
    keine Output-Embeddings trägt (Verdrahtung deferred bis Embedding-Capture existiert).
- **Tests:** `tests/test_trustcore_adapter.py` (4) + `tests/test_drift_monitor.py` (3),
  `pytest.importorskip("trust_core.<benötigtes submodul>")` → skip-sauber ohne den Extra
  UND unter dem PyPI-Namesake (offline-core erhalten; s. „deferred" unten, 2026-07-04).

## Bewusste Abweichung (Owner-ratifizierbar)

Die Regel „Migration entfernt alten Pfad komplett (100% oder gar nicht)" kollidiert hier
mit der Genesis-Invariante „Core numpy-only, Tests offline lauffähig". `gen/calibration.py`
ist stdlib-only und offline-getestet. **Entscheidung:** die numpy-freie
`calibration.conformal_quantile` wurde NICHT entfernt; stattdessen bindet ein
**Äquivalenz-Pin-Test** (`test_split_conformal_equivalence_pin`, 2000 Fälle, |Δ|≤1e-12)
`calibration.conformal_quantile == trustcore_adapter.split_conformal_threshold`. Damit gibt
es effektiv EIN Verhalten (kein unkontrolliertes Duplikat), ohne offline-core zu brechen.
Falls der Owner doch den vollständigen Rip-out (calibration delegiert hart an trust-core,
conformal-Tests werden `verify`-gated) bevorzugt, ist das ein kleiner Folge-Commit.

## Verifikation (Zahlen)

- Neue Tests: 7/7 grün; `calibration`-Tests unverändert grün (Äquivalenz-Pin inklusive).
- **Volle Suite: 842 passed, 19 skipped, 0 Fehler** (~18.8s). Die 19 Skips = optionale
  cad/web/postgres-Tests (Extras in dieser Env nicht installiert) — keine Regression.
- `ruff check` der neuen Dateien: All checks passed.

## Nicht erledigt / deferred

- DriftMonitor-Verdrahtung in die Lauf-Komposition (Audit 2026-07-04, **owner-gated**):
  Drift bleibt Monitoring-Signal, NIE Phasen-Gate (Gates sind deterministisch + LLM-frei;
  die Lauf-Ebene existiert bereits als `gen.integration.drift.detect_run_drift`). Ein
  ehrlicher Hook in `audited_run` ist offline nicht beweisbar: (i) kein Cross-Run-
  Baseline-Store (CCDD braucht ≥100 Output-Embeddings aus ECHTEN früheren Läufen),
  (ii) Produktions-Embedder = live Ollama (`gen.memory.ollama_embedder`; Toy-Embedder
  sähe semantischen Drift nicht → Fake-Coverage), (iii) das echte trust-core ist die
  private companion-Library — **das PyPI-Paket `trust-core` 0.1.0 ist ein namensgleiches
  Fremdpaket** (engine/keys/proof/wire, ohne conformal/receipts). Der Namesake machte
  aus `pytest.importorskip("trust_core")` 5 Collection-ERRORS statt Skips → Guards jetzt
  gepunktet (`trust_core.conformal.ccdd` / `.conformal.split`+`.math.fdr` /
  `.receipts.keystore`), Fehlermeldungen der drei Import-Seams warnen vor dem Namesake
  (Beweis: `tests/test_verify_extra_seam.py`, läuft in JEDER Env via sys.modules-Stand-ins).
- Optional: harter conformal-Rip-out (s. o.) nach Owner-Entscheid.
- Live-Token-/Zeit-Messung (Phase-2/3-Live-Läufe).
