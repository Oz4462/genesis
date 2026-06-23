# Depth-Audit: `src/gen/montecarlo.py` (JCGM 101 Monte-Carlo Unsicherheit)

**Verdikt: REAL** — die Engine führt eine echte, geseedete JCGM-101-Simulation aus.
Drei stille Eingabe-Domänen-Lücken wurden gefunden und mit minimalen `ValueError`-
Guards geschlossen (keine stillen Defaults, CLAUDE.md §"keine stillen Defaults").

## Geprüfte Headline-Behauptung (falsifizierbar gemacht)

`tests/test_montecarlo_depth.py` pinnt den Output gegen analytische Grundwahrheit —
würde der Funktionsrumpf durch eine Konstante ersetzt, scheitert jeder Cross-Check:

| Eigenschaft | Test | Erwartung (geschlossene Form) |
|---|---|---|
| Linear == GUM 1. Ordnung | `test_linear_model_matches_first_order_gum` | std(`a+b`) = √(u_a²+u_b²) |
| 95 %-Intervall symmetrisch | `test_linear_interval_is_symmetric_1_96_sigma` | Halbweite ≈ 1.96·std, lo-Halbweite ≈ hi-Halbweite |
| **Nicht-linearer Mean-Shift** | `test_nonlinear_mean_shift_x_squared` | E[x²] = u² > 0 (lineares GUM sähe 0); std(x²)=u²·√2 |
| Shift skaliert mit u | `test_nonlinear_shift_scales_with_input_uncertainty` | u→2u ⇒ Mean-Shift ×4 |
| Determinismus | `test_determinism_same_seed_byte_identical` | gleicher seed ⇒ byte-identische {mean,std,lo,hi} |
| Seed wirkt | `test_different_seed_changes_interval` | anderer seed ⇒ anderes Intervall |
| **Korrelation ρ=+1 (Summe)** | `test_correlation_plus_one_addition_adds_linearly` | std ≈ u_a+u_b > √(u_a²+u_b²) |
| **Korrelation ρ=+1 (Differenz)** | `test_correlation_plus_one_subtraction_cancels` | std ≈ \|u_a−u_b\| |
| Unkorreliert = Quadratur | `test_correlation_independent_recovers_quadrature` | std = √(u_a²+u_b²) |
| Property (Invariante) | `test_property_linear_std_is_quadrature` | ∀(u_a,u_b,seed): lineare std = Quadratur ±MC-Fehler |
| Property (Korrelation) | `test_property_fully_correlated_addition_exceeds_quadrature` | ρ=+1-Summe ≥ Quadratur |

Der nicht-lineare Mean-Shift (E[x²]=u² statt 0) beweist, dass jede Stichprobe
genuin durch das Modell gedrückt wird — das ist der USP gegenüber dem linearen GUM.

## Was real gemacht wurde (Source-Edit)

Vorher schlüpften drei fehlerhafte Eingaben **still** durch:

1. `n_samples < 2` → `np.std(ddof=1)` teilt durch 0 → stilles `NaN` (nur RuntimeWarning).
2. negative Unsicherheit in `montecarlo_uncertainty` → fiel in den `u > 0 → sonst Konstante`-
   Zweig und wurde **still als Konstante** behandelt (Unsicherheit verschwand).
3. `coverage ∉ (0,1)` → `coverage=0` ergab ein Null-Breite-Intervall still; `coverage>1`
   warf inkonsistent erst tief in `np.quantile`.

Fix: ein geteilter Guard `_validate_mc_inputs(...)` (Typ-Hints + Docstring mit
Fehlerfällen) am Eingang **beider** Funktionen, der genau diese drei Fälle laut
mit `ValueError` ablehnt. Negativtests: `test_guard_coverage_out_of_range`,
`test_guard_n_samples_too_small`, `test_guard_negative_uncertainty[_correlated]`,
`test_guards_apply_to_correlated_too`.

Die numerische Kern-Logik (Sampling, Vektor-Evaluierung, Quantile) blieb
unverändert — "change nothing if correct".

## 4 Linsen

- **L1 Wahrheit:** Jede Zahl ist gegen eine geschlossene Form geankert (Quadratur,
  E[x²]=u², ρ-Add/Sub, std(x²)=u²√2), nicht gegen sich selbst. MC-Fehler explizit
  über N=200k klein gehalten (~0.16 % rel.) — Toleranzen 2–3 % sind sicher darüber.
- **L2 Drift:** Der Docstring versprach Determinismus und Korrelations-Verhalten;
  die Tests pinnen beides exakt. Der negative-`u`-Drift (still verschluckt) ist
  geschlossen — Doc und Code stimmen jetzt überein.
- **L3 Vollständigkeit/Naht:** Guards gelten an **beiden** Eingängen (uncertainty
  + correlated). Naht zu `evaluate_formula` (vektorisierter `+ - * /`-Pfad sowie
  per-sample-Fallback für min/max) wird durch `a+b`, `a-b`, `x*x` real durchlaufen.
- **L4 Realisierbarkeit:** Reine numpy/stdlib, offline, kein LLM, keine neue Dep
  (`hypothesis` ist deklariert). Volle Laufzeit ~57 s für 21 Tests — akzeptabel,
  Property-Tests auf 25 Beispiele und 80k Samples gedeckelt.

## Abgleich GENESIS_PLATFORM_PLAN
Stärkt die ehrliche Unsicherheits-/CAE-Säule: MC liefert genau dort Wert, wo das
lineare GUM lügt (Nicht-Linearität, Korrelation), und verweigert jetzt laut bei
unsinnigen Eingaben statt einen geratenen Wert zu liefern.
