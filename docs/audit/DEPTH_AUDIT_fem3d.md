# Depth-Audit: `src/gen/fem3d.py`

**Verdikt: REAL.** Der 3-D-Kontinuums-FEM (Constant-Strain-Tetraeder, lineare
isotrope Elastizität, reines numpy) rechnet Spannung und Verformung **als Funktion
von Last und Geometrie** — keine gecannten Konstanten. Mit Charakterisierungs-Tests
über die Skalierungsgesetze nachgewiesen.

## Headline-Claim
> "the δ-physics FEM genuinely computes deflection/stress as a function of applied
> load and geometry (not canned constants)."

## Beweis (was wirklich konsumiert wird)
Für einen prismatischen Stab (Länge `L`, Querschnitt `A = W·H`, E-Modul `E`) unter
axialer Zugkraft `F` gelten die geschlossenen Formen
`σ_xx = F/A` und `δ = F·L/(A·E)`. Der Solver reproduziert genau diese Abhängigkeiten:

| Eingabe-Änderung | erwartet | gemessen (FEM) |
|---|---|---|
| Kraft `F → 2F` | σ ×2, δ ×2 (exakt, lineares System) | ×2.0 / ×2.0 (rtol 1e-9) |
| Länge `L → 2L` | δ ×2 (∝L), σ unverändert | δ ×1.97, σ ×1.0 |
| Fläche `A → A/2` (dünner) | σ ×2 (∝1/A), δ ×2 | σ ×2.0 (exakt), δ ×1.99 |
| `F = 0` | σ = 0, δ = 0 (kein Offset) | 0 / 0 |

`σ = F/A` ist über den ganzen (Kraft, Geometrie)-Raum **maschinengenau exakt**
(Gleichgewicht) — per Hypothesis-Property `test_property_mean_stress_is_force_over_area`
abgesichert. Die Verformung trägt einen kleinen lastaufbringungs-bedingten
End-Effekt (grober 2×2-Querschnitt mit Knoten-Punktlasten), liegt aber innerhalb
~3 % der geschlossenen Form und skaliert mit ~1.97–2.0 statt ~1.0 — die Fassade
(Geometrie ignoriert ⇒ Verhältnis 1.0) wird klar verworfen. Toleranzband: 5 %.

Eine canned-constant-Implementierung würde alle Geometrie-/Kraft-Verhältnisse auf
1.0 kollabieren lassen und den Test reißen.

## Änderungen
- **`fem3d.py`**: neuer öffentlicher Treiber `prismatic_bar_axial_response(...)`
  + Ergebnis-Datenklasse `PrismaticBarResponse`. Reiner Aufruf von
  `solve_elasticity` (Symmetrie-BCs, gleichverteilte End-Last); liest mittlere
  σ_xx und mittlere End-Verformung aus. Fail-loud-Guards: nicht-positive
  Geometrie/E-Modul und `nu ∉ (-1, 0.5)` (sonst singuläre/divergierende
  Elastizitätsmatrix → stiller Falschwert). **Der bestehende exakte
  Uniform-Stress-Solver wurde nicht verändert.**
- **`tests/test_fem3d_characterization.py`**: neue Charakterisierungs-Datei
  (Beispiel- + Hypothesis-Property-Tests). Die Legacy-`test_fem3d.py` bleibt
  unangetastet (no-churn).

## L1–L4
- **L1 Wahrheit:** Skalierungsgesetze gegen geschlossene Elastizitäts-Formen
  geankert, nicht behauptet.
- **L2 Drift:** Helper benutzt exakt die bestehenden Solver-/Mesher-Signaturen;
  keine Doppel-Implementierung.
- **L3 Naht:** schließt die Lücke "ist die δ-Physik echt last-/geometrie-abhängig?"
  zwischen dem nur-uniform-getesteten Solver und dem δ-Gate.
- **L4 Realisierbarkeit:** End-Effekt ehrlich benannt und mit Toleranzband (5 %)
  abgefangen statt verschwiegen; Guards verhindern stille Defaults.

Volle fem3d-Suite (neu + Legacy): **13 passed**.
