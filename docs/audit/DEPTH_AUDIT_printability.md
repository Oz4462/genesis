# Depth-Audit: `src/gen/printability.py`

**Verdikt: REAL** — keine Quelländerung nötig ("change nothing if correct").

## Umfang
Die sieben Closed-Form-FDM-Design-Regel-Validatoren:
`bridge_span_check`, `fdm_fit_clearance_check`, `pin_diameter_check`,
`thread_size_check`, `unsupported_wall_check`, `emboss_detail_check`,
`layer_adhesion_check`.

## Methode
Neue Charakterisierungs-Suite `tests/test_printability_characterization.py`
(25 Tests, Hypothesis-property-based + Beispiel-Tests), unabhängig von der
Legacy-`tests/test_printability.py`. Pro Validator wird der Fassaden-Killer geprüft:

- **(a) Input wird wirklich konsumiert** — kein gecanntes Konstant. Belegt durch
  *meaningful-change*-Assertions: doppelter Span halbiert den `safety_factor`;
  der custom `max_span`/`min_diameter`/`z_retention` fließt nachweisbar durch;
  derselbe Wert kippt das Verdikt je nach `fit`-/`kind`-Auswahl (echter Floor,
  nicht Konstante); `allowed_stress` skaliert mit `base_strength × z_retention`.
- **(b) Fail-loud-Pfade feuern exakt** — jeder dokumentierte `ValueError` (negativer
  Span, nicht-positives Limit, unbekannter `fit`/`kind`, nicht-positiver
  Durchmesser/Breite/Strength, `z_retention` außerhalb (0,1], negativer
  Cross-Layer-Stress) wird einzeln ausgelöst.
- **(c) Abstention** — `span == 0` und `stress == 0` liefern ehrlich `inf`
  (kein Bridge / keine Last), kein erfundener Wert.

## Property-Invarianten (Hypothesis, ∀ gültige Inputs)
- `safety_factor == quantity / limit` für alle sechs Verhältnis-Checks.
- `ok ⇔ quantity ≥ limit` (Limit inklusiv).
- `thread.use_insert_or_tap == not ok` (exakte Negation, nie beides/keines).
- `layer_adhesion.allowed_stress == z_retention × base_strength`,
  `safety_factor == allowed / stress`, `ok ⇔ safety_factor ≥ 1`.

## Befund
Alle Ausgaben sind aus den Eingaben berechnet (reine Verhältnis-Closed-Forms gegen
die research-verankerten Prozessgrenzen). Keine stillen Defaults: jeder Unsinns-Input
wirft, jede echte Grenz-/Nulllage wird ehrlich behandelt. Die Schwellen-Konstanten
(10 mm Bridge, 0.2/0.1 mm Clearance, 3 mm Pin, M5 Thread, 1.0 mm Wand, 0.9/0.5 mm
Detail, 0.45 Z-Retention) sind dokumentierte, quellen-belegte Referenzwerte — keine
magischen Zahlen, sondern die eigentliche fachliche Aussage des Moduls.

**Keine Quelländerung an `printability.py`.** Legacy- (15) und neue Charakterisierungs-
Suite (25) grün.

## 4 Linsen
- **L1 Wahrheit:** Jede Zahl gegen ihre Closed-Form (`q/limit`) und gegen die
  Doku-verankerte Prozessgrenze geprüft — kein unbelegter Output.
- **L2 Drift:** Keine Drift zwischen Docstring-Versprechen und Code; jeder
  versprochene `ValueError` existiert und wird getestet.
- **L3 Vollständigkeit/Naht:** Alle 7 Funktionen + alle dokumentierten Fehlerpfade
  + Grenz-/Null-/Negativfälle abgedeckt; Naht zu `dfm.py` (0.8 vs 1.0 Wand) belegt.
- **L4 Realisierbarkeit:** Property-Tests über realistische Längenbereiche, offline,
  ohne LLM/numpy — deterministisch reproduzierbar.
