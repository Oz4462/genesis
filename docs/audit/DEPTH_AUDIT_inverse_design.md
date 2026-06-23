# Depth-Audit: `src/gen/inverse_design.py` (GATE γ⁺ — validated Pareto front)

**Verdikt: REAL.** Keine Quelländerung nötig — der Kern rechnet Zielwerte echt aus
Spec-Quantities nach, dominiert per echter strikter Pareto-Relation und gated ehrlich
(Abstention vs. harter Fehler). „change nothing if correct" angewandt: `inverse_design.py`
bleibt unverändert.

## Was geprüft wurde (Facade-Killer + Negativtests)
Neuer Test `tests/test_inverse_design_characterization.py` (10 Tests, alle grün):

1. **`objective_value` ist berechnet, nicht gecannt.** 1500 mm gegen ein Ziel in `m`
   ergibt exakt 1.5 (mm→m-Skala 1e-3); Verdopplung der Quantity verdoppelt das Ergebnis;
   eine Hypothesis-Property beweist Linearität in `value` über den gesamten Eingaberaum.
   → der Input wird konsumiert; ein Konstanten-Stub würde durchfallen.
2. **`dominates` ist eine echte strikte Relation auf gemischtem MAXIMIZE/MINIMIZE-Ziel.**
   (höhere Effizienz, geringere Masse) dominiert; die Relation ist asymmetrisch; und sie
   **kippt auf False**, sobald genau ein Score verschlechtert wird (Masse > Rivale).
   Gleichstand ist keine strikte Dominanz.
3. **Dokumentierte Guards feuern laut.** `objective_value` wirft
   `ObjectiveEvaluationError` bei dimensional unvergleichbarer Einheit (`kg` vs `m`) und
   bei fehlender `quantity_id` — nie ein stiller Wert.
4. **`gate_gamma_plus` über direkt gebauter `ParetoFront`.** Leere Front **mit** Gap =
   ehrliche Abstention → `passed=True`, keine Failures. Leere Front **ohne** Gap → hart
   `NO_PARETO_CANDIDATES`, `passed=False`.

## 4 Linsen
- **L1 Wahrheit:** Headline-Zahlen kommen aus `Quantity.value` × Einheitenskala (units.py),
  byte-genau gegen Hand-Anker (1.5, 2×, value/1000). Kein faktischer Output ohne Quell-Quantity.
- **L2 Drift:** Kein Drift zum Docstring — die versprochenen Codes (`NO_PARETO_CANDIDATES`)
  und Guards (`ObjectiveEvaluationError`) existieren und wurden exakt getriggert.
- **L3 Vollständigkeit/Naht:** Abstention (Gap) vs. harter Void getrennt geprüft; die
  Einheiten-Naht (parse_unit-Vergleich + unit_scale) ist die kritische Grenze und getestet.
- **L4 Realisierbarkeit:** Test ist deterministisch, ohne Netz/Subprozess; Property-Test
  deckt den Eingaberaum (1..1e6 mm, Faktor 0.1..10) statt nur Punktwerte.

**Abgleich GENESIS_PLATFORM_PLAN.md:** erfüllt den γ⁺-Inverse-Design-Baustein
(goal → Kandidaten → nondominierte, validierte Front, Werte aus Specs rekonstruiert) —
als echtes Gate, nicht als Favoriten-Fassade.
