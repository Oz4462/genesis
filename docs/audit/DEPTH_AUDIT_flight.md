# Depth-Audit — `src/gen/flight.py` (multirotor closed-form axes)

**Verdikt: REAL — mit EINEM behobenen echten Defekt (fehlender Guard).**

## Umfang
Vier δ-Layer-Validatoren, je gegen eine geschlossene Form / Hand-Rechnung geprüft:
`rotor_hover_check`, `battery_endurance_check`, `current_budget_check`,
`attitude_pd_check` (plus die Primitiven `induced_velocity` / `ideal_induced_power`).

## Befund: die vier Achsen rechnen echt (keine Fassade)
Die Charakterisierungs-Tests (`tests/test_flight_characterization.py`) beweisen für jede
Achse zweierlei — (a) die Kennzahl-Behauptung hält gegen einen unabhängigen Anker, und die
Ausgabe ändert sich sinnvoll, wenn ein treibender Eingang variiert (der Eingang wird
*konsumiert*, ist keine Konstante), und (b) der dokumentierte Fail-Loud-Pfad feuert exakt:

- **Momentum-Theorie:** `T·v_i ≡ T^(3/2)/√(2·ρ·A)` maschinengenau, als Property über den
  ganzen gültigen Eingaberaum (`@given`). v_i ∝ 1/√A (kleinere Scheibe → höhere
  Induktionsgeschwindigkeit + Hover-Leistung) ist verifiziert.
- **Hover-Screen:** T/W-Verhältnis, Hover-Leistung und Sicherheitsfaktor von Grund auf
  nachgerechnet; das T/W ≥ 2-Gate kippt sauber an der Grenze.
- **Endurance:** `cap·usable/P·60` (100 Wh, 80 %, 200 W → 24 min); mehr Leistung → weniger,
  mehr Kapazität → mehr Flugzeit; Gate kippt.
- **Strombudget:** `I=P/V`, `I_max=C·Ah`, `safety_factor = min(ESC, Batterie)` — getestet,
  dass **die kleinere** Marge (die zuerst zusammenbricht) wirklich gewählt wird (beide
  Bindungs-Fälle).
- **Attitude-PD:** `ωn=√(Kp/I)`, `ζ=Kd/(2√(Kp·I))` gegen ein sauberes ζ=0.5-Design und über
  eine zweite Form `ζ=Kd/(2·I·ωn)` als Property gekreuzt; Band 0.4–0.8 kippt bei Über-/
  Unterdämpfung; Kd≤0 → ζ≤0 **scheitert ehrlich** statt zu werfen.

## Behobener Defekt (L2-Drift / L4-Edge / „keine stillen Defaults")
`rotor_hover_check`-Docstring versprach *„Raises ValueError on ... a negative thrust"*, doch
`max_total_thrust` wurde **nie** validiert: `induced_velocity` sieht nur den immer-positiven
Pro-Rotor-Hover-Schub `weight/n_rotors`, also lieferte ein negatives `max_total_thrust` still
ein **negatives** `thrust_weight_ratio` (und einen irreführenden `safety_factor`) statt laut
zu scheitern.

**Fix (minimal, ohne bestehendes Verhalten zu ändern):**
```python
if max_total_thrust < 0.0:
    raise ValueError("max total thrust must be non-negative")
```
`0.0` bleibt erlaubt — eine sinnvoll auswertbare Eingabe (ratio 0, ok=False) — passend zur
nicht-negativen Konvention von `induced_velocity`. Regression: `test_rotor_hover_negative_
thrust_raises` + Property `test_rotor_hover_any_negative_thrust_raises` über die ganze
negative Halbgerade; `test_rotor_hover_zero_thrust_is_evaluable` pinnt die 0.0-Erlaubnis.

## 4 Linsen
- **L1 (Wahrheit):** Jede Kennzahl gegen geschlossene Form / Hand-Anker + Property-Identitäten
  geprüft — keine Behauptung ohne Beleg.
- **L2 (Drift):** Doc-vs-Code-Drift gefunden und geschlossen (versprochener, aber fehlender
  Negativ-Thrust-Guard).
- **L3 (Vollständigkeit/Naht):** Alle vier Achsen + Primitiven abgedeckt; legacy `test_flight.py`
  bleibt grün (keine Verhaltensänderung an Pass-Pfaden).
- **L4 (Realisierbarkeit):** Randfälle (0-Schub, Kd≤0, kippende Gates, alle Guards) explizit
  getestet; die ehrliche Boundary (Momentum-Theorie ist ideale Untergrenze, Hover ≠ Vorwärtsflug)
  ist im Modul-Docstring deklariert und bleibt unangetastet.

**Tests:** `tests/test_flight_characterization.py` — 40 passed (zusammen mit legacy `test_flight.py`).
