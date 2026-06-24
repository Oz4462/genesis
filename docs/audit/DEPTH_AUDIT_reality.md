# Depth-Audit — `src/gen/reality.py` (GATE δ⁺ reality proof)

**Verdict: REAL.** Keine Quellcode-Änderung nötig — „change nothing if correct".

## Was das Modul behauptet (HORIZON §2B)
`evaluate_reality` vergleicht eine **reale** Messung mit einer **berechneten** Vorhersage
und entscheidet *deterministisch* `CORROBORATED` / `REFUTED` / `INCONCLUSIVE` — das Verdikt
wird nie von einem Modell behauptet, sondern hier aus den Zahlen gerechnet, mit
Dimensions-Homogenitäts-Wächter (Mars-Climate-Orbiter-Fehlerklasse). `gate_delta_plus` ist
das *ehrliche-Prozess*-Gate: es scheitert **nicht** an einer Widerlegung (ein ehrliches
„widerlegt" ist ein gültiges Ergebnis), sondern nur an *illegitimen Eingaben*.

## Facade-Killer — was der Charakterisierungstest beweist
`tests/test_reality_characterization.py` (25 Tests, alle grün, offline).

**(a) Output ist AUS DEN EINGABEN GERECHNET, nicht kanned:**
- `test_residual_tracks_the_measured_value_not_a_constant` — Sweep des Messwerts ⇒ jedes
  Residuum == echtes `|measured − predicted|`, ≥4 verschiedene Werte (kein Konstanten-Stub).
- `test_status_flips_as_tolerance_crosses_the_residual` — die Eingabe `tolerance` entscheidet
  das Verdikt; die `<=`-Grenze ist inklusiv und wird wirklich konsumiert.
- `test_unit_scale_conversion_is_real_same_length_three_units` — 1.5 m == 150 cm == 1500 mm
  korroborieren alle (Residuum ≈ 0); eine Fassade, die Rohmagnituden vergliche, würde 2 von 3
  widerlegen. Plus `…_changes_residual_when_magnitude_differs` (1600 mm → 1.6 m → REFUTED).
- `test_detail_string_reports_the_computed_numbers` — der `detail`-String ist aus den Inputs
  abgeleitet, kein festes Template.

**(b) Negativ-Batterie — jeder Abstentions-/Fail-loud-Pfad feuert exakt:**
- INCONCLUSIVE bei Dimensions-Mismatch (m vs kg), unparsbarer Einheit (`kg//m`), Einheit ohne
  SI-Skala (`widget`), fehlender retrieved-Provenance, nicht-finitem Mess- bzw. Vorhersagewert
  (Mutation an der frozen-dataclass vorbei am Ctor-Guard).
- `gate_delta_plus`: alle vier Codes einzeln (`GROUNDING_UNKNOWN_CLAIM` inkl. `claim_id`,
  `EXPERIMENT_MISMATCH`, `UNSOURCED_MEASUREMENT`, `DEAD_MEASUREMENT_SOURCE`), der saubere Pass,
  der Akkumulations-Pfad (3 Codes gleichzeitig, kein Short-Circuit) und der Schlüssel-Beweis:
  ein REFUTED-Verdikt lässt das Gate **bestehen**.

**Property-based (Hypothesis):** Residuum == Distanz und Status 1:1 zur Toleranz-Bedingung für
beliebige finite Tripel; m↔cm/mm-Skalierungs-Round-Trip korroboriert immer; Determinismus (A5).

## 4 Linsen
- **L1 Wahrheit:** Verdikt = reine Funktion der Zahlen + Einheiten-Skala; durch das
  Property-Theorem `residual == |measured − predicted|` formal gepinnt. Keine Halluzination.
- **L2 Drift:** Docstrings (CORROBORATED/REFUTED/INCONCLUSIVE, „fails only on illegitimate
  inputs") decken sich exakt mit dem Code; kein Doc-Code-Drift gefunden.
- **L3 Vollständigkeit/Naht:** Alle drei Verdikt-Zweige, alle vier Gate-Codes, die
  Defense-in-Depth-Backstops (No-Provenance/Non-finite) und der „kein Pass-Verlust bei
  Widerlegung"-Vertrag sind getestet. Naht zu `verification.units` (parse_unit/unit_scale)
  über die reale m/cm/mm/kg/widget-Skala verifiziert.
- **L4 Realisierbarkeit:** Pur, deterministisch, LLM-frei, stdlib+hypothesis; läuft offline.

## Abgleich `GENESIS_PLATFORM_PLAN.md`
Erfüllt den Reality-/Verifikations-Gate-Anker (GATE δ⁺): der ehrliche empirische Beweis als
hartes Gate, nicht als Vorschlag — Kernprinzip 1 (keine fakt. Aussage ohne Quelle) und 2
(Verifikation ist ein Gate) sind durch die Negativ-Batterie maschinell durchgesetzt.

**Ergebnis:** Modul unverändert; nur Charakterisierungstest + diese Audit-Notiz ergänzt.
