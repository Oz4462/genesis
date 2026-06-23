# Depth-Audit: `src/gen/competitive_humanoid.py`

**Verdikt: REAL** (mit einer kleinen, ehrlich gefixten Naht — der Preis-Guard).

`build_humanoid` baut eine vollständige Ganzkörper-Humanoid-`Specification` aus einer
`HumanoidConfig`. Die Tiefenprüfung bestätigt: die Wettbewerbs-Kennzahlen leben **im gebauten
Spec**, nicht nur im Docstring, und jedes geprüfte cfg-Feld wird tatsächlich konsumiert.

## Was geprüft wurde (Facade-Killer)

Neuer Test: `tests/test_competitive_humanoid_characterization.py` (24 Fälle, alle grün).

### (a) Input wird konsumiert (kein Konstanten-Stub)
- **Drehmoment-Edge im Spec:** Die `actuator.available_torque`-Quantity trägt im Flaggschiff
  exakt **420 N·m**, im Printed-Spec **200 N·m** — also `420 > 360 (Unitree H2) > 200`. Die
  beanspruchte Überlegenheit ist eine reale, im Spec verankerte und zwischen den Configs
  **unterschiedliche** Zahl.
- **Jedes cfg-Lever fließt durch:** `joint_torque_nm`, `available_torque_nm`, `reach_l1/l2`,
  `compute_workload_tops`, `compute_chip_tops` ändern jeweils die korrespondierende
  measurand-getaggte Quantity im gebauten Spec (parametrisierter Test).
- **Keine toten Labels:** `available_torque_nm` treibt die abgeleitete Flansch-Reaktionskraft
  `q_mount_reaction = q_avail_tau / 0.035` und damit die Bolzen-Scherlast `q_bolt_load` — eine
  echte Downstream-Derivation (Verdopplung des Moments verdoppelt beide).
- **Property-Test (Hypothesis):** für beliebige endliche, positive `available_torque_nm`
  erscheint der Wert verbatim als `actuator.available_torque`-Quantity (exakter Pass-Through,
  nicht auf eine Konstante gerundet).
- **Neun druckbare Bauteil-Typen** mit echter CSG-Geometrie; jede bepreiste BOM-Zeile zeigt auf
  eine tatsächlich deklarierte Quantity (kein hängender Preis-Verweis), und jedes gekaufte PART
  ist bepreist.

### (b) Fail-loud / keine stillen Defaults (Negativtests)
- Fehlt im `prices`-Dict ein erforderlicher Schlüssel, schlug der Build vorher mit einem **bloßen
  `KeyError`** tief in der Quantity-/Claim-Konstruktion fehl. Das ist zwar laut, aber undiagnostisch.
- Der Negativtest fordert ein **klares, benennendes** Fehlversagen. Daher der einzige
  Quellcode-Fix (siehe unten).

## Quellcode-Änderung (minimal, nur wo der Test einen echten Defekt aufdeckte)

Hinzugefügt:
- `REQUIRED_PRICE_KEYS` — die acht Preis-Schlüssel, die Buy-List-Quantities und Cost-Out-Claims
  benötigen (`filament_eur_g, motor, chip, battery, mcu, driver, imu, harness`).
- `_require_prices(cfg)` — validiert `cfg.prices` **vor** jeder Konstruktion und wirft einen
  `ValueError`, der **alle** fehlenden Schlüssel benennt, statt einen bloßen `KeyError` tief im
  Code (oder, schlimmer, einen geratenen Default). Aufgerufen als erste Zeile von `build_humanoid`.

Begründung (Kernprinzip „Keine stillen Defaults bei faktischen Dingen"): ein Preis ist eine
faktische Behauptung über die Welt; ein fehlender Preis darf weder still gedefaulted noch in einem
nicht-benennenden Fehler versteckt werden. Die öffentliche API, alle Quantity-/BOM-/Claim-Strukturen
und die `PRINTED`/`FLAGSHIP`-Configs bleiben unverändert (der Guard ist für vollständige Preise ein
No-op). Negativ-Kontrolle: vollständige Preise bauen weiterhin ohne Ausnahme.

## 4 Linsen
- **L1 Wahrheit:** Headline-Zahlen (420 vs 360 vs 200, Reach, TOPS) sind im Spec verankert und per
  measurand prüfbar — keine reine Docstring-Behauptung.
- **L2 Drift:** Jedes geprüfte cfg-Lever wird konsumiert; kein Konstanten-Stub. `available_torque`
  propagiert nachweislich in die Bolzen-Lastpfad-Derivation.
- **L3 Vollständigkeit/Naht:** 9 Bauteil-Typen, vollständig bepreiste BOM, alle Preis-Verweise
  auflösbar. Naht „fehlender Preis → undiagnostischer KeyError" geschlossen.
- **L4 Realisierbarkeit:** Guard ist deterministisch, offline, ohne neue Dependency; bestehende
  Tests (außer den umgebungsbedingten STL/OCCT-Fällen, die auch ohne diese Änderung fehlschlagen)
  bleiben grün.

## Abgleich `GENESIS_PLATFORM_PLAN.md`
Gehört zum Humanoid-/Wettbewerbs-Arm (zwei komplette Ganzkörper-Humanoide gegen den 2026-Weltstand).
Die Tiefenprüfung belegt, dass die Wettbewerbs-Kennzahlen real cfg-getrieben und gegatet sind, nicht
fassadenhaft.

## Reststände (ehrlich, außerhalb dieses Tasks)
- `tests/test_competitive_humanoid.py::test_competitive_humanoid_is_complete_and_verified` schlägt in
  dieser Umgebung an `BundleManifest.files_complete` fehl — das hängt am OCCT/cadquery-STL-Kernel und
  ist **unabhängig** von dieser Änderung (verifiziert: schlägt auch ohne den Guard identisch fehl).
