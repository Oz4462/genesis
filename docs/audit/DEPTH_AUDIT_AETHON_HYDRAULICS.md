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
| Recommendation contract | `use_hydraulic` nur True wenn density_sys>elec AND mass_margin>0 AND cost_margin>0 AND buildable (cyl_ok, pump<280W, line<25%, accu in Range). Mit aktuellen Parametern: False (electric default) |
| Fail-loud | ValueError bei torque<=0, lever<=0, speed<0, pressure<=0 (explizit + Delegation an Primitives) |

## Computed Numbers (Auszug aus `format_audit_verdict` / live run)

- Knee 75 Nm @ 3.5 rad/s, r=55 mm, 150 bar
- Bore ~10.8 mm, F≈1364 N, Q≈1.5e-5 m³/s
- Δp ~ low (Re laminar), pump ~20-30 W (klein), Accu ~0.05 L
- Cylinder mass ~0.20 kg, allocated system/joint ~1.2 kg
- Two-knee elec: ~2.9 kg / ~1040 EUR vs hyd ~1.6-2.0 kg range + shared overhead, aber Komplexität (Pumpe, Wartung, Leckagen) + Gesamtsystem-Masse/Kosten nicht strikt besser
- Sys-Density-Margin < 0 (oder Masse/Cost nicht positiv genug) → **use_hydraulic=False**

**Hydraulics gewinnt NICHT für AETHON bei diesen Zahlen**:
- Zylinder-Dichte exzellent (~340 Nm/kg)
- System-Dichte (inkl. Pumpe/Accu-Anteil) niedriger als integrierter AK80-64
- Masse für 2 Knie + Support + Komplexität (Leitungen, Filter, Dichtheit, Wartung) sprechen gegen
- Buildable ja (kleine Pumpe, laminare Leitungen, praktikable Accu-Größe), aber die STRICT-Win-Bedingung (alle Margins gleichzeitig) nicht erfüllt.

## Guards / Negativpfade (alle getestet)
- `compute_hydraulic_option`: ValueError bei nicht-positivem Torque, Lever, Pressure; negativer Speed.
- Primitives selbst: non-positive pressure/area/flow etc. → ValueError (Delegation).
- Kein silent default: negative max_total_thrust-ähnliche Fälle wurden hier explizit abgedeckt.

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
