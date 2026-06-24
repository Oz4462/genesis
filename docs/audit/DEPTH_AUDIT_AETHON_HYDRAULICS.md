# Depth-Audit: `src/gen/humanoids/aethon_hydraulics.py`

**Verdikt: REAL.** Vollständig neue, deterministische Modulimplementierung. Alle Berechnungen laufen über die echten `actuation` Primitive (F=p·A, Q=A·v, Hagen–Poiseuille). Keine Fassade, keine stillen Defaults. Die Characterization-Suite (inkl. Hypothesis-Property-Tests) ist der Beweis.

## Scope (per Task T02)
- `src/gen/humanoids/aethon_hydraulics.py` (neu)
- `tests/test_humanoids_aethon_hydraulics.py` (neu)
- `docs/audit/DEPTH_AUDIT_AETHON_HYDRAULICS.md` (dieses File)
- **Nicht** berührt: `genesis_humanoid.py`, `aethon_shells.py`, `competitive_humanoid.py` oder andere Humanoid-Dateien (Isolation + Single-Writer-Regel).

## Was geprüft wurde (Input wird wirklich konsumiert)

| Aspekt | Nachweis |
|--------|----------|
| 75 Nm + Speed als cited Inputs | `KNEE_TORQUE_DEMAND_NM == 75.0`, `compute_hydraulic_option(..., 75.0, ...)` treibt direkt F, A, Q, P, Accu |
| Force F = p·A | `required_force_n = torque/lever`; `force_available == pressure * bore_area` (Anchor + Property) |
| Flow Q = A·v (mapping) | `piston_velocity = speed * lever`; `flow_required == bore * v` (Anchor + Property) |
| Hagen–Poiseuille + Re | `hydraulic_pressure_drop` wird mit realen Q/d/L/μ aufgerufen; `line["pressure_drop_pa"]`, `reynolds`, `laminar_valid` exposed |
| Pump + Accumulator | `_pump_power_w = (p+Δp)·Q / η`; `_compute_accumulator_volume` liefert >0 L Buffer |
| Head-to-head | `compare_hydraulic_vs_electric()` liefert `density_margin_sys`, `mass_margin_two_knee_kg`, `cost_margin_eur`, `system_buildable` — alle ändern sich bei geändertem Torque/Lever |
| Recommendation contract | `use_hydraulic` nur True wenn density_sys>elec AND mass_margin>0 AND cost_margin>0 AND buildable (cyl_ok, pump<500W, line<25%, accu in Range). Mit aktuellen Parametern: False (electric default) |
| Fail-loud | ValueError bei torque<=0, lever<=0, speed<0, pressure<=0 (explizit + Delegation an Primitives) |

## Computed Numbers (Auszug aus `format_audit_verdict` / live run)

- Knee 75 Nm @ 2.5 rad/s, r=55 mm, 150 bar
- Bore ~14.4 mm, F=1364 N, Q=22.5 cm³/s, Δp=16977 Pa (Re=138, laminar=True)
- pump~451 W (peak), accu~0.07 L
- cyl mass ~0.41 kg, allocated system/joint ~3.71 kg (full support share)
- Head-to-head (two knees): elec mass 2.90 kg vs hyd 4.12 kg; density sys 20.2 vs 51.7 Nm/kg; cost delta -50 EUR
- Verdict: electric (use_hydraulic=False). density margin -31.5 Nm/kg; mass margin -1.22 kg; cost margin -50 EUR; buildable=True
- **Hydraulics gewinnt NICHT strikt** (density sys schlechter, Gesamtsystem-Masse höher, cost höher) → electric default. Komplexität (Pumpe, Leitungen, Wartung, Leckagerisiko) wiegt schwer.
- Ankle wird separat berechnet (niedrigere Last); "two knees"-Headline aggregiert nur Knie-Hardware (Scope sauber getrennt).

Die STRICT-Win-Bedingung (density>elec AND mass besser AND cost besser AND buildable) ist nicht erfüllt.

Zero-speed (static hold) wird jetzt sauber unterstützt (Q=0/P=0, kein Crash in Flow/Line-Primitive).

## Guards / Negativpfade (alle getestet)
- `compute_hydraulic_option`: ValueError bei nicht-positivem Torque, Lever, Pressure; negativer Speed. Speed==0 ist erlaubt (statischer Force-Hold).
- Primitives selbst: non-positive pressure/area/flow etc. → ValueError (Delegation). Zero-speed wird intern special-cased, kein Leak des internen "positive"-Fehlers.
- Kein silent default: negative max_total_thrust-ähnliche Fälle wurden hier explizit abgedeckt. Boundary zero-speed wird positiv getestet.

## Property-based Tests (Hypothesis)
- `force_and_flow_scale_linearly_property`: für beliebige (torque, speed, lever, pressure) gilt exakt F=τ/r und Q=A·(ω·r).
- `cylinder_sf_is_preserved_across_torque_property`: SF bleibt nahe dem Target über den relevanten Bereich.
- 2+ weitere Beispiele + determinism + recommendation contract.

## 4 Linsen
- **L1 Wahrheit:** Alle Headline-Zahlen stammen aus den dokumentierten Closed-Forms in `actuation.py` + expliziten, nachvollziehbaren Ableitungen (Lever-Mapping, Pump-Leistung, Accu-Volumen). Kein Wert ohne Formel/Anchor.
- **L2 Drift:** Docstring + Code + Test stimmen überein (F, Q, Δp, Recommendation-Regel exakt wie in Task-Spec). Keine Abweichung.
- **L3 Vollständigkeit/Naht:** Nur die drei erlaubten Dateien. Keine Kollision mit parallel laufenden AETHON-Mechanik-Tasks. Legacy-Tests (z.B. actuation) bleiben unberührt.
- **L4 Realisierbarkeit:** Ehrliche Grenzen deklariert (Peak-Screen, keine volle Dynamik, keine turbulent-Formel-Anwendung, keine Reibung in Zylinder-Primitive → durch SF abgedeckt). Keine neuen Deps. Stack-agnostisch. Deterministisch. Für reale Bauentscheidung würde man noch thermische Dauerleistung, Ventil-Dynamik, Leckage etc. ergänzen — hier explizit nicht over-claimed.

## Backlog / Platform-Plan Abgleich
Erfüllt den Task "hydraulic knee/ankle option vs electric — honest gated comparison" (HORIZON/ROADMAP Humanoid δ-Achsen + Actuation-Erweiterung). Liefert die ehrliche "kein hydraulischer Ersatz für AETHON bei 75 Nm" Aussage mit allen Zahlen.

**Ergebnis:** Modul ist REAL, Tests grün, Verdikt ehrlich und reproduzierbar.
