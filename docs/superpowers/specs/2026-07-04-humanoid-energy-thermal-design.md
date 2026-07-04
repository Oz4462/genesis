# Humanoid Teilprojekt 1: Energie & Thermik — Design

**Datum:** 2026-07-04 · **Autor:** Claude (Orchestrator) · **Auftrag:** Ozan
**Status:** Approved (Ansatz A, Ozan 2026-07-04)

## Problem

Der Genesis-Humanoid (`src/gen/competitive_humanoid.py`) ist strukturell, kinematisch
und rechenseitig verifiziert — aber energetisch und thermisch blind:

- Der Akku (2.1 / 2.6 kWh) ist nur BOM-Posten + Preis-Claim. Kapazität ist keine
  geprüfte `Quantity`; es gibt keine Laufzeit-Anforderung und keinen Endurance-Check.
- Es existiert kein Modell der Lokomotions-Leistung (Gelenk-Drehmoment × Drehzahl ×
  Duty), obwohl alle Eingangsgrößen in der Config vorhanden sind.
- Motor-Verlustleistung und Wicklungstemperatur sind unmodelliert; `overtemperature_check`
  (thermal.py:119) existiert, feuert aber auf keiner Humanoiden-Quantity.
- `battery_endurance_check` (flight.py:141) existiert, ist generisch (Kapazität,
  Leistung, geforderte Zeit), wird aber nur von Flug-Specs getriggert.

Ein Humanoid, der nach 20 Minuten leer ist oder dessen Motoren überhitzen, gilt
heute als `physics_verified`. Das verletzt den Genesis-Ehrlichkeitsanspruch.

## Ansatz (A — Derived Quantities + vorhandene Validatoren)

Kein neuer Physik-Code. Die Energie-Kette wird als abgeleitete Quantities mit
Formeln ausgedrückt (das ε/δ-Gate rechnet Formeln deterministisch und dimensional
nach), und die zwei existierenden Validatoren werden über neue `CheckRecipe`s
mit Robot-Measurands verdrahtet.

### 1. Neue `HumanoidConfig`-Felder (alle grounded über Claims)

| Feld | Einheit | Bedeutung |
|---|---|---|
| `battery_capacity_wh` | Wh | nutzbare Nennkapazität des Packs (passend zum BOM-Namen) |
| `required_endurance_min` | min | geforderte Dauerbetriebszeit (Benchmark-relevant) |
| `locomotion_duty` | 1 | RMS-Duty der Antriebe über den Gang-Zyklus (0..1) |
| `n_drive_motors` | 1 | Anzahl gleichzeitig arbeitender Antriebsmotoren |
| `motor_housing_conductivity_w_mk` | W/(m·K) | Wärmeleitpfad Wicklung→Gehäuse |
| `motor_housing_area_m2` | m² | Leitquerschnitt des Pfads |
| `motor_housing_length_m` | m | Länge des Leitpfads |
| `motor_max_winding_temp_k` | K | Isolationsklasse-Grenze (z.B. Klasse F = 428 K) |
| `ambient_temp_k` | K | Auslegungs-Umgebung |

### 2. Neue Quantities + Formelkette (in `competitive_humanoid.py`)

- `q_batt_cap` (`battery.capacity`, Wh) — grounded, ersetzt den reinen Namens-Claim.
- `q_loco_duty` (`robot.locomotion_duty`, 1), `q_n_drive` (`robot.n_drive_motors`, 1).
- `q_p_mech_joint` = τ_joint · ω_joint · duty (`robot.joint_mech_power`, W) — derived.
- `q_p_loco` = n_drive · p_mech_joint / η (`robot.locomotion_power`, W) — derived;
  η ist der vorhandene Antriebsstrang-Wirkungsgrad (`cfg.efficiency`).
- `q_p_total` = p_loco + compute_power_budget (`robot.total_power`, W) — derived.
- `q_endurance_req` (`robot.required_endurance`, min) — grounded Anforderung.
- `q_p_motor_loss` = p_mech_joint · (1−η)/η (`motor.loss_power`, W) — derived
  (Verlust je Antrieb, konservativ: Getriebe+Kupfer+Eisen im η subsumiert).
- Motor-Thermik-Quantities: `motor.housing_conductivity` (W/(m·K)),
  `motor.housing_area` (m²), `motor.housing_length` (m),
  `motor.max_winding_temp` (K), `robot.ambient_temp` (K).

Anmerkung Ehrlichkeit: `locomotion_duty` und η sind deklarierte, grounded Parameter
(kein verstecktes Modell). Die Formeln sind einfachste konservative Schranken;
Verfeinerung (gang-aufgelöst) ist Roadmap A0/C und wird NICHT vorweggenommen.

### 3. Neue Recipes (in `physics_selection.py`, Block "robot: humanoid")

```
CheckRecipe(name="robot battery endurance", validator="battery_endurance",
    trigger="robot.required_endurance",
    inputs={
        "capacity_wh": ("battery.capacity", "Wh"),
        "hover_power_w": ("robot.total_power", "W"),      # generischer Power-Input
        "required_endurance_min": ("robot.required_endurance", "min"),
    })
CheckRecipe(name="drive motor overtemperature (conduction bound)",
    validator="overtemperature", trigger="motor.loss_power",
    inputs={
        "power": ("motor.loss_power", "W"),
        "conductivity": ("motor.housing_conductivity", "W/(m*K)"),
        "area": ("motor.housing_area", "m^2"),
        "length": ("motor.housing_length", "m"),
        "ambient": ("robot.ambient_temp", "K"),
        "max_service_temp": ("motor.max_winding_temp", "K"),
    })
```

Falls `overtemperature_check`s Signatur Keyword-only-Parameter (`ambient`,
`max_service_temp`) über das Recipe-Input-Mapping nicht erreicht: kleinste
notwendige Anpassung im Recipe-Runner prüfen, KEIN Validator-Fork.
Einheiten-Alias prüfen: `W/(m*K)` muss vom Unit-Parser akzeptiert sein
(sonst Basis-Einheiten verwenden).

### 4. Config-Werte (grounded, 2026-realistisch)

- **printed_humanoid:** 2100 Wh, gefordert ≥ 120 min; duty 0.35; 8 Antriebsmotoren
  aktiv; Klasse-F-Wicklung (428 K), Alu-Gehäusepfad.
- **flagship_humanoid:** 2600 Wh, gefordert ≥ 180 min; duty 0.4; 8–10 aktiv;
  Werte je Claim mit Quelle (Unitree H2 ~2–4 h Laufzeit als Wettbewerbs-Anker).
- Benchmark-Test-Erweiterung: Flagship-`endurance_min` (aus Check-Resultat) > 180
  UND overtemperature-margin > 0 für beide.

### 5. Claims & Grounding

Neue Claims: `c_battery_capacity` (Datenblatt-Anker), `c_endurance_requirement`
(Wettbewerbs-Anker), `c_motor_thermal` (Isolationsklasse + Gehäusepfad),
`c_locomotion_duty` (Gang-Duty-Begründung). Bestehender `c_battery`-Claim wird
präzisiert statt dupliziert.

### 6. Tests (TDD: zuerst rot)

In `tests/test_competitive_humanoid.py` (bzw. neuem `test_humanoid_energy.py`):
1. Beide Humanoiden: `battery_endurance` und `overtemperature` erscheinen in
   `physics_checks` und bestehen; overall bleibt `physics_verified`.
2. Negativ: Config mit 200-Wh-Akku ⇒ `battery_endurance` failt ⇒ overall
   `physics_failed`.
3. Negativ: Config mit Miniatur-Wärmepfad (z.B. length 0.5 m, area 1e-6 m²) ⇒
   `overtemperature` failt.
4. Benchmark: Flagship-Endurance > 180 min.
5. Dimensionen: alle neuen derived-Formeln bestehen den Gate-Recompute (implizit
   über overall-Assertion, explizit über einen Formel-Smoke-Test).

### 7. Nicht-Ziele (YAGNI)

- Keine gang-aufgelöste Leistungsintegration (Roadmap A0/C).
- Keine Treiber-/FOC-Verlustmodelle, keine Kabelverluste (später Teilprojekt-2/3-nah).
- Kein neues Validator-Modul, solange A trägt.
- Keine Änderung an Seam-Logik oder Domain-Detektion (Grok-Territorium, läuft parallel).

## Koordination mit Grok

- `competitive_humanoid.py` wird erst angefasst, NACHDEM Groks Seam-Migration
  (deklarierte DomainSeams für die 5 Specs) committet ist; danach Rebase auf main.
- KORREKTUR (verifiziert 2026-07-04): Der Humanoid hatte VORHER keine THERMAL-Domain.
  Die neuen K-Quantities erzeugen die Pflicht-Paare (MECH,THERM) und (ELEC,THERM).
  Das Teilprojekt liefert deshalb deklarierte DomainSeams mit (Energieerhaltung
  Verlustleistung→Wärme; Motor-Peaktemperatur ≤ Material-Servicegrenze) plus einen
  Pipeline-Fallback auf `spec.seam_certificate` (Feld existiert, wurde nie gelesen).
- Nach Implementierung: Cross-Review durch Grok über die Bridge.

## Erfolgskriterien

- Volle Testsuite grün (inkl. der 5 von Grok migrierten Tests).
- Beide Humanoiden weisen Laufzeit + Motor-Thermik nach; Negativ-Tests beweisen,
  dass die Checks scharf sind (Gate kann rot werden).
- Kein neuer Physik-Code — nur Formeln, Recipes, Config, Claims, Tests.
