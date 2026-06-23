# Depth-Audit: `src/gen/discovery/srbench_hygiene.py` (SRBench hygiene gate)

**Task:** T02 — symbolic-regression benchmark hygiene (leakage prevention, OOS, deterministic splits, dummy soundness, fair scoring)
**Verdict: REAL** (targeted extension + one bugfix for the headline claim to be self-verifiable)

## Was geprüft wurde

Neuer Charakterisierungs-Test `tests/discovery/test_srbench_hygiene_characterization.py` (13 Tests, davon mehrere via Hypothesis @given; alte `test_discovery_srbench_hygiene.py` untouched und grün).

| Anspruch (headline) | Beweis im Test | Ergebnis |
|---|---|---|
| **Leakage prevention** (train/test overlap metric) | `check_train_test_overlap` + `assert_no_split_leakage` auf deliberate-overlap Indizes (2 shared rows) → >0 + exakter ValueError; clean Indizes → 0 + no-raise. Property-Test auf allen Zufallspaaren. | REAL |
| **OOS auf truly held-out (kein Leak)** | Für Kepler: `split_overlap == 0`; exakte Replikation des Splits + Fit NUR auf train + Anwendung der train-coeff+exponents auf test_rows → recomputed R² exakt == `report.oos_test_r2` (math.isclose) | REAL |
| **Dummy + Generalises + Gate** | Kepler clean → passed, dummy_excluded, oos>0.99, overlap=0; pure-noise Target → not passed + generalises=False (split immer 0) | REAL |
| **Negative / documented errors** | n<4 → ValueError mit exaktem Message "need at least 4 data points..." (kein silent) | REAL |
| **Determinismus (A5)** | gleiches Problem + Seed → identischer Report (passed, oos, overlap) | REAL |

**Property-Invarianten (Hypothesis):**
- Interner OOS-Split immer overlap==0 für n>=5, beliebige Seeds.
- `check_train_test_overlap` == exakte Set-Intersection (symmetrisch, >=0) für alle Index-Listen.

## Gefundener + behobener Defekt (L2 / seed + L4 leakage headline)

1. `hygiene_gate(..., seed=42)` übergab seed an dummy + noise_sweep, aber NICHT an `out_of_sample_validate` → OOS-Teil lief immer mit seed=0. Verletzte die "deterministic splits" + Reproduzierbarkeit (A5) für den Gate als Ganzes. Fix: `out_of_sample_validate(problem, seed=seed)`.
2. Headline-Claim "train/test leakage prevention ..." war nicht durch die API des Moduls selbst nachweisbar (keine Leakage-Metrik, keine Checker-Funktion; nur Delegation). Hätte ein Hohl-Facade für den "leakage prevention"-Teil des SR-Benchmark-Hygiene-Anspruchs sein können. Fix: `check_train_test_overlap` + `assert_no_split_leakage` (fail-loud) + `HygieneReport.split_overlap` (immer 0 im Gate) + Berechnung+Reporting des Overlaps im Gate (Replikation der Split-Logik, dokumentiert warum).

Beide Änderungen minimal; bestehendes Verhalten auf Default-Pfaden unverändert.

## Bewusst NICHT geändert

- Keine Änderung an `validation.py` / `engine.py` (Scope + Isolation).
- Keine blanket NaN/Inf-Guards (keine echten stillen Falschwerte durch sie ausgelöst; positive-Magnitude-Guard liegt im Engine).
- Keine Erweiterung der public Signaturen von `hygiene_gate` (nur interne Fix + additive API für Leakage-Checker).
- Alte Test-Datei nicht angerührt (neue _characterization ist die autoritative).

## 4 Linsen (angewendet nach der Arbeitseinheit)

- **L1 Wahrheit:** Alle Claims (dummy=0 für alien dim, OOS-R² auf held-out, overlap==0, Noise reject) mit Source (kepler, recompute, set-intersect) + Test verifiziert. Keine unausgewiesenen Fakten.
- **L2 Drift:** Seed-Forwarding-Bug (silent inconsistency) entdeckt + geschlossen; Leakage-Headline jetzt durch eigenes Modul beweisbar (kein Drift Doc vs. Code).
- **L3 Vollständigkeit/Naht:** Neuer Test + alte Tests grün; Naht zu validation/engine über öffentliche API (kein Mock); Error-Pfade dokumentiert; Scope strikt eingehalten (keine anderen Dateien).
- **L4 Realisierbarkeit:** Tests (inkl. Hypothesis + Negativ + recompute-Proof) grün; minimaler Fix; Gate-Verhalten erhalten; 4_Linsen + BUILD_LOG-Eintrag; pytest-Gate gesamt grün.

## Akzeptanz

- Interface + Typen: erweitert (Sequence, HygieneReport.split_overlap) + annotiert.
- Tests: 13 neu (grün) + 5 alt (grün), mind. 1 Negativ + Properties.
- Ledger: n/a (kein faktischer Claim ohne Quelle im Code; HygieneReport ist strukturell).
- Gate: n/a (kein Phasen-Gate; Hygiene ist Benchmark-Hilfe).
- Doku: Modul-Docstring + Funktions-Docs aktualisiert; eigenes `docs/audit/srbench_hygiene.md`; BUILD_LOG Zeile.
- 4 Linsen vollständig dokumentiert.

**Status:** Task T02 abgeschlossen, keine Kollision mit anderen Worktrees (eigener Pfad srbench_hygiene + neuer Test + eigenes Audit-Doc).