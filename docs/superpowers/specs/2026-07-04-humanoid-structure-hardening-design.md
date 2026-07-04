# Humanoid Teilprojekt 2: Struktur-Härtung — Design

**Datum:** 2026-07-04 · **Autor:** Claude (Orchestrator) · **Auftrag:** Ozan
**Status:** Approved (Ansatz A, Ozan 2026-07-04)
**Baut auf:** Teilprojekt 1 (Energie & Thermik, Branch humanoid-energy-thermal)

## Problem

Der Humanoid ist statisch verifiziert (Einmal-Biegespannung `q_sigma_peak ≤ q_strength`
als Constraint k_stress), aber ein gehender Roboter erlebt **zyklische** Lasten:
Millionen Schritte biegen den Oberschenkel wechselnd, das Hüftlager-Loch ist die
Kerbe, der Unterschenkel steht als Druckstab unter Körperlast, und die Schrittfrequenz
regt Struktur-Eigenmoden an. Die Validatoren dafür existieren alle
(`fatigue`/Goodman, `notch_fatigue`, `buckling`, `resonance` — physics_validation.py
VALIDATORS), werden vom Humanoiden aber nicht gefeuert. Ein Humanoid, dessen
Oberschenkel nach 200.000 Schritten am Hüftloch reißt, gilt heute als
`physics_verified`.

## Ansatz (A — 4 Checks über vorhandene Validatoren, YAGNI)

Wie in TP1: keine neuen Validatoren. Vorhandene Humanoid-Quantities werden mit
Measurands getaggt bzw. minimal ergänzt, sodass die vier existierenden Recipes
(bzw. wo nötig neue Recipe-Einträge mit Robot-Measurands) feuern.

### Die 4 Checks

1. **Goodman-Fatigue (Oberschenkel-Biegung):** `fatigue`-Validator.
   stress_amplitude = `q_sigma_nom` (Gang = wechselnde Biegung, R≈-1 ⇒ mean_stress≈0
   als DECISION mit Rationale), uts = `q_strength`,
   endurance = neue Quantity `q_endurance_limit` (MPa).
   Dauerfestigkeits-Basis EHRLICH: kein Datenblatt vorhanden ⇒ deklarierte
   Ableitung endurance = 0.30 · UTS für gedruckte Polymere (konservativer als das
   Metall-übliche 0.4-0.5; Rationale mit Quelle "additiv gefertigte Polymere,
   Schichthaftung"), als DECISION markiert. Wenn der Council/Grok später ein
   Datenblatt liefert, wird es GROUNDED.
2. **Kerb-Fatigue (Hüftlager-Loch):** `notch_fatigue`-Validator.
   nominal_alternating_stress = `q_sigma_nom`, kt = `q_kt` (Kirsch, vorhanden),
   notch_radius = `q_r_hip` (6 mm, vorhanden), peterson_constant_a = neue
   Material-Quantity (mm, DECISION mit Polymer-Rationale),
   smooth_endurance_se = `q_endurance_limit`.
3. **Euler-Knickung (Unterschenkel als Druckstab):** `buckling`-Validator.
   applied_load = `q_force` (Auslegungskraft, vorhanden), e_modulus = neue
   Quantity `q_e_modulus` (MPa, GROUNDED je Material: CF-Nylon ~6000-8000,
   CF-Primärstruktur höher), inertia/area aus `q_shank_y/z` als DERIVED-Formeln
   (I = b·h³/12, A = b·h), length = `q_shank_x` (180 mm), end_condition pinned,
   yield_strength = `q_strength`.
4. **Struktur-Resonanz:** `resonance`-Validator.
   excitation_hz = 2 · `q_step_f` (2. Gang-Harmonische als konservative Anregung,
   DERIVED), first_natural_hz = neue DERIVED-Quantity: erste Biegemode des
   Oberschenkels als Kragbalken (f1 = (1.875²/2π)·sqrt(E·I/(ρ·A·L⁴)) — alles aus
   vorhandenen Geometrie-/Materialgrößen ableitbar), min_separation_factor
   Validator-Default 2.0. Abgrenzung: `swing_resonance_check` (Pendel-Kadenz)
   bleibt unberührt — das hier ist die STEIFIGKEITS-Mode.

### Wiring

- Existierende Recipes prüfen (Trigger `fatigue.stress_amplitude`,
  `column.axial_load`, `vibration.excitation_frequency`, `notch.kt`): wo die
  Trigger/Input-Measurands passen, nur Quantities taggen; wo die bestehenden
  Recipes andere Input-Namen erwarten, neue Robot-Recipe-Einträge analog
  TP1 ergänzen (Entscheidung fällt im Plan nach Lektüre der Recipes).
- Neue Config-Felder (beide Configs, grounded/decided):
  `e_modulus_mpa`, `peterson_constant_mm`, `endurance_limit_basis` (Faktor, 0.30).
- Seam-Auswirkung: KEINE neuen Domains (alles MECHANICAL/vorhandene) ⇒ keine
  neuen Pflicht-Paare. Mit Repro im Plan verifizieren (Lehre aus TP1!).

### Tests (TDD)

Neues tests/test_humanoid_structure.py:
1. Alle 4 Checks erscheinen in physics_checks beider Humanoiden und bestehen;
   overall bleibt physics_verified.
2. Negativ Fatigue: Config mit dünnem Oberschenkel (thigh_thick_mm klein ⇒
   sigma_nom hoch) ⇒ fatigue failt ⇒ overall physics_failed.
3. Negativ Knickung: langer dünner Unterschenkel (shank-Maße überschrieben) ⇒
   buckling failt.
4. Negativ Resonanz: step_frequency nahe der Eigenfrequenz ⇒ resonance failt.
5. Formel-Konsistenz: I/A/f1-DERIVED-Werte gegen unabhängige Handrechnung (Test).
6. Gap-Freiheit: select_physics_checks liefert keine neuen Gaps.

### Benchmark-Erweiterung

test_flagship_beats_the_2026_benchmark: Fatigue-Safety-Factor ≥ 1.5 und
infinite_life True für den Flagship (Dauerläufer-Anspruch).

## Nicht-Ziele (YAGNI)

- Kein Miner/Basquin-Lebensdauer-Validator (Follow-up dokumentiert, braucht
  Validator-Registrierung).
- Kein fracture/creep/thermal_mismatch (fehlende ehrliche Eingangsdaten;
  thermal_mismatch ist TP3-nah am Motorflansch).
- Keine FEM-Moden (Roadmap A1); die Kragbalken-Formel ist die deklarierte
  konservative Schranke.

## Koordination

- Gleicher Worktree/Branch-Flow wie TP1; Grok arbeitet parallel auf seiner Spur.
- Nach Implementierung: Cross-Review durch Grok über die Bridge.

## Erfolgskriterien

- Volle Suite grün; 4 neue Checks feuern und sind scharf (Negativ-Tests).
- Alle neuen Zahlen grounded oder DECISION mit ehrlicher Rationale.
- Kein neuer Validator-Code.
