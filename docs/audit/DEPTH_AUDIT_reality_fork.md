# Depth-Audit: `reality_fork.py` (Reality Fork Simulator, build 4.2)

**Verdikt: REAL** (mit einem behobenen ehrlichkeits-relevanten Defekt).

## Was geprüft wurde
Tiefenprüfung gegen die Facade-Frage „Rechnet das Modul die Gesetze wirklich aus, oder
liefert es kanned strings?". Neuer Test: `tests/test_reality_fork_characterization.py`
(14 Tests, davon 3 property-based via Hypothesis). Bestehende
`tests/test_discovery_reality_fork.py` bleibt grün.

## Belege, dass es echt ist (L1 Wahrheit)
- **Räumliche-Dimension-Fork = Gauß'sches Gesetz, nicht kanned.** `gauss_force_exponent(D)`
  liefert für jede ganzzahlige D≥1 exakt `-(D-1)` (property-based über D∈[1,200] verifiziert).
  Verschiedene D ergeben verschiedene Exponenten **und** verschiedene `forked_law`-Strings
  (D=2→r^-1, 3→r^-2, 4→r^-3, …, alle fünf unterschiedlich) — eine Fassade würde ein festes
  Gesetz zurückgeben. Das Quantity-Label (`E`/`F`) wird in den String eingefädelt → gebaut,
  nicht hartkodiert.
- **Konstanten-Fork = Potenzgesetz-Skalierung, nicht kanned.** `target_scale_factor` ist
  exakt `(new/base)^exp`; ändert man `new_value` oder kippt das Vorzeichen des Exponenten,
  bewegt sich der Faktor entsprechend (Reziprozitäts-Identität property-based bestätigt).

## Ehrlichkeits-Invarianten (L2 Drift)
- Genau die Basis-Dimension (Default D=3) ist `counterfactual=False`; jeder andere Fork ist
  `counterfactual=True`. Bei eigener `base_dimension` wandert das „reale"-Label mit, und der
  dokumentierte Selbst-Check warnt, wenn die Basis nicht r^-2 reproduziert.
- **Kein Fork trägt je `bestaetigt`.** Strukturell kein `verdict`/`passed`/`bestaetigt`-Feld;
  der String taucht in keinem Textinhalt auf. Die Real-Daten-Gate-Autorität wird nie geborgt.

## Gefundener + behobener Defekt (L4 Realisierbarkeit / „keine stillen Defaults")
`fork_constant` definiert eine konsistente Welt laut Modul-Docstring als *finites*,
positiv-magnitudiges Potenzgesetz. Der bisherige Guard prüfte nur `<= 0.0`. Da
NaN-Vergleiche immer `False` sind, **schlüpften NaN/inf-Magnituden durch** und erzeugten
einen nicht-finiten `target_scale_factor`, der mit `internally_consistent=True` gestempelt
wurde — ein stiller nicht-finiter „Fakt", der dem Finitheits-Vertrag und Kernprinzip 4
widerspricht. Beweis vor dem Fix: `inf new → consistent=True, factor=inf`;
`nan base → consistent=True, factor=nan`.

**Fix:** expliziter Finitheits-Guard für `base_value`, `new_value` und `scaling_exponent`
vor der Positivitäts-Prüfung, plus ein Overflow-Guard auf den berechneten Faktor (finite
Eingaben können nach `inf` überlaufen). Nicht-finite Fälle werden jetzt
`internally_consistent=False` ohne `target_scale_factor` zurückgegeben (ehrliche Abstention).

## L3 Vollständigkeit / Naht
Öffentliche Signaturen (`CounterfactualWorld`, beide Fork-Funktionen, `gauss_force_exponent`,
`fork_from_discovery`) unverändert → keine Downstream-Brüche. Bestehende Tests bleiben grün.

## Ergebnis
19 Tests grün (14 neu + 5 bestehend). Defekt behoben; sonst keine Änderung nötig
(„change nothing if correct").
