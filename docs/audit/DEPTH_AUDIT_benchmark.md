# Depth-Audit: `src/gen/discovery/benchmark.py`

**Modul:** `discovery/benchmark.py` — Rediscovery-Benchmark + Red-Team (Build-Doc Phase 4)
**Datum:** 2026-06-23
**Aufgabe:** T05 — Beweisen, dass die ~100 %-Rediscovery NICHT geleakt/geechot ist.
**Verdikt:** **REAL (ehrlich, kein Leak).** Quelltext unverändert — der Honesty-Test deckt keinen Defekt auf.

## Headline-Behauptung
`rediscovery_benchmark()` meldet `rediscovery_rate == 1.0` (4 Lehrbuch-Gesetze: Kepler III,
ideales Gasgesetz, Newton-Gravitation, Fadenpendel) und `redteam_catch_rate == 1.0`
(2 falsche Ideen korrekt verworfen).

## Die Leak-Frage (Team-Honesty-Regel 2026-06-23)
Könnte die Trefferquote daher rühren, dass dem Suchprozess die Antwort vorgegeben wird?
Geprüft an drei Stellen:

1. **`known_laws` wird der Engine NICHT gefüttert.** Die realen Fälle
   (`kepler_case`, `ideal_gas_case`, …) konstruieren `BenchmarkCase(name, problem, expected)`
   und lassen das Feld `known_laws` auf seinem Default `None`. `_run_case` ruft
   `discover_new_formulas(case.problem, known_laws=case.known_laws)` → also mit `None`.
   `known_laws` würde im Erfolgsfall nur das δ (die Evidenz-Schwelle) senken; da `None`, läuft
   jeder reale Fall mit dem vollen δ-Bar. *Bewiesen durch* `test_known_laws_is_never_fed_to_the_engine`.
2. **`expected_exponents` ist ein reiner Post-hoc-Filter.** Es taucht ausschließlich in
   `_exponents_match` auf, das NACH dem Gate-Verdikt prüft, ob die — unabhängig per
   Dimensionsanalyse gefundenen — Exponenten zur Lehrbuch-Signatur passen. Es fließt nie in
   `discover_new_formulas` ein. *Bewiesen durch* `test_engine_recovers_signature_without_being_told_it`
   (Engine findet `a^1.5·mu^-0.5` ohne jede Vorgabe) und
   `test_wrong_expected_exponents_blocks_success_proving_posthoc_check`
   (falsche `expected_exponents` ⇒ `success=False`, obwohl die Engine das korrekte Gesetz bestätigt).

## Recovery kommt aus den Daten, nicht aus den gebackenen Arrays
- **Held-out / perturbierte Daten:** Kepler aus einem DISJUNKTEN Satz Bahnradien (exakt) und aus
  einer verrauschten Stichprobe (deterministisches `default_rng(7)`, ~5e-5 rel. Streuung, innerhalb
  der 1e-3-Recompute-Toleranz) wird weiterhin rediscovered. *`test_kepler_recovered_from_held_out_sample`,
  `test_kepler_recovered_from_noisier_sample`.*
- **Property-Test (Hypothesis):** Für JEDEN Satz distinkter positiver Bahnradien wird das exakte
  Kepler-Gesetz wiedergefunden — die Headline ist eine Eigenschaft der Methode, nicht eines
  handverlesenen Arrays. *`test_property_kepler_recovered_from_any_exact_sample`.*

## Negativ-Kontrolle (Echo wäre hier sichtbar)
Kepler-Inputs mit einem GESCRAMBLETEN (umgekehrten) Ziel gepaart, `expected_exponents` korrekt
gelassen: Die dimensional bestimmten Exponenten der Engine sind weiterhin `a^1.5·mu^-0.5` (Einheiten
fixieren sie). Käme der Erfolg aus dem Echo von `expected_exponents`, MÜSSTE dieser Fall „bestehen".
Er fällt aber durch (`success=False`, Verdikt `unentschieden`), weil der Fit-Gate kollabiert —
nur die Daten entscheiden. *`test_negative_control_scrambled_target_not_rediscovered`,
`test_negative_control_engine_does_not_validate_scrambled_data`.*

## Red-Team-Ehrlichkeit
- Unmögliche Dimension (Temperatur aus Länge·Zeit) ⇒ hartes `widerlegt`.
- Versteckter additiver Term (`v = g·t + v0`) ⇒ ehrliches `unentschieden`, KEIN falsches
  `bestaetigt` (ein reines Potenzgesetz kann das additive `v0` nicht darstellen → Fit-Gate hält).
  *`test_redteam_verdicts_are_honest`.*

## 4 Linsen
- **L1 Wahrheit:** Trefferquote ist echt; aus Dimensionssolve + Daten-Fit, kein Leak — falsifizierbar
  per Negativ-Kontrolle gemacht.
- **L2 Drift:** Docstring deckt sich mit Verhalten; `known_laws`-Default `None` entspricht der Doku
  „expected rediscovery gets a low δ" (Opt-in, nicht im Benchmark genutzt). Keine Drift.
- **L3 Vollständigkeit/Naht:** Naht Benchmark→Engine geprüft (`known_laws`-Durchreichung,
  `expected_exponents` nur post-hoc). Held-out + Property decken den Eingaberaum.
- **L4 Realisierbarkeit/Edge:** verrauschte Stichprobe (Recompute-Toleranz-Grenze), gescrambelte
  Daten (Fit-Kollaps), falscher Erwartungsschlüssel (Post-hoc-Filter) als Negativtests abgedeckt.

## Ergebnis
Keine Quelltextänderung nötig. `tests/test_benchmark_characterization.py` (10 Tests, inkl.
Property-Test) macht die ~100 %-Behauptung ehrlich und falsifizierbar.
