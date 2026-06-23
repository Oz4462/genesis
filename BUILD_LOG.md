# BUILD_LOG

## 2026-06-23 — T01 Depth-Audit + Härtung `discovery/multiterm.py`

**Verdict: REAL.** Neuer Charakterisierungs-Test `tests/test_multiterm_characterization.py` (29 Fälle,
3 Hypothesis-Property-Tests) beweist, dass Greedy-Selektion + lineare lstsq + Pruning + Held-out-Scoring
wirklich berechnet werden (Output folgt dem Input; gemeldetes R²/RMSE == unabhängig nachgerechnet;
Linearität Ziel×k ⇒ Koeffizient×k).

**Defekt gefunden + behoben:** `discover_multiterm(max_terms<1)` gab still ein erfundenes 1-Term-Gesetz
zurück (Greedy-Schleife läuft nie → `not selected`-Fallback griff fälschlich). Guard
`if max_terms < 1: raise ValueError` ergänzt (fail-loud, „keine stillen Defaults") + Regressionstest.
Greedy-Nicht-Global-Optimalität ist eine dokumentierte ehrliche Grenze, kein Bug — out-of-sample gefangen.

Bestehende `tests/test_discovery_multiterm.py` weiter grün (14/14). Details: `docs/audit/DEPTH_AUDIT_multiterm.md`.
4 Linsen angewendet (L1 Wahrheit / L2 Drift / L3 Naht / L4 Realisierbarkeit).

## T03 — Depth-audit + harden `reality_fork.py` (counterfactual physics sandbox)

**Verdikt: REAL** (ein ehrlichkeits-relevanter Defekt behoben).

- Neuer Charakterisierungs-Test `tests/test_reality_fork_characterization.py` (14 Tests, 3
  property-based via Hypothesis): beweist, dass Dimensions-Fork = Gauß'sches Gesetz
  `F ∝ r^(-(D-1))` und Konstanten-Fork = Potenzgesetz `(new/base)^exp` **berechnet** werden
  (Output ändert sich mit dem Input, keine kanned strings), und dass die Ehrlichkeits-
  Invarianten halten (Basis D=3 → `counterfactual=False`, alle anderen `True`, kein Fork
  trägt `bestaetigt`).
- **Defekt gefunden+behoben** in `src/gen/discovery/reality_fork.py`: `fork_constant` ließ
  NaN/inf-Magnituden durch den `<= 0.0`-Guard schlüpfen (NaN-Vergleiche sind immer `False`)
  und stempelte einen nicht-finiten Skalenfaktor `internally_consistent=True` — ein stiller
  nicht-finiter „Fakt", der dem Finite-Power-Law-Vertrag widerspricht (Kernprinzip 4). Fix:
  Finitheits-Guard für base/new/exponent + Overflow-Guard auf den Faktor → ehrliche
  Abstention (`internally_consistent=False`, kein `target_scale_factor`).
- **Runde 2 (Review-Finding `rubberduck`):** CPython wirft beim Potenz-Overflow
  `OverflowError` (kein `inf`), z.B. `base=1, new=1e10, exp=40` → `1e400`; der reine
  `isfinite`-Guard ließ die Exception ungefangen entkommen → Absturz statt Flag. Fix: Potenz
  in `try/except OverflowError` gekapselt, beide Überlauf-Pfade → flagged-inconsistent. Neuer
  Regressionstest `test_power_overflow_is_flagged_not_crashed`.
- **Runde 3 (Review-Finding `rubberduck`):** zweiter Crash-Pfad — Verhältnis `new/base`
  unterläuft nach `0.0` (z.B. `1e-300/1e300`) + negativer Exponent → `ZeroDivisionError`
  (nicht `OverflowError`), entkam dem alleinigen `except OverflowError`. Fix:
  `except (OverflowError, ZeroDivisionError)`. Neuer Regressionstest
  `test_ratio_underflow_with_negative_exponent_is_flagged_not_crashed`.
- Öffentliche Signaturen unverändert; bestehende `tests/test_discovery_reality_fork.py` grün.
- 4 Linsen: L1 (Math gegen Gauß/Potenzgesetz verifiziert), L2 (Counterfactual-/`bestaetigt`-
  Invarianten getestet), L3 (Signaturen stabil, keine Downstream-Brüche), L4 (stiller
  nicht-finiter Defekt + Overflow-Crash beseitigt).
- **21 Tests grün** (16 neu + 5 bestehend). Details: `docs/audit/DEPTH_AUDIT_reality_fork.md`.
