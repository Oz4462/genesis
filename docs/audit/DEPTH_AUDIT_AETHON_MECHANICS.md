# DEPTH AUDIT — AETHON mechanics deep-compute + gate-proven evolution

**Modul:** `src/gen/humanoids/aethon_mechanics.py` (neu) + Evolution in
`src/gen/humanoids/genesis_humanoid.py`
**Verdikt:** **REAL** — alle vier Analysen rechnen über die echten δ-Physik-Validatoren
(numpy-FEM `fem3d`, `kinematics`, `actuation`, `scaling_laws`); jede evolutionäre Änderung
ist eine gegatete Quantity, keine Docstring-Behauptung.

## Was berechnet wird (über die echten Validatoren)

| Analyse | Validator | Ergebnis |
|---|---|---|
| (1) Struktur-FEM + Biegung | `fem3d.prismatic_bar_axial_response` (σ=F/A maschinen­genau) + `structural` Closed-Form-Biegung mit Kirsch-Kt | thigh SF 4.86, pelvis 5.70, torso 8.10 → overbuilt; **shank SF 1.68 → ok** |
| (2) Kinematik/Dynamik | `kinematics.knee_squat_hold_torque` / `reach_check` / `zmp_balance_check` | Worst-Pose-Knie 51 N·m; Reach SF 1.31; ZMP stat 0.92 / dyn 0.47 (beide ok) |
| (3) Antrieb je Gelenk | `actuation.electric_actuator_check` (Knie-Envelope) + Peak-Screen | 15 Gelenke geflaggt over/matched/**under** (Knie SF_stat 1.31 über die reflektierte Kennlinie — ehrlicher als der reine 120/75-Peak-Screen) |
| (4) Masse/Trägheit + Skalierung | `mechanics_formulas.rod_inertia_about_end` + `scaling_laws.check_knee` | 21.4 kg; Bein-Schwung 0.408 kg·m²; Knie 120 N·m = 1.63× Vorhersage → IN_BAND |

Honesty-Anker (Dünnwand): `arXiv:cond-mat/0502303` — gedruckte Dünnwände versagen UNTER der
Bulk-Festigkeit an den Lagen-Interfaces; die verwendete Festigkeit (85 MPa) ist die effektive,
bereits deratete Druckfestigkeit, und der FEM/Closed-Form-Screen ist NOTWENDIG, nicht hinreichend
(Coupon-Test bleibt die deklarierte Restlücke).

## Evolviert (gate-bewiesen, behalten)

- **Unterschenkel-Wanddicke 14 mm → 18 mm.** Die Tiefen­analyse fand den round-1-Shank als
  schwächstes lasttragendes Glied (Biege-SF ≈ **1.02**, „under"). `AETHON.shank_thick_mm` wurde
  verdickt, bis die maßgebende Struktur-SF die `STRUCT_SF_MIN = 1.5`-Marke klar überschreitet
  (jetzt **1.68**, „ok"). Reproduzierbar über `genesis_humanoid.aethon_evolution_report()`.
- **Neuer Gate `k_shank_stress`** (`q_shank_sigma_peak ≤ q_strength`). Der Shank ist jetzt ein
  EXPLIZIT gegatetes Biegeglied — exakt wie der Oberschenkel (`k_stress`). Das C-6-Rezept rechnet
  `q_shank_sigma_peak` unabhängig nach, C-15 prüft die Dimension, und die Ungleichung erzwingt
  σ_peak < Festigkeit. Ein Zurückdrehen auf eine untermaßige Wand (z. B. 11 mm → σ_peak ≈ 135 MPa)
  lässt **GATE γ mit `CONSTRAINT_VIOLATION` auf `k_shank_stress` fehlschlagen** (Test
  `test_understrength_shank_fails_gate_gamma`) — die Evolution ist damit erzwungen, nicht behauptet.

## Verworfen (mit Grund)

- **Knie-Aktuator-Upgrade (AK80-64 → stärker).** Die Antriebsanalyse flaggt das Knie als „under"
  (SF_stat 1.31 über die reflektierte Drehmoment-Drehzahl-Kennlinie bei 1.4 rad/s). Ein Upgrade
  wurde NICHT übernommen: GENESIS will VOLLSTÄNDIG aus Seriennteilen baubar bleiben, der Peak-SF
  (120/75 = 1.60) ist ausreichend, der Worst-Pose-Bedarf ist eine begrenzte transiente Spitze, und
  der DAUER-Stand ist über `k_knee_cont` separat gegatet (gehaltenes Moment ~14.1 N·m ≪ 48 N·m
  Dauergrenze, SF ~3.4). Das „under"-Flag bleibt ehrlich im Bericht stehen.
- **Verdünnen der overbuilt-Glieder (thigh/pelvis/torso, SF 4.9–8.1).** NICHT durchgeführt: die
  Dicke ist bereits durch die FDM-Mindestwand- und Lochgaten (`k_dfm_*`) und durch die
  Steifigkeit/Schwung-Trägheit mitbestimmt; ein blindes Abspecken hätte die DFM- oder
  Modal-Reserven verletzt. Als bewusst konservativ dokumentiert, nicht als Versehen.

## Round-2-Review-Fixes (diese Runde)

1. **`k_shank_stress` existiert jetzt wirklich** (war zuvor nur im Kommentar behauptet). Der Shank
   ist ein echtes gegatetes Biegeglied; ein untermaßiger Wert lässt das γ-Gate fallen. Neue Tests:
   `test_shank_is_an_explicitly_gated_bending_member`, `test_understrength_shank_fails_gate_gamma`.
2. **`aethon_evolution_report()` ist jetzt eine echte Funktion** (war eine hängende Referenz in zwei
   Kommentaren). Sie rechnet die Shank-SF vor/nach über den echten `part_structural_finding`-Validator
   und ist deterministisch. Neuer Test: `test_evolution_report_is_honest_and_reproducible`.

## 4 Linsen

- **L1 Wahrheit:** Jede Zahl ist ein Validator-Output (FEM σ=F/A maschinengenau, Skalierungs-Band aus
  Realdaten); keine geratenen Werte. Quelle/Festigkeits-Honesty via cond-mat/0502303.
- **L2 Drift:** Keine Behauptung ohne Code-Deckung — die zuvor driftenden Kommentare (Gate-Name,
  Report-Funktion) sind jetzt durch reale Symbole + Tests gedeckt.
- **L3 Vollständigkeit/Naht:** Shank an dieselbe Gate-Naht wie der Thigh angeschlossen; Evolution
  speist genau die Quantity, die das Gate prüft (keine offene Naht zwischen Analyse und Spec).
- **L4 Realisierbarkeit:** 18 mm bleibt druckbar (≥ FDM-Mindestwand), AK80-64 bleibt kaufbar,
  Gesamtmasse 21.4 kg im Zielband — die Evolution ist baubar, nicht nur rechnerisch besser.

## Tests / Gate

- `tests/test_humanoids_aethon_mechanics.py` — 19 Tests (Beispiele + Hypothesis-Property
  σ_FEM = F/A + Negativ-Guards).
- `tests/test_humanoids_genesis_humanoid.py` — Shank-Gate + Evolution-Report-Tests ergänzt.
- `gen --mode aethon`: GATE γ PASS (0 Fehler), GATE δ PASS (0 Fehler); 5-s-Stand hält (lean 0.23°).
