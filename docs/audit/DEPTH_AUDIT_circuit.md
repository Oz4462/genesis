# Depth-Audit: `src/gen/circuit.py`

**Verdikt: REAL** — keine Quelländerung nötig (`change nothing if correct`).

## Auftrag
Tiefenprüfung des reinen-numpy MNA-Lösers (DC / AC / Transient / nichtlinear) gegen
geschlossene Formen, um zu beweisen, dass die Zahlen **berechnet** und nicht **gecanned**
sind, plus mindestens ein Negativtest pro dokumentiertem Fail-Loud-Pfad.

## Was geprüft wurde (`tests/test_circuit_characterization.py`, 15 Tests, alle grün)

### Headline-Zahlen sind echt berechnet (Input wird konsumiert)
- **Ohm (1 Widerstand):** `solve_dc` → Quellstrom `I = V/R`, Knotenspannung `= V`.
  Zusatz: Halbierung von `R` verdoppelt den Strom (`100 Ω → 0.1 A`, `50 Ω → 0.2 A`) —
  beweist, dass `R` tatsächlich konsumiert wird, nicht konstant ist.
- **Spannungsteiler (2 Widerstände):** analytischer Mittelknoten `V·R2/(R1+R2)`;
  Änderung von `R2` (1 kΩ → 8 kΩ) bewegt den Mittelknoten (4.5 V → 8.0 V).
  Zusätzlich **Property-Test (Hypothesis)**: Invariante `V_mid = Vin·R2/(R1+R2)`
  für alle positiven `R1, R2` und `Vin ∈ [−50, 50]`.
- **Transient (RK/Backward-Euler RC):** `solve_transient` konvergiert über 20·τ gegen
  den von `solve_dc` unabhängig berechneten DC-Endwert; der Endwert folgt der
  Quellspannung (3.0 V → 3.0 V, 7.5 V → 7.5 V) → Input konsumiert.
- **AC (komplexes MNA):** `solve_ac` liefert für RC-Tiefpass bei `ω = 2/RC` die exakte
  reaktive Phasor-Magnitude `1/√(1+(ωRC)²) = 1/√5`; höheres `ω` dämpft stärker → `ω` wird
  konsumiert.

### Negativtests (dokumentierte Fail-Loud-/Abstentions-Pfade feuern)
- `Resistor.ohms ≤ 0` / `Capacitor.farads ≤ 0` / `Inductor.henries ≤ 0` /
  `Diode.i_sat ≤ 0` → **`ValueError`** (via `_validate_components`).
- Schwebendes/singuläres Netz (Widerstand zwischen zwei Knoten ohne DC-Pfad zur Masse)
  → **`numpy.linalg.LinAlgError`** (kein geratener Wert).
- Bewusst nicht-konvergente nichtlineare Newton-Iteration (`max_iter=1` bei
  vorwärts-gepoltem Diode) → **`RuntimeError`** (nie ein still falscher Arbeitspunkt).

## 4-Linsen
- **L1 Wahrheit:** Alle Headline-Werte gegen geschlossene Formen (Ohm, Teiler, RC-Tiefpass
  `1/√(1+(ωRC)²)`, RC-Steady-State) verifiziert — exakt, nicht gecanned.
- **L2 Drift:** Docstrings entsprechen dem Verhalten; die versprochenen Exceptions
  (`ValueError`, `LinAlgError`, `RuntimeError`) feuern wie dokumentiert.
- **L3 Vollständigkeit/Naht:** Alle vier öffentlichen Löser (`solve_dc`,
  `solve_transient`, `solve_ac`, `solve_dc_nonlinear`) plus alle Bauteiltypen abgedeckt;
  neuer Test trägt das `_characterization`-Suffix und lässt `tests/test_circuit.py`
  unberührt (kein Churn).
- **L4 Realisierbarkeit:** rein numpy/stdlib, offline, deterministisch, keine neue
  Abhängigkeit (`hypothesis` ist bereits deklarierte Test-Dep).

## Befund
`circuit.py` ist ein echter MNA-Löser: jede geprüfte Größe ist eine korrekte Funktion
der Eingabe-Bauteile, und jeder dokumentierte Guard ist real. **Keine Fassade,
kein stiller Default — Quelle unverändert.**
