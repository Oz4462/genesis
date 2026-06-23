# Depth-Audit: `src/gen/actuation.py`

**Verdikt: REAL.** Alle vier Closed-Form-Screens sind echt gerechnet, nicht gestubbt. Keine
Quelländerung nötig — `actuation.py` bleibt byte-stabil. Der neue Test
`tests/test_actuation_characterization.py` (42 Fälle, inkl. 4 Hypothesis-Property-Tests) ist der
ausführbare Beweis.

## Was geprüft wurde (input wird wirklich konsumiert, kein Hidden-Constant)

| Funktion | Closed Form | Anker (handgerechnet) | Beweismethode |
|---|---|---|---|
| `electric_actuator_check` | `max_torque = τ_stall·N·η`, `max_speed = ω_noload/N`, Hüllkurve `max_torque·(1−ω/max_speed)`, `safety = available/τ` | stall 0.4, N=20, η=0.9 → 7.2 N·m; noload 200 → 10 rad/s; ω=4 → 4.32 N·m; τ=2.16 → SF 2.0 | Anker + Envelope-Property über den ganzen Eingaberaum |
| `hydraulic_cylinder_check` | `F = p·A − friction` | 1.5e7 Pa · 0.002 m² − 2 kN = 28 kN; SF 2.0 | Anker + `F = p·A − friction`-Property |
| `hydraulic_flow_check` | `Q = A·v` | 0.002 m² · 0.05 m/s = 1e-4 m³/s; SF 3.0 | Anker + `Q = A·v`-Property |
| `hydraulic_pressure_drop` | `Δp = 128·μ·L·Q/(π·d⁴)`, `Re = 4ρQ/(π·d·μ)`, `laminar_valid = Re<2300` | Q=1e-4, d=0.01, L=1, μ=0.03, ρ=870 → Re ≈ 369 laminar; Q=1e-2 → Re ≈ 3.7e4 turbulent | Anker + d⁴-Skalierung (½d → 16× Δp) + `laminar_valid == (Re<2300)`-Property |

Bewegungs-Beweise (jede treibende Variable verschiebt den Output messbar): Gear-Ratio hebt das
Joint-Drehmoment **und** senkt die Joint-Drehzahl (echte Übersetzungs-Trade-off), η hebt SF, Δp ∝ Q,L,μ
und ∝ 1/d⁴, ρ bewegt nur Re — nicht Δp.

## Guards / Negativpfade (alle fail-loud, getestet)
- `electric_actuator_check`: ValueError bei nicht-positivem Stall/No-Load, nicht-positivem Gear-Ratio,
  η außerhalb (0,1], negativer Nachfrage. Boundary η==1.0 zulässig. SF==inf bei τ=0 (kein Div-0-Crash).
- `hydraulic_cylinder_check`: ValueError bei nicht-positivem Druck/Fläche/Soll-Kraft, negativer Reibung.
- `hydraulic_flow_check`: ValueError bei nicht-positiver Fläche/Geschwindigkeit/Pumpenförderung.
- `hydraulic_pressure_drop`: ValueError bei nicht-positivem Flow/Durchmesser/Länge/Viskosität/Dichte.

## 4 Linsen
- **L1 Wahrheit:** Jeder Output gegen handgerechneten Anker UND eine Hypothesis-Property fixiert; die
  Formeln stimmen mit den dokumentierten Closed Forms überein (Motor-Linearhülle, F=p·A, Q=A·v,
  Hagen–Poiseuille, Re). Kein faktischer Wert ohne nachvollziehbare Herleitung.
- **L2 Drift:** Docstrings versprechen genau die implementierten Formeln + Guards; keine Lücke
  zwischen Versprechen und Code. `laminar_valid` wird nicht stillschweigend auf turbulente Strömung
  angewandt (Re<2300-Flag, mit Turbulenz-Negativfall belegt).
- **L3 Vollständigkeit/Naht:** Legacy-Test `test_actuation.py` (7) bleibt grün; neuer
  Characterization-Test (42) deckt zusätzlich Property-Invarianten, alle Guard-Permutationen,
  Boundary η==1.0, SF==inf und die d⁴-Skalierung ab. Beide Suiten koexistieren ohne Überschneidung.
- **L4 Realisierbarkeit:** Die dokumentierten ehrlichen Grenzen (Peak-vs-Continuous-Drehmoment,
  reflektierte Trägheit, Retract-Annulus, Rohr-Knicken, minor losses, turbulent) bleiben als
  bewusste Nicht-Abdeckung deklariert — kein Over-Claim. Stack-agnostisch, offline, deterministisch,
  keine neuen Dependencies (nur stdlib `math` + Hypothesis im Test).

**Ergebnis:** `actuation.py` ist REAL und unverändert; die Tiefe ist jetzt durch Property-Tests
gegen den gesamten Eingaberaum abgesichert.
