# Depth-Audit: `src/gen/refinement.py` (verify→refine bounded loop)

**Datum:** 2026-06-24
**Aufgabe:** T05 — Tiefen-Audit des Verify→Refine-Controllers.
**Verdikt:** **REAL** — keine Quelländerung nötig ("change nothing if correct").
**Test:** `tests/test_refinement_characterization.py` (12 Tests, davon 2 Negativtests +
2 Hypothesis-Properties) — alle grün, offline, ohne LLM/Physik/I-O.

## Was das Modul behauptet
Ein deterministischer, **bounded** Controller um ein beliebiges Gate:
1. `directives_from_gate` übersetzt **jede** Gate-Failure in eine `RefinementDirective`
   (bekannter Code → deklariertes Template aus `DIRECTIVE_TEMPLATES`; unbekannter Code →
   generische Direktive, die das **Detail** des Gates trägt, nie ein erfundener Fix).
2. `refine_until_pass` läuft Verify→Regenerate→Verify, **honest** über das Ergebnis:
   `converged=True` nur bei echtem Gate-Pass; `stuck=True` sobald eine Failure-**Signatur**
   wiederkehrt (kein Fortschritt); sonst `converged=False` mit Residual-Failures bei
   erschöpftem Budget. Nicht-positives Budget → `ValueError`.

## Facade-Killer (warum es kein Fassaden-Stub ist)
- **(a) Output wird vom Input getrieben:** `test_outcome_changes_with_regenerator_strength`
  zeigt unter identischem Gate + Budget: starker Regenerator → `converged`, zu schwacher
  → `not converged`, mit unterschiedlicher Rundenzahl. Ein kanned "converged" könnte das
  nicht. Die Property `test_monotone_strengthener_converges_in_exactly_ceil_steps` pinnt die
  Rundenzahl auf die geschlossene Form `ceil((threshold−start)/step)` — der Controller macht
  die **minimale** Anzahl Regenerationen, nicht mehr, nicht weniger.
- **(b) Fail-loud/Abstention feuert exakt:**
  - `test_no_progress_regenerator_is_reported_stuck` — Noop-Regenerator → `stuck`, früher
    Abbruch (Budget nicht verbrannt).
  - `test_oscillating_regenerator_is_caught_as_stuck_not_run_to_budget` — A↔B-Zyklus (die
    *letzte* Signatur wiederholt sich nie) wird vom **mengen**basierten Detektor `_signature`
    + `seen` als `stuck` gefangen, nicht als erschöpftes Budget. Ein Konsekutiv-nur-Check
    würde hier das volle Budget verbrennen.
  - `test_too_slow_regenerator_exhausts_the_budget_honestly` — echter, aber zu langsamer
    Fortschritt → `converged=False`, `stuck=False`, Residual-Failures vorhanden.
  - `test_rejects_nonpositive_budget` — `max_rounds=0` → `ValueError`.
- **Direktiven-Mapping vollständig:** `test_directives_one_per_failure_mapping_known_and_unknown`
  — genau eine Direktive pro Failure, keine verschluckt; bekannte Codes → Template; unbekannter
  Code trägt das Detail und ist garantiert **kein** Template-Wert (keine Erfindung).

## 4-Linsen-Selbstkontrolle
- **L1 (Wahrheit):** Der Controller meldet nie eine nicht erreichte Konvergenz. `converged`
  setzt `result.passed and not result.failures` voraus (Zeile 135). Property
  `test_result_is_always_internally_honest` beweist die Invariante
  `converged ⇔ (keine Residuals ∧ ¬stuck)` über zufällige Welten.
- **L2 (Drift):** Signatur = `(code, claim_id, detail)` sortiert — `claim_id`/`detail`
  getrennt gehalten (keine Feld-Wert-Kollision); "gleiches Failure" heißt gleicher Code **und**
  Target **und** Grund. Ein geänderter Grund ist eine echte, verschiedene Signatur → kein
  vorzeitiges Stuck-Flag, kein verschlepptes Oszillieren.
- **L3 (Vollständigkeit/Naht):** `history` ist lückenlos ab Runde 0 (`range`-Property), eine
  Gate-Auswertung pro Runde + finale; `len(history) == rounds + 1` durchgehend asserted. Naht
  zum Gate ist über `core.interfaces.GateResult/GateFailure` (pre-existing) sauber.
- **L4 (Realisierbarkeit/Edge):** Sofort-Pass (`rounds==0`), nicht erreichbares Threshold,
  Budget-Grenze, Oszillation, Noop, ungültiges Budget — alle abgedeckt. Charakterisierungstest
  ist rein deterministisch (Level via realem `Question.run_id`), keine Abhängigkeit von δ-Physik
  oder einem Live-Modell, daher robust und kollisionsfrei zu `tests/test_refinement.py`.

## Quelländerung
**Keine.** Das Modul ist korrekt und ehrlich implementiert; der defensive `passed and not
failures`-Guard (D14) und der mengenbasierte Zyklus-Detektor sind bereits vorhanden. Nach der
Konvention "change nothing if correct" bleibt `src/gen/refinement.py` unverändert.
