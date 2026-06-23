# Depth-Audit: `src/gen/discovery/assumption_annihilator.py`

**Verdikt: REAL.** Keine Quell-Änderung nötig — alle drei δ-Verdikte sind echt erreichbar
und werden vom tatsächlichen Fit-Verbesserungswert unter der δ-Asymmetrie getrieben, nicht
von konstanten Strings.

## Was geprüft wurde
`annihilate_constant(problem, constant_name, per_sample_values, …)` hebt eine gehaltene
Konstante zur freien **Variable** an und re-derived das Gesetz (Law Rebuilder): die promotete
Größe wird mit ihren `per_sample_values` als zusätzlicher `Variable`-Input in ein neues
`DiscoveryProblem` gehängt, die Konstante entfernt, und `discover_new_formulas` läuft erneut.

## Beweis, dass es kein Facade ist (Charakterisierungstest)
`tests/test_assumption_annihilator_characterization.py` konstruiert das dimensional saubere
Gesetz `y[m] = C · x[s] · k[m/s]` und steuert den Eingang so, dass jeder Pfad real feuert
(R²-Werte gegen die echte Engine offline gemessen):

| Fall | Konstrukt | base_r2 | rebuilt_r2 | improvement | required | Verdikt |
|------|-----------|---------|-----------|-------------|----------|---------|
| (a) | `k` variiert echt pro Sample (`[2,5,3,7,4]`) → versteckte Abhängigkeit | ≈0.687 | 1.0 | ≈0.313 ≥ 0.05 | 0.05 | **promoted** |
| (b) | `k` wirklich konstant (`[3,3,3,3,3]`) | 1.0 | 1.0 | 0.0 ≤ 0.01 | 0.05 | **assumption_held** |
| (c) | nur letztes Sample weicht ab (`[3,3,3,3,3.5]`) | ≈0.973 | 1.0 | ≈0.027 | 0.05 | **insufficient_evidence** |

Damit ist bewiesen:
- der Input wird **wirklich konsumiert** — verschiedene `per_sample_values` ändern
  `rebuilt_r2` und damit das Verdikt meaningfully;
- die **ehrliche Abstention** (`insufficient_evidence`) feuert bei marginaler Verbesserung
  über `improvement_margin` aber unter der δ-gehobenen Schranke;
- `improvement == rebuilt_r2 - base_r2` und
  `required_improvement == improvement_margin + PROMOTION_DELTA·DELTA_MARGIN_SCALE`
  (= 0.01 + 0.8·0.05 = 0.05) gelten exakt — als Beispiel **und** als Property-Test über
  zufällige positive Daten und variables `improvement_margin`.

## Fail-loud-Wächter (Negativtests, grün)
- unbekannter `constant_name` → `ValueError("… is not a constant …")`;
- `per_sample_values`-Längen-Mismatch → `ValueError("… one entry per data point")`.

## Branch-Erreichbarkeit (L3 Vollständigkeit / L4 Realisierbarkeit)
Alle drei Verdikt-Zweige sind erreichbar (siehe Tabelle). Die δ-Asymmetrie ist korrekt:
ein marginaler Gewinn wird nie zur Falsch-Entdeckung — `promoted` verlangt zusätzlich
`rebuilt_best.candidate.dimension_ok`. Kein toter Code, keine stillen Defaults: jede
faktische Größe wird berechnet, fehlende/inkonsistente Eingaben werfen laut.

## 4-Linsen
- **L1 Wahrheit:** R²-Werte gegen die echte deterministische Engine gemessen, nicht geraten.
- **L2 Drift:** Docstring deckt sich mit Verhalten (δ-gehobene Schranke, ValueErrors); keine Anpassung nötig.
- **L3 Naht:** Wiederverwendet `discover_new_formulas` + die Engine-Gates — der Rebuild wird
  von derselben Maschinerie wie jede andere Entdeckung beurteilt.
- **L4 Realisierbarkeit:** Offline, deterministisch, numpy-only; alle Pfade testgedeckt.

**Quelldatei unverändert.** Nur Test + dieses Audit-Dokument hinzugefügt.
