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

## T04 — Depth-audit + harden `separability.py` (additive/multiplicative separability)

**Verdict: REAL** — `analyze_separability` genuinely evaluates the mixed second difference
`y(++) − y(+−) − y(−+) + y(−−)` (and its `log y` form for multiplicative mode); the grouping is
computed from the per-pair residual, not canned.

- **Added** `tests/test_separability_characterization.py`: facade-killer proving (a) the grouping/
  `max_interaction` changes meaningfully when the function's coupling changes (additive→singletons,
  product→one group, partial `a·b+c` isolates `{a,b}` from `{c}`, magnitude scales with coupling
  strength), (b) the log path genuinely flips `a*b`'s verdict between modes (anchored to a hand-computed
  log corner sum), and (c) every documented guard raises. Includes Hypothesis property tests sweeping the
  coefficient/exponent space.
- **Fixed** `src/gen/discovery/separability.py`: two confirmed silent-wrong-value defects (no-silent-
  defaults). `n_bases < 1` skipped the sampling loop → fabricated "fully separable" (a coupled `a*b` read
  as separable); `tol < 0` → fabricated "all coupled" (a pure sum read as coupled). Both now raise
  `ValueError`; docstring updated. The only repo caller uses defaults, so legacy paths are unchanged.
- **Tests:** `tests/test_separability_characterization.py` + legacy `test_separability.py` +
  `test_engine_separability_annotation.py` → 28 passed. `test_discovery_engine.py` → 6 passed.
- Full audit + 4 Linsen in `docs/audit/DEPTH_AUDIT_separability.md`.

## 2026-06-23 — T05 Depth-Audit + Härtung `discovery/simulated_data.py`

Verdikt **REAL**: `problem_from_simulation`/`discover_from_simulation` sampeln echt eine geschlossene
Form, generieren die Zieldaten selbst und gewinnen das Gesetz dimensional zurück (kein Stub).
Neue Charakterisierungssuite `tests/test_simulated_data_characterization.py` (21 Tests, inkl.
2 Hypothesis-Property-Tests: Potenzgesetz-Recovery für eine Familie + `baked`-Round-Trip-Identität;
Negativ-Kontrolle additive Form; alle dokumentierten Guards).

**Gefundener + behobener Defekt (L2):** Namens-Kollision (zwei Eingaben gleichen Namens, oder
Eingabe == Konstante) kollabierte still auf eine Spalte und korrumpierte den dimensionalen Solve.
Minimaler Eindeutigkeits-Guard in `problem_from_simulation` → lautes `ValueError` („keine stillen
Defaults"). Öffentliche Signaturen + Sampling unverändert; vorbestehende Tests grün (27 passed).
Details: `docs/audit/DEPTH_AUDIT_simulated_data.md`.

---

## 2026-06-23 — Depth-Audit + Fix: `discovery/symbiosis.py` (Grok Cross-Model-Symbiose) [T04]

**Verdikt: REAL (nach gezielter Ergänzung).** Die bestehenden `symbiosis_discover`/`council_discover`
nutzten als Verifikator den deterministischen Gate (echt, aber nicht die *wörtliche*
Modell-gegen-Modell-Drift-Prüfung aus CLAUDE.md §3). Neu: `cross_model_drift_check(...) -> DriftReport`
lässt ein **zweites, anders-familiges** Modell (dependency-injizierter `LLMClient`, offline via
`ScriptedLLM`) dieselbe Frage unabhängig beantworten. `verified=True` nur bei echter
Cross-Model-Korroboration; Widerspruch ⇒ `drift` (kein stiller Pass); Verifikator-Fehler/Timeout ⇒
ehrliche `abstention`; gleiche Familie ⇒ `ModelConflictError` (Selbstcheck verweigert). 6 neue Tests
inkl. zwei Negativtests + ein Hypothesis-Property (falsches Zweiturteil kann nie fälschlich
verifizieren), alle offline grün. 4 Linsen + Details: `docs/audit/symbiosis.md`.
